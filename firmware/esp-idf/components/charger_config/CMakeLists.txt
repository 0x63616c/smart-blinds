idf_component_register(SRCS "bq25798_config.cpp" "../../../src/charger.cpp"
    INCLUDE_DIRS "include" "../../../include"
    REQUIRES esp_driver_i2c esp_timer freertos)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)

# IDF RISC-V headers require GNU statement expressions. Keep ISO checks on the
# portable core; the SDK adapter retains all ordinary warnings as errors.
set_source_files_properties("${CMAKE_CURRENT_LIST_DIR}/../../../src/charger.cpp"
    PROPERTIES COMPILE_OPTIONS "-Wpedantic")
