#pragma once
#include "freertos/FreeRTOS.h"
#include <cstddef>
struct MockQueue;
using QueueHandle_t=MockQueue*;
QueueHandle_t xQueueCreate(unsigned,std::size_t);
BaseType_t xQueueOverwrite(QueueHandle_t,const void*);
BaseType_t xQueuePeek(QueueHandle_t,void*,TickType_t);
BaseType_t xQueueReceive(QueueHandle_t,void*,TickType_t);
BaseType_t xQueueSend(QueueHandle_t,const void*,TickType_t);
