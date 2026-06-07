idf_component_register(
    SRCS "bno08x.c"
         "sh2/sh2.c"
         "sh2/sh2_SensorValue.c"
         "sh2/sh2_util.c"
         "sh2/shtp.c"
    INCLUDE_DIRS "include" "sh2"
    REQUIRES driver esp_timer
)
