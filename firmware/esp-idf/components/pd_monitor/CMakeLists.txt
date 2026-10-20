idf_component_register(SRCS "c6_pd_monitor.cpp" "../../../src/pd_monitor.cpp"
    INCLUDE_DIRS "include" "../../../include"
    REQUIRES esp_driver_i2c esp_timer freertos)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
set_source_files_properties("${CMAKE_CURRENT_LIST_DIR}/../../../src/pd_monitor.cpp"
    PROPERTIES COMPILE_OPTIONS "-Wpedantic")
