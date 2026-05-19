cmake_minimum_required(VERSION 3.10)
project(ur3e_api)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rcl_interfaces REQUIRED)
find_package(rclpy REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/GetAprox.srv"
  "srv/GetVector.srv"
  "srv/MoveJoints.srv"
  "srv/MoveOffset.srv"
  "srv/MovePose.srv"
  "srv/Servo.srv"
  "srv/SpeedCommand.srv"
)

ament_python_install_package(ur3e_api_node)

install(PROGRAMS
  scripts/ur3e_api_node
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES
  robot.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
