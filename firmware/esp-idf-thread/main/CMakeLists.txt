idf_component_register(SRCS "main.cpp"
    INCLUDE_DIRS "." "../../include"
    REQUIRES esp_event esp_netif openthread nvs_flash esp_pm esp_timer mbedtls bootloader_support)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
