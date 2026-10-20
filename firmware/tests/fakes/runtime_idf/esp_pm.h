#pragma once
struct MockPm;
using esp_pm_lock_handle_t=MockPm*;
constexpr int ESP_PM_NO_LIGHT_SLEEP=1,ESP_PM_CPU_FREQ_MAX=2;
int esp_pm_lock_create(int,int,const char*,esp_pm_lock_handle_t*);
int esp_pm_lock_acquire(esp_pm_lock_handle_t);
int esp_pm_lock_release(esp_pm_lock_handle_t);
