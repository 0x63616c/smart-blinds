#pragma once
#include <cstdint>
using gpio_num_t=int;
constexpr int GPIO_INTR_ANYEDGE=0,GPIO_INTR_LOW_LEVEL=1,GPIO_INTR_NEGEDGE=2;
int gpio_get_level(gpio_num_t);
int gpio_install_isr_service(int);
int gpio_set_intr_type(gpio_num_t,int);
int gpio_isr_handler_add(gpio_num_t,void(*)(void*),void*);
int gpio_wakeup_enable(gpio_num_t,int);

constexpr int GPIO_MODE_INPUT=1,GPIO_INTR_DISABLE=0,GPIO_PULLUP_DISABLE=0,GPIO_PULLDOWN_DISABLE=0;
struct gpio_config_t { std::uint64_t pin_bit_mask=0;int mode=0,intr_type=0,pull_up_en=0,pull_down_en=0; };
int gpio_config(const gpio_config_t*);
