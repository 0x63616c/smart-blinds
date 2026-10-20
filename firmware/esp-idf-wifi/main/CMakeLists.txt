idf_component_register(SRCS "main.cpp"
    INCLUDE_DIRS "." "../../include"
    REQUIRES coap esp_wifi esp_event esp_netif nvs_flash esp_pm esp_timer
             esp_driver_gpio esp_hw_support bootloader_support mbedtls vfs spi_flash gauge_continuity)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
