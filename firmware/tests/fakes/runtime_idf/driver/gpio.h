#pragma once
using gpio_num_t=int;
constexpr int GPIO_INTR_ANYEDGE=0,GPIO_INTR_LOW_LEVEL=1;
int gpio_get_level(gpio_num_t);
int gpio_install_isr_service(int);
int gpio_set_intr_type(gpio_num_t,int);
int gpio_isr_handler_add(gpio_num_t,void(*)(void*),void*);
int gpio_wakeup_enable(gpio_num_t,int);
