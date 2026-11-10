# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(am13e230_tinielite_demo)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

target_sources(app PRIVATE
  src/main.c
  src/app_aeabi_compat.c
  src/app_clock.c
  src/app_npu.c
  src/app_protocol.c
  src/app_uart.c
  src/app_watchdog.c
)

set(APP_MODEL "waveform_classifier" CACHE STRING "Model package under models/")
if(NOT APP_MODEL MATCHES "^[A-Za-z0-9_]+$")
  message(FATAL_ERROR "APP_MODEL must contain only letters, digits, and underscores")
endif()

set(MODEL_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../models/${APP_MODEL}")
set(MODEL_MANIFEST "${MODEL_DIR}/model.json")
if(NOT EXISTS "${MODEL_MANIFEST}")
  message(FATAL_ERROR "Model package manifest not found: ${MODEL_MANIFEST}")
endif()

execute_process(
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/../tools/model_package.py"
          "${MODEL_DIR}"
  RESULT_VARIABLE APP_MODEL_VALIDATION_RESULT
  OUTPUT_VARIABLE APP_MODEL_VALIDATION_OUTPUT
  ERROR_VARIABLE APP_MODEL_VALIDATION_ERROR
)
if(NOT APP_MODEL_VALIDATION_RESULT EQUAL 0)
  message(FATAL_ERROR
    "Invalid model package ${APP_MODEL}:\n${APP_MODEL_VALIDATION_OUTPUT}${APP_MODEL_VALIDATION_ERROR}")
endif()

file(READ "${MODEL_MANIFEST}" APP_MODEL_JSON)
string(JSON APP_MODEL_SCHEMA GET "${APP_MODEL_JSON}" schema_version)
if(NOT APP_MODEL_SCHEMA EQUAL 1)
  message(FATAL_ERROR "Unsupported model package schema: ${APP_MODEL_SCHEMA}")
endif()

string(JSON APP_MODEL_NAME GET "${APP_MODEL_JSON}" name)
string(JSON APP_MODEL_ID GET "${APP_MODEL_JSON}" model_id)
string(JSON APP_MODEL_INPUT_SIZE_BYTES GET "${APP_MODEL_JSON}" input size_bytes)
string(JSON APP_MODEL_OUTPUT_SIZE_BYTES GET "${APP_MODEL_JSON}" output size_bytes)
string(JSON APP_MODEL_INPUT_DTYPE GET "${APP_MODEL_JSON}" input dtype)
string(JSON APP_MODEL_OUTPUT_DTYPE GET "${APP_MODEL_JSON}" output dtype)
string(JSON APP_MODEL_IO_ALIGNMENT GET "${APP_MODEL_JSON}" io_alignment)
string(JSON APP_MODEL_LIBRARY_REL GET "${APP_MODEL_JSON}" artifacts library)
string(JSON APP_MODEL_HEADER_REL GET "${APP_MODEL_JSON}" artifacts header)
string(JSON APP_MODEL_ENTRY_SYMBOL GET "${APP_MODEL_JSON}" artifacts entry_symbol)
string(JSON APP_MODEL_REQUIRES_NPU GET "${APP_MODEL_JSON}" target requires_npu)

if(NOT APP_MODEL_NAME STREQUAL APP_MODEL)
  message(FATAL_ERROR
    "Model package directory '${APP_MODEL}' does not match manifest name '${APP_MODEL_NAME}'")
endif()

function(model_dtype_code output_variable dtype)
  if(dtype STREQUAL "int8")
    set(code 1)
  elseif(dtype STREQUAL "uint8")
    set(code 2)
  elseif(dtype STREQUAL "int16")
    set(code 3)
  elseif(dtype STREQUAL "float32")
    set(code 4)
  else()
    message(FATAL_ERROR "Unsupported model dtype: ${dtype}")
  endif()
  set(${output_variable} ${code} PARENT_SCOPE)
endfunction()

model_dtype_code(APP_MODEL_INPUT_DTYPE_CODE "${APP_MODEL_INPUT_DTYPE}")
model_dtype_code(APP_MODEL_OUTPUT_DTYPE_CODE "${APP_MODEL_OUTPUT_DTYPE}")
if(APP_MODEL_REQUIRES_NPU)
  set(APP_MODEL_CAPABILITY_FLAGS 1)
else()
  message(FATAL_ERROR "The current inference engine requires a TINIElite NPU model")
endif()

foreach(required_path
    "${MODEL_DIR}/${APP_MODEL_LIBRARY_REL}"
    "${MODEL_DIR}/${APP_MODEL_HEADER_REL}")
  if(NOT EXISTS "${required_path}")
    message(FATAL_ERROR "Model package file not found: ${required_path}")
  endif()
endforeach()

configure_file(
  src/app_model_config.h.in
  ${CMAKE_CURRENT_BINARY_DIR}/generated/app_model_config.h
  @ONLY
)

set(APP_MODEL_ADAPTER "${CMAKE_CURRENT_BINARY_DIR}/generated/model_adapter.c")
execute_process(
  COMMAND "${Python3_EXECUTABLE}"
          "${CMAKE_CURRENT_SOURCE_DIR}/../tools/generate_model_adapter.py"
          "${MODEL_DIR}" "${APP_MODEL_ADAPTER}"
  RESULT_VARIABLE APP_MODEL_GENERATION_RESULT
  OUTPUT_VARIABLE APP_MODEL_GENERATION_OUTPUT
  ERROR_VARIABLE APP_MODEL_GENERATION_ERROR
)
if(NOT APP_MODEL_GENERATION_RESULT EQUAL 0)
  message(FATAL_ERROR
    "Could not generate adapter for ${APP_MODEL}:\n"
    "${APP_MODEL_GENERATION_OUTPUT}${APP_MODEL_GENERATION_ERROR}")
endif()
set_source_files_properties("${APP_MODEL_ADAPTER}" PROPERTIES GENERATED TRUE)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${MODEL_MANIFEST}"
  "${MODEL_DIR}/${APP_MODEL_HEADER_REL}"
  "${CMAKE_CURRENT_SOURCE_DIR}/../tools/model_package.py"
  "${CMAKE_CURRENT_SOURCE_DIR}/../tools/generate_model_adapter.py"
)

get_filename_component(APP_MODEL_HEADER_DIR "${MODEL_DIR}/${APP_MODEL_HEADER_REL}" DIRECTORY)
target_sources(app PRIVATE "${APP_MODEL_ADAPTER}")
target_include_directories(app PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/src"
  "${CMAKE_CURRENT_BINARY_DIR}/generated"
)
target_include_directories(app SYSTEM PRIVATE "${APP_MODEL_HEADER_DIR}")
target_link_libraries(app PRIVATE "${MODEL_DIR}/${APP_MODEL_LIBRARY_REL}")
target_link_options(zephyr_interface INTERFACE "-Wl,-u,${APP_MODEL_ENTRY_SYMBOL}")

message(STATUS
  "Selected model ${APP_MODEL_NAME}: input=${APP_MODEL_INPUT_SIZE_BYTES}B/${APP_MODEL_INPUT_DTYPE}, "
  "output=${APP_MODEL_OUTPUT_SIZE_BYTES}B/${APP_MODEL_OUTPUT_DTYPE}")
message(STATUS "Generated model adapter: ${APP_MODEL_ADAPTER}")
