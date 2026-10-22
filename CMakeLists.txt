cmake_minimum_required(VERSION 3.16)
project(AMORPH LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

option(AMORPH_STATIC_LINK "Link the executable statically (mingw/Windows)" ON)

# ------------------------------------------------------------------ yaml-cpp
# Only used for reading config.yaml. Vendored under external/yaml-cpp (MIT
# licence, see external/yaml-cpp/LICENSE), so the build needs no network
# access. Tag yaml-cpp-0.9.0 (commit 56e3bb55), without its tests and tools.
set(YAML_CPP_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(YAML_CPP_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(YAML_CPP_INSTALL OFF CACHE BOOL "" FORCE)
set(YAML_BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
add_subdirectory(external/yaml-cpp EXCLUDE_FROM_ALL)

# -------------------------------------------------------------------- DNest4
# The nested sampling engine. Vendored under external/DNest4 (MIT licence,
# see external/DNest4/LICENSE). Pinned to upstream commit 40366c01.
set(DNEST4_DIR ${CMAKE_CURRENT_SOURCE_DIR}/external/DNest4)
if(NOT EXISTS ${DNEST4_DIR}/code/DNest4.h)
    message(FATAL_ERROR "DNest4 sources are missing from ${DNEST4_DIR}")
endif()

file(GLOB DNEST4_SOURCES CONFIGURE_DEPENDS
    ${DNEST4_DIR}/code/*.cpp
    ${DNEST4_DIR}/code/Distributions/*.cpp
    ${DNEST4_DIR}/code/RJObject/ConditionalPriors/*.cpp
)

add_library(dnest4 STATIC ${DNEST4_SOURCES})
# AMORPH includes "DNest4/code/DNest4.h", so the include directory is the
# parent of the DNest4 directory.
target_include_directories(dnest4 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/external)
target_compile_definitions(dnest4 PUBLIC NDEBUG)

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(dnest4 PUBLIC Threads::Threads)

# --------------------------------------------------------------------- AMORPH
file(GLOB AMORPH_SOURCES CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp)

add_executable(AMORPH ${AMORPH_SOURCES})
target_include_directories(AMORPH PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_link_libraries(AMORPH PRIVATE dnest4 yaml-cpp)

if(WIN32 AND AMORPH_STATIC_LINK)
    target_link_options(AMORPH PRIVATE -static)
endif()

install(TARGETS AMORPH RUNTIME DESTINATION bin)
