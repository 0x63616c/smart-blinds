#pragma once
struct MockTask;
using TaskHandle_t=MockTask*;
TaskHandle_t xTaskGetCurrentTaskHandle();
