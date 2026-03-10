#!/usr/bin/env python3
"""Enter OFFBOARD, arm, then climb via twist_mux safety channel."""

from __future__ import annotations

import argparse
import time

import rclpy
from geometry_msgs.msg import Twist
from px4_msgs.msg import VehicleCommand, VehicleLocalPosition, VehicleStatus
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy


class OffboardTakeoff(Node):
    """Coordinate a minimal PX4 takeoff without duplicating offboard heartbeats."""

    def __init__(
        self,
        target_alt_m: float,
        climb_speed_mps: float,
        settle_sec: float,
        command_period_sec: float,
        command_timeout_sec: float,
    ) -> None:
        super().__init__("offboard_takeoff_via_twist_mux")

        px4_qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
        )
        cmd_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
        )

        self._vehicle_command_pub = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", px4_qos
        )
        self._safety_cmd_pub = self.create_publisher(
            Twist, "/drone/safety/cmd_vel", cmd_qos
        )

        self.create_subscription(
            VehicleStatus, "/fmu/out/vehicle_status_v2", self._on_vehicle_status, px4_qos
        )
        self.create_subscription(
            VehicleLocalPosition,
            "/fmu/out/vehicle_local_position_v1",
            self._on_local_position,
            px4_qos,
        )

        self._target_alt_m = target_alt_m
        self._climb_speed_mps = climb_speed_mps
        self._settle_sec = settle_sec
        self._command_period_sec = command_period_sec
        self._command_timeout_sec = command_timeout_sec

        self._arming_state = 0
        self._nav_state = 0
        self._xy_valid = False
        self._z_valid = False
        self._v_xy_valid = False
        self._v_z_valid = False
        self._heading_good_for_control = False
        self._z_ned_m = 0.0
        self._status_seen = False
        self._local_position_seen = False

    def _on_vehicle_status(self, msg: VehicleStatus) -> None:
        self._status_seen = True
        self._arming_state = int(msg.arming_state)
        self._nav_state = int(msg.nav_state)

    def _on_local_position(self, msg: VehicleLocalPosition) -> None:
        self._local_position_seen = True
        self._xy_valid = bool(msg.xy_valid)
        self._z_valid = bool(msg.z_valid)
        self._v_xy_valid = bool(msg.v_xy_valid)
        self._v_z_valid = bool(msg.v_z_valid)
        self._heading_good_for_control = bool(msg.heading_good_for_control)
        self._z_ned_m = float(msg.z)

    def localization_ready(self) -> bool:
        return (
            self._local_position_seen
            and self._xy_valid
            and self._z_valid
            and self._v_xy_valid
            and self._v_z_valid
        )

    def current_altitude_m(self) -> float:
        return -self._z_ned_m

    def publish_safety_twist(self, vz_up_mps: float) -> None:
        msg = Twist()
        msg.linear.x = 0.0
        msg.linear.y = 0.0
        msg.linear.z = vz_up_mps
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = 0.0
        self._safety_cmd_pub.publish(msg)

    def send_vehicle_command(
        self,
        command: int,
        param1: float = 0.0,
        param2: float = 0.0,
    ) -> None:
        msg = VehicleCommand()
        msg.timestamp = self.get_clock().now().nanoseconds // 1000
        msg.command = command
        msg.param1 = param1
        msg.param2 = param2
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self._vehicle_command_pub.publish(msg)

    def spin_until(self, predicate, timeout_sec: float) -> bool:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.2)
            if predicate():
                return True
        return predicate()

    def run(self) -> int:
        self.get_logger().info("Waiting for PX4 status and local position...")
        if not self.spin_until(
            lambda: self._status_seen and self._local_position_seen,
            timeout_sec=self._command_timeout_sec,
        ):
            self.get_logger().error("PX4 status/local position did not appear in time.")
            return 1

        self.get_logger().info("Waiting for valid local position before motion...")
        if not self.spin_until(self.localization_ready, timeout_sec=self._command_timeout_sec):
            self.get_logger().error(
                "Localization not ready: "
                f"xy_valid={self._xy_valid} z_valid={self._z_valid} "
                f"v_xy_valid={self._v_xy_valid} v_z_valid={self._v_z_valid} "
                f"heading_good_for_control={self._heading_good_for_control}"
            )
            return 1

        self.get_logger().info(f"Localization valid. Settling for {self._settle_sec:.1f}s...")
        settle_deadline = time.monotonic() + self._settle_sec
        while time.monotonic() < settle_deadline:
            rclpy.spin_once(self, timeout_sec=0.2)

        self.get_logger().info("Requesting OFFBOARD mode...")
        mode_deadline = time.monotonic() + self._command_timeout_sec
        while time.monotonic() < mode_deadline:
            self.send_vehicle_command(
                VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
                1.0,
                6.0,
            )
            if self.spin_until(
                lambda: self._nav_state == VehicleStatus.NAVIGATION_STATE_OFFBOARD,
                timeout_sec=self._command_period_sec,
            ):
                break
        if self._nav_state != VehicleStatus.NAVIGATION_STATE_OFFBOARD:
            self.get_logger().error("OFFBOARD mode was not accepted.")
            return 1

        self.get_logger().info("OFFBOARD accepted. Requesting ARM...")
        arm_deadline = time.monotonic() + self._command_timeout_sec
        while time.monotonic() < arm_deadline:
            self.send_vehicle_command(
                VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                1.0,
            )
            if self.spin_until(
                lambda: self._arming_state == VehicleStatus.ARMING_STATE_ARMED,
                timeout_sec=self._command_period_sec,
            ):
                break
        if self._arming_state != VehicleStatus.ARMING_STATE_ARMED:
            self.get_logger().error("ARM was not accepted.")
            return 1

        self.get_logger().info(
            f"Armed. Climbing to {self._target_alt_m:.2f} m at {self._climb_speed_mps:.2f} m/s..."
        )
        climb_deadline = time.monotonic() + max(
            self._command_timeout_sec,
            (self._target_alt_m / max(self._climb_speed_mps, 0.01)) + 5.0,
        )
        while time.monotonic() < climb_deadline:
            self.publish_safety_twist(self._climb_speed_mps)
            if self.spin_until(
                lambda: self.current_altitude_m() >= self._target_alt_m,
                timeout_sec=0.05,
            ):
                break

        self.publish_safety_twist(0.0)
        self.spin_until(lambda: False, timeout_sec=0.3)

        if self.current_altitude_m() < self._target_alt_m:
            self.get_logger().error(
                f"Takeoff incomplete. Current altitude: {self.current_altitude_m():.2f} m"
            )
            return 1

        self.get_logger().info(
            f"Takeoff complete. Current altitude: {self.current_altitude_m():.2f} m. "
            "Releasing control to lower-priority sources."
        )
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Take off using PX4 vehicle commands plus twist_mux safety topic.",
    )
    parser.add_argument("--target-alt", type=float, default=1.5, help="Target altitude in meters")
    parser.add_argument("--climb-speed", type=float, default=0.6, help="Climb speed in m/s")
    parser.add_argument("--settle-sec", type=float, default=10.0, help="Post-EKF settle time")
    parser.add_argument(
        "--command-period-sec",
        type=float,
        default=1.0,
        help="Delay between repeated ARM/OFFBOARD requests",
    )
    parser.add_argument(
        "--command-timeout-sec",
        type=float,
        default=20.0,
        help="Timeout per phase",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rclpy.init(signal_handler_options=rclpy.SignalHandlerOptions.NO)
    node = OffboardTakeoff(
        target_alt_m=args.target_alt,
        climb_speed_mps=args.climb_speed,
        settle_sec=args.settle_sec,
        command_period_sec=args.command_period_sec,
        command_timeout_sec=args.command_timeout_sec,
    )
    try:
        return node.run()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
