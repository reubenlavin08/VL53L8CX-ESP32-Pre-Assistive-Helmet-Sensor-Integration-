idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_netif esp_event nvs_flash lwip
             app_update esp_http_server esp_driver_ledc esp_timer bno08x
)
