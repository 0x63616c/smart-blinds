#pragma once
#include "freertos/FreeRTOS.h"
struct MockTask;
using TaskHandle_t=MockTask*;
TaskHandle_t xTaskGetCurrentTaskHandle();
BaseType_t xTaskCreate(void(*)(void*),const char*,unsigned,void*,unsigned,TaskHandle_t*);
void xTaskNotifyGive(TaskHandle_t);
void vTaskNotifyGiveFromISR(TaskHandle_t,BaseType_t*);
std::uint32_t ulTaskNotifyTake(BaseType_t,TickType_t);
void vTaskDelay(TickType_t);
