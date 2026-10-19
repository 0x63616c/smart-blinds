idf_component_register(SRCS "max17320_reader.cpp" INCLUDE_DIRS "include"
                       REQUIRES esp_driver_i2c esp_timer)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
