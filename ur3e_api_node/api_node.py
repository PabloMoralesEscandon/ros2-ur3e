from __future__ import annotations

from threading import Lock
from typing import Callable, Iterable, Sequence

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from std_srvs.srv import Trigger

from robot import Robot
from ur3e_api.srv import (
    GetAprox,
    GetVector,
    MoveJoints,
    MoveOffset,
    MovePose,
    Servo,
    SpeedCommand,
)


Vector = Sequence[float]


class UR3eApiNode(Node):
    """Expose the Robot class as ROS 2 services and telemetry topics."""

    def __init__(self) -> None:
        super().__init__("ur3e_api")

        self.declare_parameter("robot_ip", "192.168.0.10")
        self.declare_parameter("auto_connect", False)
        self.declare_parameter("refresh_rate", 1.0)

        self._robot = Robot(self.get_parameter("robot_ip").value)
        self._lock = Lock()

        self._pose_pub = self.create_publisher(Float64MultiArray, "tcp_pose", 10)
        self._force_pub = self.create_publisher(Float64MultiArray, "tcp_force", 10)

        self._create_services()

        self._timer = None
        self._set_refresh_timer(float(self.get_parameter("refresh_rate").value))
        self.add_on_set_parameters_callback(self._on_parameters_changed)

        if bool(self.get_parameter("auto_connect").value):
            ok, message = self._call_robot(self._robot.connect)
            if ok:
                self.get_logger().info("Connected to robot during startup")
            else:
                self.get_logger().error(f"Startup robot connection failed: {message}")

    def _create_services(self) -> None:
        self.create_service(Trigger, "connect", self._handle_connect)
        self.create_service(Trigger, "reconnect", self._handle_reconnect)
        self.create_service(Trigger, "check_connection", self._handle_check_connection)
        self.create_service(Trigger, "is_steady", self._handle_is_steady)
        self.create_service(Trigger, "stop", self._handle_stop)
        self.create_service(Trigger, "speed_stop", self._handle_speed_stop)
        self.create_service(Trigger, "end_servocontrol", self._handle_end_servocontrol)
        self.create_service(Trigger, "freedrive_on", self._handle_freedrive_on)
        self.create_service(Trigger, "freedrive_off", self._handle_freedrive_off)

        self.create_service(GetVector, "get_pos", self._handle_get_pos)
        self.create_service(GetVector, "get_joints", self._handle_get_joints)
        self.create_service(GetVector, "get_pos_init", self._handle_get_pos_init)
        self.create_service(GetVector, "get_pos_ref", self._handle_get_pos_ref)
        self.create_service(GetVector, "get_force", self._handle_get_force)
        self.create_service(GetVector, "get_fuerzas", self._handle_get_force)

        self.create_service(MovePose, "a_move", self._handle_a_move)
        self.create_service(MoveOffset, "offset_move", self._handle_offset_move)
        self.create_service(MoveJoints, "joint_move", self._handle_joint_move)
        self.create_service(SpeedCommand, "a_speed", self._handle_a_speed)
        self.create_service(Servo, "servocontrol", self._handle_servocontrol)
        self.create_service(Servo, "servocontrol_joint", self._handle_servocontrol_joint)
        self.create_service(GetAprox, "get_aprox", self._handle_get_aprox)

    def _on_parameters_changed(self, params):
        from rcl_interfaces.msg import SetParametersResult

        new_refresh_rate = None
        new_robot_ip = None

        for param in params:
            if param.name == "refresh_rate":
                try:
                    new_refresh_rate = float(param.value)
                    if new_refresh_rate <= 0:
                        raise ValueError("refresh_rate must be greater than 0 Hz")
                except ValueError as exc:
                    return SetParametersResult(successful=False, reason=str(exc))
            elif param.name == "robot_ip":
                if self._is_connected():
                    return SetParametersResult(
                        successful=False,
                        reason="robot_ip cannot be changed while connected; disconnect externally or restart the node",
                    )
                new_robot_ip = str(param.value)

        if new_robot_ip is not None:
            with self._lock:
                self._robot = Robot(new_robot_ip)
        if new_refresh_rate is not None:
            self._set_refresh_timer(new_refresh_rate)

        return SetParametersResult(successful=True)

    def _set_refresh_timer(self, refresh_rate: float) -> None:
        if refresh_rate <= 0:
            raise ValueError("refresh_rate must be greater than 0 Hz")

        if self._timer is not None:
            self.destroy_timer(self._timer)

        period = 1.0 / refresh_rate
        self._timer = self.create_timer(period, self._publish_telemetry)
        self.get_logger().info(f"Telemetry refresh rate set to {refresh_rate:g} Hz")

    def _publish_telemetry(self) -> None:
        if not self._is_connected():
            return

        pose_ok, pose = self._read_robot_vector(self._robot.get_pos)
        if pose_ok:
            self._pose_pub.publish(Float64MultiArray(data=pose))

        force_ok, force = self._read_robot_vector(self._robot.get_fuerzas)
        if force_ok:
            self._force_pub.publish(Float64MultiArray(data=force))

    def _is_connected(self) -> bool:
        try:
            with self._lock:
                return bool(self._robot.check_connection())
        except Exception:
            return False

    def _call_robot(self, callback: Callable, *args):
        try:
            with self._lock:
                value = callback(*args)
            return True, value
        except Exception as exc:
            self.get_logger().error(f"Robot command failed: {exc}")
            return False, str(exc)

    def _read_robot_vector(self, callback: Callable[[], Iterable[float]]):
        ok, value = self._call_robot(callback)
        if not ok:
            return False, value
        return True, [float(item) for item in value]

    @staticmethod
    def _validate_vector(values: Vector, name: str, expected_len: int = 6) -> list[float]:
        result = [float(item) for item in values]
        if len(result) != expected_len:
            raise ValueError(f"{name} must contain exactly {expected_len} values")
        return result

    @staticmethod
    def _validate_offset(values: Vector) -> list[float]:
        result = [float(item) for item in values]
        if len(result) not in (3, 6):
            raise ValueError("offset must contain exactly 3 or 6 values")
        return result

    @staticmethod
    def _trigger_result(response: Trigger.Response, ok: bool, message: str = "ok"):
        response.success = ok
        response.message = message
        return response

    def _handle_connect(self, request, response):
        ok, message = self._call_robot(self._robot.connect)
        return self._trigger_result(response, ok, "connected" if ok else str(message))

    def _handle_reconnect(self, request, response):
        ok, message = self._call_robot(self._robot.reconnect)
        return self._trigger_result(response, ok, "reconnected" if ok else str(message))

    def _handle_check_connection(self, request, response):
        connected = self._is_connected()
        return self._trigger_result(response, connected, "connected" if connected else "not connected")

    def _handle_is_steady(self, request, response):
        ok, value = self._call_robot(self._robot.is_steady)
        if not ok:
            return self._trigger_result(response, False, str(value))
        return self._trigger_result(response, bool(value), "steady" if value else "moving")

    def _handle_stop(self, request, response):
        ok, message = self._call_robot(self._robot.stop)
        return self._trigger_result(response, ok, "stopped" if ok else str(message))

    def _handle_speed_stop(self, request, response):
        ok, message = self._call_robot(self._robot.speed_stop)
        return self._trigger_result(response, ok, "speed stopped" if ok else str(message))

    def _handle_end_servocontrol(self, request, response):
        ok, message = self._call_robot(self._robot.end_servocontrol)
        return self._trigger_result(response, ok, "servo stopped" if ok else str(message))

    def _handle_freedrive_on(self, request, response):
        ok, message = self._call_robot(self._robot.freedrive_on)
        return self._trigger_result(response, ok, "freedrive enabled" if ok else str(message))

    def _handle_freedrive_off(self, request, response):
        ok, message = self._call_robot(self._robot.freedrive_off)
        return self._trigger_result(response, ok, "freedrive disabled" if ok else str(message))

    def _fill_vector_response(self, response, ok: bool, values: Iterable[float] | str):
        response.success = ok
        if ok:
            response.values = [float(item) for item in values]
            response.message = "ok"
        else:
            response.values = []
            response.message = str(values)
        return response

    def _handle_get_pos(self, request, response):
        ok, value = self._read_robot_vector(self._robot.get_pos)
        return self._fill_vector_response(response, ok, value)

    def _handle_get_joints(self, request, response):
        ok, value = self._read_robot_vector(self._robot.get_joints)
        return self._fill_vector_response(response, ok, value)

    def _handle_get_pos_init(self, request, response):
        ok, value = self._read_robot_vector(self._robot.get_pos_init)
        return self._fill_vector_response(response, ok, value)

    def _handle_get_pos_ref(self, request, response):
        ok, value = self._read_robot_vector(self._robot.get_pos_ref)
        return self._fill_vector_response(response, ok, value)

    def _handle_get_force(self, request, response):
        ok, value = self._read_robot_vector(self._robot.get_fuerzas)
        return self._fill_vector_response(response, ok, value)

    def _handle_a_move(self, request, response):
        try:
            pose = self._validate_vector(request.pose, "pose")
            return self._command_response(
                response,
                self._robot.a_move,
                pose,
                float(request.speed),
                float(request.acceleration),
            )
        except Exception as exc:
            return self._error_response(response, exc)

    def _handle_joint_move(self, request, response):
        try:
            joints = self._validate_vector(request.joints, "joints")
            return self._command_response(
                response,
                self._robot.joint_move,
                joints,
                float(request.speed),
                float(request.acceleration),
            )
        except Exception as exc:
            return self._error_response(response, exc)

    def _handle_offset_move(self, request, response):
        try:
            offset = self._validate_offset(request.offset)
            ok, value = self._call_robot(
                self._robot.offset_move,
                offset,
                float(request.speed),
                float(request.acceleration),
            )
            response.success = ok
            response.message = "ok" if ok else str(value)
            response.target_pose = [float(item) for item in value] if ok else []
        except Exception as exc:
            response.success = False
            response.message = str(exc)
            response.target_pose = []
        return response

    def _handle_a_speed(self, request, response):
        try:
            vector = self._validate_vector(request.vector, "vector")
            return self._command_response(
                response,
                self._robot.a_speed,
                vector,
                float(request.speed),
                float(request.acceleration),
                float(request.duration),
            )
        except Exception as exc:
            return self._error_response(response, exc)

    def _handle_servocontrol(self, request, response):
        try:
            coordinates = self._validate_vector(request.coordinates, "coordinates")
            return self._command_response(response, self._robot.servocontrol, coordinates)
        except Exception as exc:
            return self._error_response(response, exc)

    def _handle_servocontrol_joint(self, request, response):
        try:
            coordinates = self._validate_vector(request.coordinates, "coordinates")
            return self._command_response(response, self._robot.servocontrol_joint, coordinates)
        except Exception as exc:
            return self._error_response(response, exc)

    def _handle_get_aprox(self, request, response):
        try:
            pose = self._validate_vector(request.pose, "pose")
            ok, value = self._call_robot(self._robot.get_aprox, pose)
            response.success = ok
            response.pose = [float(item) for item in value] if ok else []
            response.message = "ok" if ok else str(value)
        except Exception as exc:
            response.success = False
            response.pose = []
            response.message = str(exc)
        return response

    def _command_response(self, response, callback: Callable, *args):
        try:
            ok, message = self._call_robot(callback, *args)
            response.success = ok
            response.message = "ok" if ok else str(message)
        except Exception as exc:
            return self._error_response(response, exc)
        return response

    @staticmethod
    def _error_response(response, exc: Exception):
        response.success = False
        response.message = str(exc)
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = UR3eApiNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
