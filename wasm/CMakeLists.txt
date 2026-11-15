# Emscripten build of JSBSim (libJSBSim + our small embind binding).
# Configure with: emcmake cmake -S wasm -B build/<variant> -DJSBSIM_SOURCE_DIR=... -DFDM_EH=js|wasm
cmake_minimum_required(VERSION 3.20)
project(fdm_jsbsim_wasm LANGUAGES C CXX)

if(NOT JSBSIM_SOURCE_DIR)
  message(FATAL_ERROR "JSBSIM_SOURCE_DIR is required")
endif()
set(FDM_EH "js" CACHE STRING "Exception handling: js (-fexceptions) or wasm (-fwasm-exceptions)")
set(FDM_OUTPUT_NAME "jsbsim" CACHE STRING "Output base name")

if(FDM_EH STREQUAL "wasm")
  set(EH_FLAG "-fwasm-exceptions")
else()
  set(EH_FLAG "-fexceptions")
endif()

# Exception support on ALL code (JSBSim relies on its own try/catch while parsing aircraft files).
# Set before add_subdirectory so libJSBSim and the bundled expat get it too.
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${EH_FLAG}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${EH_FLAG}")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${EH_FLAG}")

set(BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(BUILD_PYTHON_MODULE OFF CACHE BOOL "" FORCE)
set(BUILD_JULIA_PACKAGE OFF CACHE BOOL "" FORCE)
set(BUILD_MATLAB_SFUNCTION OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(SYSTEM_EXPAT OFF CACHE BOOL "" FORCE)

add_subdirectory("${JSBSIM_SOURCE_DIR}" "${CMAKE_BINARY_DIR}/jsbsim" EXCLUDE_FROM_ALL)

add_executable(fdm_jsbsim "${CMAKE_CURRENT_LIST_DIR}/bindings.cpp")
set_target_properties(fdm_jsbsim PROPERTIES OUTPUT_NAME "${FDM_OUTPUT_NAME}" SUFFIX ".mjs")
target_compile_features(fdm_jsbsim PRIVATE cxx_std_17)
target_include_directories(fdm_jsbsim PRIVATE "${JSBSIM_SOURCE_DIR}/src" "${CMAKE_BINARY_DIR}/jsbsim/src")
target_link_libraries(fdm_jsbsim PRIVATE libJSBSim)
target_link_options(fdm_jsbsim PRIVATE
  -lembind
  -O3
  -sMODULARIZE=1
  -sEXPORT_ES6=1
  -sEXPORT_NAME=createJSBSim
  -sENVIRONMENT=web,worker,node
  -sFILESYSTEM=1
  -sFORCE_FILESYSTEM=1
  -sALLOW_MEMORY_GROWTH=1
  -sSTACK_SIZE=1MB
  "-sEXPORTED_RUNTIME_METHODS=['FS','HEAPF64']"
)
