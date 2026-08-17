cmake_minimum_required(VERSION 3.16)

# Reuse the helmet project's already-downloaded VL53L8CX driver instead of
# pulling it again — this project builds with no network access.
set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../managed_components")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(tof_pin_test)
