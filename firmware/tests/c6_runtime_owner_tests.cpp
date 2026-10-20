#include "c6_motion_runtime.hpp"
#include "bench_c6_io.hpp"
#include "c6_pd_monitor.hpp"
#include "soc/gpio_struct.h"
#include "esp_pm.h"
#include "fakes/sensor_fixture.hpp"
#include <chrono>
#include <cstring>
#include <memory>
#include <string>
#include <regex>
#include <set>
using sensor_fixture::check;
namespace gc=blinds::power::continuity;
namespace ch=smart_blinds::charger;
struct MockTask {
    std::string name;std::thread thread;std::mutex mutex;std::condition_variable cv;
    unsigned notices=0;bool stop=false;
};
struct MockQueue { std::mutex mutex;std::vector<unsigned char> body;bool present=false; };
struct MockBus {};
struct MockDevice { unsigned address=0;MockTask* owner=nullptr; };
struct MockPm { MockTask* owner=nullptr;bool held=false; };
MockGpio GPIO;
namespace runtime_fake {
std::atomic<unsigned> fast_reads{0},stop_reads{0},actuations{0};std::atomic<bool> stop{false},fault{false};
}
namespace {
struct EndTask {};
thread_local MockTask* current=nullptr;
std::vector<std::unique_ptr<MockTask>> tasks;
std::vector<std::unique_ptr<MockQueue>> queues;
std::vector<std::unique_ptr<MockPm>> locks;
std::mutex registry,bus_mutex;
std::condition_variable bus_cv;
MockBus bus;
std::array<std::uint8_t,0x49> registers{};
std::array<std::uint16_t,512> words{};
std::array<std::uint8_t,256> pd_regs{};
std::atomic<unsigned> gauge_reads{0},pd_reads{0};
std::atomic<bool> stuck_alert{false};
std::atomic<bool> inject_off_race{false},off_read_waiting{false},off_race_released{false};
std::atomic<bool> inject_telemetry_race{false},telemetry_waiting{false},telemetry_released{false};
void(*power_irq)(void*)=nullptr;void* power_irq_arg=nullptr;
std::atomic<std::int64_t> offset{0};
std::chrono::steady_clock::time_point origin;
std::atomic<unsigned> transfers{0},adds{0},removes{0},held_locks{0},released_locks{0},missing_off_reads{0};
bool block=false,blocked=false,release_call=false,fail_call=false;
unsigned block_device=0;
std::function<void()> transfer_hook;
std::uint64_t before_block_time=0;
void await(const std::function<bool()>& predicate,const char* reason,unsigned milliseconds=6000) {
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(milliseconds);
    while(!predicate()) {
        check(std::chrono::steady_clock::now()<deadline,reason);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}
void reset_bus() {
    std::lock_guard<std::mutex> guard(bus_mutex);
    registers.fill(0);registers[0x48]=0x19;registers[0x0A]=0xA3;registers[0x13]=0x21;registers[0x1D]=1;
    sensor_fixture::Time fake_time;sensor_fixture::Wire fake(fake_time);words=fake.words;
    pd_regs.fill(0);pd_regs[0x2F]=0x25;pd_regs[0x0C]=0xFB;pd_regs[0x70]=3;pd_regs[0x13]=0x40;
    const unsigned values[]{0x04019096,0x0002D0FA,0x0004B0FA};
    for(unsigned i=0;i<3;++i) for(unsigned b=0;b<4;++b) pd_regs[0x85+i*4+b]=values[i]>>(8*b);
    gauge_reads=pd_reads=0;stuck_alert=false;inject_off_race=off_read_waiting=off_race_released=false;power_irq=nullptr;power_irq_arg=nullptr;
    inject_telemetry_race=telemetry_waiting=telemetry_released=false;
    block=blocked=release_call=fail_call=false;block_device=0;transfer_hook={};
}
blinds::runtime::Configuration configuration(bool pd=false) {
    blinds::runtime::Configuration c;
    c.task_timing_verified=c.bus_readback_verified=c.sensor_handoff_verified=true;c.verified_for_boot=99;
    c.port.bench_qualified=true;c.port.qualification_id=1;c.port.motor_sign=c.port.encoder_sign=1;
    c.motion.bench_qualified=c.motion.holding_qualified=true;c.motion.qualification_id=1;
    const blinds::Knot knots[]={{0,0},{1000,100}};c.calibration.assign(knots,2,7);
    c.gauge=sensor_fixture::profile();c.clock.validated=true;
    if(pd) {
        c.pd_shared_bus_verified=true;
        c.pd_factory={1,1,99,true,true,true,true,true,0x25,{0x04019096,0x0002D0FA,0x0004B0FA}};
    }
    check(c.valid(99),"synthetic test configuration invalid");return c;
}
void shutdown() {
    // Application has no teardown API; the host seam stops owner loops solely
    // at their task waits, control first, so no real application lifecycle is claimed.
    for(const char* name:{"blind_control","blind_power"}) for(auto& task:tasks) if(task->name==name) {
        { std::lock_guard<std::mutex> lock(task->mutex);task->stop=true;task->cv.notify_all(); }
        task->thread.join();
    }
    tasks.clear();queues.clear();locks.clear();held_locks=0;
}
struct Fixture {
    std::unique_ptr<blinds::c6::MotionRuntime> runtime;
    explicit Fixture(bool pd=false) {
        origin=std::chrono::steady_clock::now();offset=0;reset_bus();transfers=adds=removes=0;
        released_locks=0;missing_off_reads=0;runtime_fake::fast_reads=runtime_fake::stop_reads=runtime_fake::actuations=0;runtime_fake::stop=false;runtime_fake::fault=false;
        runtime=std::make_unique<blinds::c6::MotionRuntime>(99,configuration(pd));
        check(runtime->start({nullptr,[](void*){return true;}},true),"actual runtime failed to start");
        await([&]{return runtime->io_qualified() && held_locks==0;},"initial clean closure/PM release failed");
        check(!missing_off_reads,"sensor request preceded actual physical OFF publication");
    }
    ~Fixture() { shutdown(); }
    void awake(bool value) {
        runtime->ingress().radio(true,value);runtime->publish_network(esp_timer_get_time());
    }
    bool power_ready() {
        char json[1500]{};runtime->status(json,sizeof(json),esp_timer_get_time());
        return std::strstr(json,"\"power_ready\":true");
    }
    std::string telemetry() {
        char out[768]{};
        check(runtime->telemetry(out,sizeof(out),123),"informational serialization failed");
        return out;
    }
    unsigned reg(unsigned address) { std::lock_guard<std::mutex> lock(bus_mutex);return registers[address]; }
    void park() {
        awake(false);
        await([&]{return reg(0x10)==0x90 && held_locks==0;},"actual sensor did not park before PM release");
    }
};
}
TaskHandle_t xTaskGetCurrentTaskHandle() { return current; }
BaseType_t xTaskCreate(void(*entry)(void*),const char* name,unsigned,void* context,unsigned,TaskHandle_t* out) {
    auto task=std::make_unique<MockTask>();task->name=name;*out=task.get();
    task->thread=std::thread([raw=task.get(),entry,context]{current=raw;try { entry(context); } catch(const EndTask&) {}});
    tasks.push_back(std::move(task));return pdPASS;
}
void xTaskNotifyGive(TaskHandle_t task) {
    if(!task) return;
    { std::lock_guard<std::mutex> lock(task->mutex);++task->notices;task->cv.notify_all(); }
    // Force the lower-priority owner to observe a prematurely posted request.
    // A real synchronous SDK call can also yield the control task. Correct
    // source posts its request only after actual OFF and never enters this seam.
    if(current && current->name=="blind_control" && task->name=="blind_power") {
        bool present=false;{ std::lock_guard<std::mutex> lock(queues[3]->mutex);present=queues[3]->present; }
        if(!present) await([]{return missing_off_reads.load()!=0;},"early request was not observed",1000);
    }
}
void vTaskNotifyGiveFromISR(TaskHandle_t task,BaseType_t* wake) { xTaskNotifyGive(task);*wake=pdFALSE; }
std::uint32_t ulTaskNotifyTake(BaseType_t,TickType_t timeout) {
    check(current,"task wait from non-owner");std::unique_lock<std::mutex> lock(current->mutex);
    const auto ready=[&]{return current->notices || current->stop;};
    if(timeout==portMAX_DELAY) current->cv.wait(lock,ready);
    else current->cv.wait_for(lock,std::chrono::milliseconds(timeout),ready);
    if(current->stop) throw EndTask{};
    const auto value=current->notices;current->notices=0;return value;
}
void vTaskDelay(TickType_t ticks) { std::this_thread::sleep_for(std::chrono::milliseconds(ticks)); }
QueueHandle_t xQueueCreate(unsigned count,std::size_t size) {
    check(count==1,"runtime changed queue bound");auto q=std::make_unique<MockQueue>();q->body.resize(size);
    auto* raw=q.get();queues.push_back(std::move(q));return raw;
}
BaseType_t xQueueOverwrite(QueueHandle_t q,const void* data) {
    std::lock_guard<std::mutex> guard(q->mutex);std::memcpy(q->body.data(),data,q->body.size());q->present=true;
    if(q==queues[3].get() && current && current->name=="blind_control" && off_read_waiting) off_race_released=true;
    if(q==queues[7].get() && current && current->name=="blind_power" && telemetry_waiting) telemetry_released=true;
    return pdPASS;
}
BaseType_t xQueuePeek(QueueHandle_t q,void* data,TickType_t wait) {
    check(wait==0,"runtime reader blocked on queue");
    if(q==queues[3].get() && current && current->name=="blind_power" && inject_off_race.exchange(false)) {
        off_read_waiting=true;
        await([] {return off_race_released.load();},"control did not publish during OFF read",500);
        off_read_waiting=false;
    }
    if(q==queues[7].get() && !current && inject_telemetry_race.exchange(false)) {
        telemetry_waiting=true;
        await([] {return telemetry_released.load();},"sensor did not publish during telemetry read",500);
        telemetry_waiting=false;
    }
    std::lock_guard<std::mutex> guard(q->mutex);
    if(!q->present) {
        if(q==queues[3].get() && current && current->name=="blind_power") ++missing_off_reads;
        return pdFALSE;
    }
    std::memcpy(data,q->body.data(),q->body.size());return pdPASS;
}
BaseType_t xQueueReceive(QueueHandle_t q,void* data,TickType_t wait) {
    check(wait==0,"runtime blocked on reference queue");std::lock_guard<std::mutex> guard(q->mutex);
    if(!q->present) return pdFALSE;
    std::memcpy(data,q->body.data(),q->body.size());q->present=false;return pdPASS;
}
BaseType_t xQueueSend(QueueHandle_t q,const void* data,TickType_t wait) {
    check(wait==0,"runtime blocked on send");return xQueueOverwrite(q,data);
}
std::int64_t esp_timer_get_time() {
    return 1000000+offset.load()+std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-origin).count();
}
int gpio_get_level(gpio_num_t pin) {
    if(pin==17) {
        if(stuck_alert) return 0;
        std::lock_guard<std::mutex> lock(bus_mutex);
        const auto al=(pd_regs[0x0D]?0x40:0)|(pd_regs[0x0F]?0x20:0)|
            (pd_regs[0x12]?0x10:0)|(pd_regs[0x16]?2:0);
        bool bq=false;for(unsigned p=0x22;p<=0x27;++p) bq=bq||registers[p];
        return !bq && !(al&~pd_regs[0x0C]);
    }
    return pin!=blinds::io::Pins::in1 && pin!=blinds::io::Pins::in2;
}
int gpio_config(const gpio_config_t* c) {
    check(current && current->name=="blind_control" && c->pin_bit_mask==(1ULL<<17) &&
          c->mode==GPIO_MODE_INPUT && !c->pull_up_en && !c->pull_down_en,"shared ALERT GPIO setup incorrect");
    GPIO.enable.val&=~(1U<<17);return 0;
}
int gpio_install_isr_service(int) { return 0; }
int gpio_set_intr_type(gpio_num_t,int) { return 0; }
int gpio_isr_handler_add(gpio_num_t pin,void(*fn)(void*),void* arg) {
    if(pin==17) { power_irq=fn;power_irq_arg=arg; }return 0;
}
void fire_irq() { check(power_irq,"shared interrupt handler missing");power_irq(power_irq_arg); }
int gpio_wakeup_enable(gpio_num_t,int) { return 0; }
int esp_sleep_enable_gpio_wakeup() { return 0; }
int esp_pm_lock_create(int,int,const char*,esp_pm_lock_handle_t* out) {
    auto p=std::make_unique<MockPm>();p->owner=current;*out=p.get();
    std::lock_guard<std::mutex> lock(registry);locks.push_back(std::move(p));return 0;
}
int esp_pm_lock_acquire(esp_pm_lock_handle_t p) {
    check(p->owner==current && !p->held,"wrong owner/double PM acquire");p->held=true;++held_locks;return 0;
}
int esp_pm_lock_release(esp_pm_lock_handle_t p) {
    check(p->owner==current && p->held,"wrong owner/double PM release");p->held=false;--held_locks;++released_locks;return 0;
}
int i2c_new_master_bus(const i2c_master_bus_config_t* cfg,i2c_master_bus_handle_t* out) {
    check(current && current->name=="blind_power" && cfg->sda_io_num==10 && cfg->scl_io_num==11 &&
          !cfg->flags.enable_internal_pullup,"wrong I2C owner/configuration");*out=&bus;return ESP_OK;
}
int i2c_master_bus_add_device(i2c_master_bus_handle_t b,const i2c_device_config_t* cfg,i2c_master_dev_handle_t* out) {
    check(current && current->name=="blind_power" && b==&bus && cfg->scl_speed_hz==100000,"wrong attach owner/config");
    *out=new MockDevice{cfg->device_address,current};++adds;return ESP_OK;
}
int i2c_master_bus_rm_device(i2c_master_dev_handle_t d) { check(d->owner==current,"cross-task teardown");++removes;delete d;return ESP_OK; }
int i2c_master_transmit_receive(i2c_master_dev_handle_t d,const std::uint8_t* pointer,std::size_t send,
                               std::uint8_t* output,std::size_t size,int timeout) {
    check(current==d->owner && send==1 && timeout==10,"wrong read owner/shape/timeout");++transfers;
    std::unique_lock<std::mutex> lock(bus_mutex);
    if(block && block_device==d->address) {
        block=false;blocked=true;before_block_time=esp_timer_get_time();bus_cv.notify_all();
        bus_cv.wait(lock,[]{return release_call;});
        if(fail_call) return ESP_ERR_TIMEOUT;
    }
    if(transfer_hook) { auto hook=std::move(transfer_hook);hook(); }
    if(d->address==0x6B) {
        check(*pointer+size<=registers.size(),"charger map overflow");std::copy_n(registers.data()+*pointer,size,output);
        for(unsigned i=0;i<size;++i) if(*pointer+i>=0x22 && *pointer+i<=0x27) registers[*pointer+i]=0;
    } else if(d->address==0x28) {
        ++pd_reads;check(*pointer+size<=pd_regs.size(),"PD map overflow");
        std::copy_n(pd_regs.data()+*pointer,size,output);
        for(unsigned i=0;i<size;++i) {
            const auto p=*pointer+i;
            if(p==0x0D || p==0x0F || p==0x12 || p==0x14 || p==0x16) pd_regs[p]=0;
        }
    } else {
        ++gauge_reads;
        check(size==2 && (d->address==0x36 || d->address==0x0B),"gauge read shape/address changed");
        const auto word=words[*pointer+(d->address==0x0B ? 0x100:0)];output[0]=word;output[1]=word>>8;
    }
    return ESP_OK;
}
int i2c_master_transmit(i2c_master_dev_handle_t d,const std::uint8_t* bytes,std::size_t size,int timeout) {
    if(d->address==0x28) {
        check(current==d->owner && size==2 && bytes[0]==0x0C && !(bytes[1]&0x72) && timeout==10,
              "PD wrote outside allowlisted mask/owner");
        std::lock_guard<std::mutex> lock(bus_mutex);pd_regs[0x0C]=bytes[1];return ESP_OK;
    }
    check(current==d->owner && d->address==0x6B && size>=2 && size<=3 && timeout==10,"wrong write owner/shape");
    std::lock_guard<std::mutex> lock(bus_mutex);++transfers;
    check(!(bytes[0]==0x0F && (bytes[1]&0x20)),"charge enabled");
    std::copy_n(bytes+1,size-1,registers.data()+bytes[0]);if(bytes[0]==0x10) registers[0x10]&=~8;return ESP_OK;
}
void empty_physical_records_publish_no_observation() {
    origin=std::chrono::steady_clock::now();offset=0;reset_bus();transfers=adds=removes=0;
    held_locks=0;runtime_fake::actuations=0;
    auto runtime=std::make_unique<blinds::c6::MotionRuntime>(99,blinds::runtime::Configuration{});
    check(runtime->start({nullptr,[](void*){return true;}},true),"unqualified owner startup failed");
    await([] {std::lock_guard<std::mutex> guard(queues[4]->mutex);return queues[4]->present;},"unqualified control never published");
    char out[768]{};
    check(runtime->telemetry(out,sizeof(out),123),"unqualified actual runtime telemetry failed");
    check(std::strstr(out,"\"state\":\"absent\"") && std::strstr(out,"\"soc_pct\":null") &&
          std::strstr(out,"\"input_present\":null") && std::strstr(out,"\"kind\":\"none\""),"unqualified runtime fabricated an observation/fault");
    check(!runtime->io_qualified() && !runtime_fake::actuations && !held_locks && !adds && !transfers,
          "telemetry initialized unqualified I/O or sensing");
    shutdown();
}
void initialized_owner_loss_still_retires_sensor() {
    Fixture f;f.awake(true);
    await([&] {return f.power_ready();},"owner-loss fixture warmup failed");
    runtime_fake::fault=true;f.runtime->notify_request();
    await([&] {return !f.runtime->io_qualified();},"lost I/O owner stayed qualified");
    await([&] {return f.telemetry().find("\"state\":\"invalid\"")!=std::string::npos;},"lost owner failed to retire observation");
    check(!f.power_ready() && held_locks==2 && !f.runtime->parked_off(esp_timer_get_time()) && !runtime_fake::actuations,
          "owner loss published power/park or released PM");
    const auto first=f.telemetry();
    check(first.find("\"kind\":\"none\"")==std::string::npos,"owner loss lacked first fault");
    runtime_fake::fault=false;f.awake(false);f.awake(true);
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    check(!f.runtime->io_qualified() && !f.power_ready() && held_locks==2,"later I/O success revived failed owner");
}
void newer_off_publication_during_guard_copy() {
    Fixture f;
    inject_off_race=true;f.awake(true);
    await([] {return off_race_released.load();},"OFF publication race was not exercised");
    await([&] {return f.power_ready();},"healthy newer OFF publication was rejected");
    check(f.runtime->io_qualified() && !runtime_fake::actuations,"OFF race changed physical permissions");
    f.park();
}
void newer_telemetry_publication_during_response_copy() {
    Fixture f;f.awake(true);
    await([&] {return f.power_ready();},"telemetry race warmup failed");
    inject_telemetry_race=true;
    const auto result=f.telemetry();
    check(telemetry_released,"telemetry publication barrier did not run");
    std::smatch match;
    check(std::regex_search(result,match,std::regex(R"rx("sent_us":"([0-9a-f]{16})")rx")),"missing telemetry response time");
    const auto sent=std::stoull(match[1].str(),nullptr,16);
    const std::regex stamp(R"rx("sample_us":"([0-9a-f]{16})")rx");
    for(auto i=std::sregex_iterator(result.begin(),result.end(),stamp);i!=std::sregex_iterator();++i) {
        const auto sampled=std::stoull((*i)[1].str(),nullptr,16);
        if(sampled>sent) std::cerr<<"telemetry future sample="<<sampled<<" response="<<sent<<" delta="<<(sampled-sent)<<"\n";
        check(sampled<=sent,"new healthy telemetry sample was published after response time");
    }
    check(result.find("\"state\":\"retained\"")!=std::string::npos,"fresh battery marked invalid");
    f.park();
}
void real_workers_wake_park_cold() {
    Fixture f;f.awake(true);
    await([&]{return f.power_ready();},"actual runtime never completed cold warmup");
    check(f.reg(0x10)==0x93 && held_locks==2 && adds==3,"active watchdog/owner setup wrong");
    for(unsigned i=0;i<20;++i) check(f.power_ready(),"status consumed control publication");
    f.park();const auto attachments=adds.load();
    // A genuine short park must retain continuity, without a second warmup or
    // fresh hardware attach. Source stamps still come from the new read.
    f.awake(true);await([&]{return f.power_ready();},"qualified short wake restarted cold warmup",600);
    check(adds==attachments && f.reg(0x10)==0x93,"short wake replaced session or missed watchdog restore");
    f.park();
    for(unsigned i=0;i<5;++i) { f.runtime->notify_request();std::this_thread::sleep_for(std::chrono::milliseconds(1)); }
    check(adds==attachments && f.reg(0x10)==0x90 && !f.power_ready(),"idle wake restamped/restarted session");
    offset+=8LL*60*60*1000000;f.awake(true);
    await([&]{return adds==attachments+3;},"expired session did not reconstruct on owner");
    check(!f.power_ready() && removes==3 && f.reg(0x10)==0x93,"cold restart bypassed history or active WD");
    await([&]{return f.power_ready();},"cold restart required reboot/requalification");
    f.park();check(runtime_fake::actuations==0,"unreferenced host test actuated motor");
    const auto existing=adds.load();f.runtime->transport_fault();f.awake(true);
    await([&]{return !f.runtime->io_qualified();},"global ownership fault did not revoke runtime");
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    check(adds==existing && !f.power_ready(),"cold restart erased a real global ownership fault");
}
void blocked_call_stop_and_lock(unsigned address) {
    Fixture f(address==0x28);
    { std::lock_guard<std::mutex> lock(bus_mutex);block=true;block_device=address; }
    f.awake(true);
    { std::unique_lock<std::mutex> lock(bus_mutex);check(bus_cv.wait_for(lock,std::chrono::seconds(2),[]{return blocked;}),"SDK call did not block"); }
    const auto reads=runtime_fake::stop_reads.load(),releases=released_locks.load(),prior_removes=removes.load();
    runtime_fake::stop=true;f.runtime->local_stop_from_isr();f.awake(false);
    await([&]{return runtime_fake::stop_reads>reads;},"blocked sensor prevented raw STOP owner");
    check(held_locks==2 && released_locks==releases && !f.runtime->parked_off(esp_timer_get_time()),
          "control released PM/parked while synchronous I2C still blocked");
    char json[1500]{};check(f.runtime->status(json,sizeof(json),esp_timer_get_time()),"status blocked on sensor");
    const auto info=f.telemetry();
    check(info.find("\"charge_authorized\":false")!=std::string::npos,"blocked informational read granted charge");
    // A deliberately over-budget call returns a real failure, not a new good
    // sample. Only returning owner may clean up; no timeout thread removes it.
    { std::lock_guard<std::mutex> lock(bus_mutex);fail_call=true;release_call=true;bus_cv.notify_all(); }
    await([&]{return !f.runtime->io_qualified();},"first bus failure did not revoke actual runtime");
    check(held_locks==2 && removes==prior_removes && !f.power_ready(),"fault released PM or cross-task removed handles");
}
void cable(bool present,unsigned threshold=76) {
    std::lock_guard<std::mutex> lock(bus_mutex);
    registers[5]=present?threshold:36;registers[0x1B]=present?15:0;registers[0x1C]=present?0x16:0;
    registers[0x22]|=15;
    pd_regs[0x0E]=present?0x21:0;pd_regs[0x10]=present?10:4;pd_regs[0x15]=present?2:0;
    pd_regs[0x29]=present?0x18:0x13;pd_regs[0x0D]|=1;pd_regs[0x0F]|=14;
    const auto rdo=present?0x2303E8FA:0;
    for(unsigned i=0;i<4;++i) pd_regs[0x91+i]=rdo>>(8*i);
}
void actual_cable_lifecycle() {
    Fixture f(true);
    check(adds==4 && !gauge_reads && f.reg(0x10)==0x90,"initial source-only setup woke full gauge");
    const auto reads=gauge_reads.load();
    cable(true);fire_irq();
    smart_blinds::pd::Observation source{};
    check(!f.runtime->source_status(source,esp_timer_get_time()),"IRQ did not revoke source immediately");
    await([&]{return held_locks==0 && f.reg(5)==76 && f.runtime->source_status(source,esp_timer_get_time());},
          "parked cable event did not close under PM");
    check(gauge_reads==reads && f.reg(0x10)==0x90 && f.reg(7)==10 && f.reg(0x14)==0x16,
          "source-only wake resumed gauge/watchdog or lifted ILIM");
    f.awake(true);await([&]{return f.power_ready();},"awake cable monitor failed full warmup");
    await([&]{return f.runtime->source_status(source,esp_timer_get_time()) && source.state==smart_blinds::pd::State::ready;},
          "actual source status never qualified current");
    char json[1500]{};check(f.runtime->status(json,sizeof(json),esp_timer_get_time()),"motion status failed");
    const std::regex key("\"([a-z_]+)\":");const std::string text(json);std::set<std::string> fields;
    for(auto it=std::sregex_iterator(text.begin(),text.end(),key);it!=std::sregex_iterator();++it) fields.insert((*it)[1]);
    const std::set<std::string> expected{"boot","sampled_us","phase","result","command","last_message",
        "io_qualified","fresh","ready","reference_valid","awake_required","height_mm","power_ready",
        "power_sampled_us","soc_percent"};
    check(fields==expected,"existing strict motion-status wire schema changed");
    cable(false);fire_irq();
    await([&]{return f.reg(5)==36 && f.runtime->source_status(source,esp_timer_get_time()) &&
          source.state==smart_blinds::pd::State::detached;},"awake stationary unplug failed");
    check(f.runtime->io_qualified() && !runtime_fake::actuations,"normal unplug faulted or actuated");
    f.park();const auto parked_reads=gauge_reads.load();
    const auto battery_part=[](const std::string& info) {
        const auto begin=info.find("\"battery\":");const auto end=info.find("}",begin);
        check(begin!=std::string::npos && end!=std::string::npos,"battery snapshot missing");
        return info.substr(begin,end-begin+1);
    };
    const auto retained=battery_part(f.telemetry());
    check(retained.find("\"state\":\"retained\"")!=std::string::npos,"healthy park discarded battery observation");
    const auto requests=transfers.load(),released=released_locks.load();
    for(unsigned i=0;i<100;++i) check(battery_part(f.telemetry())==retained,"status request restamped battery");
    check(gauge_reads==parked_reads && transfers==requests && released_locks==released && held_locks==0,
          "informational reads acquired sensors or changed PM");
    // Preserve entire parked age through repeated cable-only service. After the
    // real continuity interval expires, next motion wake must be a cold session.
    offset+=90000000;fire_irq();
    await([&]{return held_locks==0 && f.runtime->source_status(source,esp_timer_get_time());},"source poll stalled");
    check(gauge_reads==parked_reads,"source service renewed gauge continuity");
    check(battery_part(f.telemetry())==retained,"source-only service restamped battery");
    const auto prior_adds=adds.load();f.awake(true);
    await([&]{return adds>=prior_adds+4;},"expired park did not replace owner epoch");
    await([&]{return f.power_ready();},"exact dynamic parked image lost at cold restart");
    check(f.reg(5)==36 && f.reg(7)==10 && !runtime_fake::actuations,"cold restart guessed source/actuated");
    { std::lock_guard<std::mutex> lock(bus_mutex);pd_regs[0x0C]=0xFB; }
    fire_irq();
    await([&]{return !f.runtime->io_qualified();},"unexpected PD reset was repaired/ignored");
    const auto invalid=f.telemetry();
    check(invalid.find("\"state\":\"invalid\"")!=std::string::npos &&
          invalid.find("\"state\":\"unknown\"")!=std::string::npos,"fault retained current informational values");
}
void bounded_shared_line() {
    Fixture f(true);
    stuck_alert=true;fire_irq();
    await([&]{return held_locks==2;},"asserted ALERT did not acquire PM");
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    check(f.runtime->io_qualified() && held_locks==2,"one reasserted event was immediately terminal/released PM");
    stuck_alert=false;
    await([&]{return held_locks==0;},"bounded reassertion never completed");
    check(!gauge_reads,"source drain woke gauge");
    stuck_alert=true;fire_irq();
    await([&]{return !f.runtime->io_qualified();},"permanently asserted line never timed out",2000);
    check(held_locks==2 && !runtime_fake::actuations,"stuck line released PM or actuated");
}
void pd_adapter_owner_epoch() {
    for(unsigned scenario=0;scenario<3;++scenario) {
        origin=std::chrono::steady_clock::now();offset=0;reset_bus();
        MockTask owner,other;owner.name="blind_power";other.name="other";current=&owner;
        gc::BusEpoch epoch;
        blinds::c6::PdMonitor adapter({},epoch);
        check(adapter.attach(&bus)==ESP_OK && adapter.policy().initialize(0).error==smart_blinds::pd::Error::none,
              "owned PD adapter setup failed");
        const auto removed=removes.load();
        if(scenario==0) {
            current=&other;
            check(adapter.close()==ESP_ERR_INVALID_STATE && removes==removed,"wrong task removed PD handle");
        } else {
            transfer_hook=[&] { if(scenario==1) epoch.retire();else current=&other; };
            check(adapter.policy().poll().error==smart_blinds::pd::Error::bus,
                  "mid-transfer epoch/task loss published PD observation");
            check(removes==removed,"failed PD transfer used cross-task teardown");
        }
        current=&owner;check(adapter.close()==ESP_OK && removes==removed+1,"owner could not remove PD handle");
    }
    current=nullptr;
}
int main() {
    if(std::getenv("SB_TEST_TELEMETRY_RACE")) {newer_telemetry_publication_during_response_copy();return 0;}
    if(std::getenv("SB_TEST_OFF_RACE")) {newer_off_publication_during_guard_copy();return 0;}
    empty_physical_records_publish_no_observation();initialized_owner_loss_still_retires_sensor();newer_telemetry_publication_during_response_copy();newer_off_publication_during_guard_copy();pd_adapter_owner_epoch();real_workers_wake_park_cold();actual_cable_lifecycle();bounded_shared_line();blocked_call_stop_and_lock(0x28);blocked_call_stop_and_lock(0x6B);blocked_call_stop_and_lock(0x36);
    std::cout<<"actual C6 runtime/adapter sources: two owners, cold restart, blocked I2C STOP/status and PM handoff passed\n";
}
