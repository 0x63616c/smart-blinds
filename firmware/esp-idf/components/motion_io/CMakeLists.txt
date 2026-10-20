idf_component_register(SRCS "bench_c6_io.cpp"
    INCLUDE_DIRS "include" "../../../include"
    REQUIRES blinds_control esp_driver_gpio esp_driver_pcnt esp_driver_mcpwm esp_adc esp_pm esp_timer)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
