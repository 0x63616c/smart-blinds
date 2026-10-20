#pragma once
#include <cstdint>
#include <mutex>
using BaseType_t=int;
using TickType_t=std::uint32_t;
constexpr int pdPASS=1,pdTRUE=1,pdFALSE=0;
constexpr TickType_t portMAX_DELAY=UINT32_MAX;
#define pdMS_TO_TICKS(x) (x)
using portMUX_TYPE=std::mutex;
#define portMUX_INITIALIZER_UNLOCKED {}
#define portENTER_CRITICAL(p) (p)->lock()
#define portEXIT_CRITICAL(p) (p)->unlock()
#define portYIELD_FROM_ISR() ((void)0)
