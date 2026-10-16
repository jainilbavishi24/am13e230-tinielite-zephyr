# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(am13e230_tinielite_demo)

target_sources(app PRIVATE
  src/main.c
  src/app_clock.c
  src/app_npu.c
  src/app_uart.c
)

set(MODEL_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../models/waveform_classifier")
target_include_directories(app SYSTEM PRIVATE "${MODEL_DIR}/artifacts")
target_link_libraries(app PRIVATE "${MODEL_DIR}/artifacts/mod.a")
target_link_options(zephyr_interface INTERFACE "-Wl,-u,tvmgen_default_run")
