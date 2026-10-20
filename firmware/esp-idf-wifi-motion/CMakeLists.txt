cmake_minimum_required(VERSION 3.20)
set(SB_COAP_DIR "" CACHE PATH "Verified pinned vendor coap component directory")
if(NOT EXISTS "${SB_COAP_DIR}/libcoap/CMakeLists.txt")
  message(FATAL_ERROR "Run fetch_dependencies.sh and set SB_COAP_DIR; no implicit download")
endif()
# CI fetches as the runner user and builds inside the root-owned IDF container.
# Trust only these explicitly selected dependency worktrees, for each Git
# invocation; do not modify global safe.directory or permit arbitrary paths.
get_filename_component(SB_VENDOR_ROOT "${SB_COAP_DIR}/.." REALPATH)
get_filename_component(SB_LIBCOAP_ROOT "${SB_COAP_DIR}/libcoap" REALPATH)
set(SB_VERIFY_GIT git -c "safe.directory=${SB_VENDOR_ROOT}" -c "safe.directory=${SB_LIBCOAP_ROOT}")
execute_process(COMMAND ${SB_VERIFY_GIT} rev-parse HEAD WORKING_DIRECTORY "${SB_COAP_DIR}"
  OUTPUT_VARIABLE VENDOR_REV OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${SB_VERIFY_GIT} rev-parse HEAD WORKING_DIRECTORY "${SB_COAP_DIR}/libcoap"
  OUTPUT_VARIABLE COAP_REV OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
if(NOT VENDOR_REV STREQUAL "cad43839020fc329722035a35640a54e06fee09b" OR
   NOT COAP_REV STREQUAL "d9b4031ee61df1a40ecec46fe3817a1f985b3919")
  message(FATAL_ERROR "Unreviewed vendor/libcoap source revision")
endif()
foreach(SOURCE_DIR "${SB_COAP_DIR}" "${SB_COAP_DIR}/libcoap")
  execute_process(COMMAND ${SB_VERIFY_GIT} diff --quiet HEAD -- . WORKING_DIRECTORY "${SOURCE_DIR}" RESULT_VARIABLE DIRTY)
  if(NOT DIRTY EQUAL 0)
    message(FATAL_ERROR "Pinned dependency has tracked changes: ${SOURCE_DIR}")
  endif()
endforeach()
set(EXTRA_COMPONENT_DIRS "${SB_COAP_DIR}" "../esp-idf/components")
set(COMPONENTS main)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(smart_blinds_wifi_motion_unqualified)
