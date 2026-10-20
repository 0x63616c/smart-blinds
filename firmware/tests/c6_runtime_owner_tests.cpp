#include "c6_motion_runtime.hpp"
#include "bench_c6_io.hpp"
#include "soc/gpio_struct.h"
#include "esp_pm.h"
#include "fakes/sensor_fixture.hpp"
#include <chrono>
#include <cstring>
#include <memory>
#include <string>
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
std::atomic<unsigned> fast_reads{0},stop_reads{0},actuations{0};std::atomic<bool> stop{false};
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
std::atomic<std::int64_t> offset{0};
std::chrono::steady_clock::time_point origin;
std::atomic<unsigned> transfers{0},adds{0},removes{0},held_locks{0},released_locks{0},missing_off_reads{0};
bool block=false,blocked=false,release_call=false,fail_call=false;
unsigned block_device=0;
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
    block=blocked=release_call=fail_call=false;block_device=0;
}
blinds::runtime::Configuration configuration() {
    blinds::runtime::Configuration c;
    c.task_timing_verified=c.bus_readback_verified=c.sensor_handoff_verified=true;c.verified_for_boot=99;
    c.port.bench_qualified=true;c.port.qualification_id=1;c.port.motor_sign=c.port.encoder_sign=1;
    c.motion.bench_qualified=c.motion.holding_qualified=true;c.motion.qualification_id=1;
    const blinds::Knot knots[]={{0,0},{1000,100}};c.calibration.assign(knots,2,7);
    c.gauge=sensor_fixture::profile();c.clock.validated=true;
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
    Fixture() {
        origin=std::chrono::steady_clock::now();offset=0;reset_bus();transfers=adds=removes=0;
        released_locks=0;missing_off_reads=0;runtime_fake::fast_reads=runtime_fake::stop_reads=runtime_fake::actuations=0;runtime_fake::stop=false;
        runtime=std::make_unique<blinds::c6::MotionRuntime>(99,configuration());
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
    std::lock_guard<std::mutex> guard(q->mutex);std::memcpy(q->body.data(),data,q->body.size());q->present=true;return pdPASS;
}
BaseType_t xQueuePeek(QueueHandle_t q,void* data,TickType_t wait) {
    check(wait==0,"runtime reader blocked on queue");std::lock_guard<std::mutex> guard(q->mutex);
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
int gpio_get_level(gpio_num_t pin) { return pin!=blinds::io::Pins::in1 && pin!=blinds::io::Pins::in2; }
int gpio_install_isr_service(int) { return 0; }
int gpio_set_intr_type(gpio_num_t,int) { return 0; }
int gpio_isr_handler_add(gpio_num_t,void(*)(void*),void*) { return 0; }
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
    if(d->address==0x6B) {
        check(*pointer+size<=registers.size(),"charger map overflow");std::copy_n(registers.data()+*pointer,size,output);
        for(unsigned i=0;i<size;++i) if(*pointer+i>=0x22 && *pointer+i<=0x27) registers[*pointer+i]=0;
    } else {
        check(size==2 && (d->address==0x36 || d->address==0x0B),"gauge read shape/address changed");
        const auto word=words[*pointer+(d->address==0x0B ? 0x100:0)];output[0]=word;output[1]=word>>8;
    }
    return ESP_OK;
}
int i2c_master_transmit(i2c_master_dev_handle_t d,const std::uint8_t* bytes,std::size_t size,int timeout) {
    check(current==d->owner && d->address==0x6B && size>=2 && size<=3 && timeout==10,"wrong write owner/shape");
    std::lock_guard<std::mutex> lock(bus_mutex);++transfers;
    check(!(bytes[0]==0x0F && (bytes[1]&0x20)),"charge enabled");
    std::copy_n(bytes+1,size-1,registers.data()+bytes[0]);if(bytes[0]==0x10) registers[0x10]&=~8;return ESP_OK;
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
    Fixture f;
    { std::lock_guard<std::mutex> lock(bus_mutex);block=true;block_device=address; }
    f.awake(true);
    { std::unique_lock<std::mutex> lock(bus_mutex);check(bus_cv.wait_for(lock,std::chrono::seconds(2),[]{return blocked;}),"SDK call did not block"); }
    const auto reads=runtime_fake::stop_reads.load(),releases=released_locks.load();
    runtime_fake::stop=true;f.runtime->local_stop_from_isr();f.awake(false);
    await([&]{return runtime_fake::stop_reads>reads;},"blocked sensor prevented raw STOP owner");
    check(held_locks==2 && released_locks==releases && !f.runtime->parked_off(esp_timer_get_time()),
          "control released PM/parked while synchronous I2C still blocked");
    char json[1500]{};check(f.runtime->status(json,sizeof(json),esp_timer_get_time()),"status blocked on sensor");
    // A deliberately over-budget call returns a real failure, not a new good
    // sample. Only returning owner may clean up; no timeout thread removes it.
    { std::lock_guard<std::mutex> lock(bus_mutex);fail_call=true;release_call=true;bus_cv.notify_all(); }
    await([&]{return !f.runtime->io_qualified();},"first bus failure did not revoke actual runtime");
    check(held_locks==2 && removes==0 && !f.power_ready(),"fault released PM or cross-task removed handles");
}
int main() {
    real_workers_wake_park_cold();blocked_call_stop_and_lock(0x6B);blocked_call_stop_and_lock(0x36);
    std::cout<<"actual C6 runtime/adapter sources: two owners, cold restart, blocked I2C STOP/status and PM handoff passed\n";
}
