cmake_minimum_required(VERSION 3.8)
project(barcode_scanner)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ---------- dependencies ----------
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)

# ZXing-C++ — optional; build decodes only when present
find_package(ZXing QUIET)
if(ZXing_FOUND)
  if(TARGET ZXing::ZXing)
    set(ZXING_LIB ZXing::ZXing)
  elseif(TARGET ZXing::Core)
    set(ZXING_LIB ZXing::Core)
  endif()
  message(STATUS "ZXing found — barcode decoding ENABLED")
else()
  message(STATUS "ZXing NOT found — barcode decoding DISABLED (stub mode)")
endif()

# ---------- C++ barcode_scanner_node ----------
add_executable(barcode_scanner_node
  src/barcode_scanner_node.cpp
)

target_include_directories(barcode_scanner_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

target_compile_features(barcode_scanner_node PUBLIC cxx_std_17)

ament_target_dependencies(barcode_scanner_node
  rclcpp
  sensor_msgs
  std_msgs
  cv_bridge
  OpenCV
)

if(ZXing_FOUND AND ZXING_LIB)
  target_compile_definitions(barcode_scanner_node PRIVATE HAS_ZXING)
  target_link_libraries(barcode_scanner_node ${ZXING_LIB})
endif()

# ---------- Python package (slot_kpi etc.) ----------
ament_python_install_package(${PROJECT_NAME})

# ---------- install ----------
install(TARGETS barcode_scanner_node
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS scripts/scan_policy_fsm.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# ---------- tests ----------
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
