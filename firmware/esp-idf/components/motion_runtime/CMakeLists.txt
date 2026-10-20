idf_component_register(SRCS "c6_motion_runtime.cpp"
    INCLUDE_DIRS "include" "../../../include"
    REQUIRES blinds_control motion_io gauge_continuity charger_config esp_driver_i2c esp_driver_gpio esp_timer esp_pm freertos)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
