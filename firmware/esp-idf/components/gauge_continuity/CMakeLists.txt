idf_component_register(SRCS "c6_gauge_continuity.cpp" "../../../src/gauge_continuity.cpp"
    "../../../src/gauge_bus_session.cpp"
    INCLUDE_DIRS "include" "../../../include"
    REQUIRES esp_driver_i2c esp_timer freertos)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
