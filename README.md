# UR3e ROS 2 API

This package exposes the existing `robot.py` `Robot` class through ROS 2 services and publishes TCP telemetry.

## Parameters

- `robot_ip` (`string`, default `192.168.0.10`): UR controller IP.
- `auto_connect` (`bool`, default `false`): call `connect` when the node starts.
- `refresh_rate` (`double`, default `1.0`): telemetry publish rate in Hz. It can be changed at runtime.

## Topics

- `tcp_pose` (`std_msgs/msg/Float64MultiArray`): `Robot.get_pos()` every `1 / refresh_rate` seconds.
- `tcp_force` (`std_msgs/msg/Float64MultiArray`): `Robot.get_fuerzas()` every `1 / refresh_rate` seconds.

## Services

Trigger services:

- `connect`
- `reconnect`
- `check_connection`
- `is_steady`
- `stop`
- `speed_stop`
- `end_servocontrol`
- `freedrive_on`
- `freedrive_off`

Vector getter services using `ur3e_api/srv/GetVector`:

- `get_pos`
- `get_joints`
- `get_pos_init`
- `get_pos_ref`
- `get_force`
- `get_fuerzas`

Command services:

- `a_move` (`ur3e_api/srv/MovePose`): `pose`, `speed`, `acceleration`
- `joint_move` (`ur3e_api/srv/MoveJoints`): `joints`, `speed`, `acceleration`
- `a_speed` (`ur3e_api/srv/SpeedCommand`): `vector`, `speed`, `acceleration`, `duration`
- `servocontrol` (`ur3e_api/srv/Servo`): `coordinates`
- `servocontrol_joint` (`ur3e_api/srv/Servo`): `coordinates`
- `get_aprox` (`ur3e_api/srv/GetAprox`): `pose`

All motion vectors are validated as six `float64` values before calling `robot.py`.

## Usage

Build from a sourced ROS 2 workspace:

```bash
colcon build --symlink-install
source install/setup.bash
```

The driver also needs the Python RTDE modules used by `robot.py` (`rtde_control` and `rtde_receive`) available in the same environment:

```bash
python3 -m pip install ur_rtde
```

Run the node:

```bash
ros2 run ur3e_api ur3e_api_node --ros-args -p robot_ip:=192.168.0.10 -p refresh_rate:=1.0
```

Change telemetry rate at runtime:

```bash
ros2 param set /ur3e_api refresh_rate 5.0
```

Example service call:

```bash
ros2 service call /a_move ur3e_api/srv/MovePose "{pose: [-0.192, -0.18212, 0.17233, 2.889, -1.211, 0.051], speed: 20.0, acceleration: 20.0}"
```
