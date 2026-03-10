#!/usr/bin/env python3
"""
Minimal arm + offboard mode + takeoff script for PX4 SITL testing.
Sends VehicleCommand to ARM and enable OFFBOARD, then climbs to target_alt.

Usage:
    ros2 run <pkg> arm_and_takeoff.py
    # or directly:
    python3 arm_and_takeoff.py
"""

import rclpy  # type: ignore[import]
from rclpy.node import Node  # type: ignore[import]
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy  # type: ignore[import]
from px4_msgs.msg import (  # type: ignore[import]
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleStatus,
    VehicleLocalPosition,
)


class ArmAndTakeoff(Node):
    """Arm the drone, enter offboard mode, climb to target altitude, then hover."""

    TARGET_ALT_M = 1.5   # metres above takeoff point (NED: negative Z)
    CLIMB_SPEED   = 0.4  # m/s

    def __init__(self) -> None:
        super().__init__("arm_and_takeoff")

        px4_qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.offboard_pub_ = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", px4_qos
        )
        self.traj_pub_ = self.create_publisher(
            TrajectorySetpoint, "/fmu/in/trajectory_setpoint", px4_qos
        )
        self.cmd_pub_ = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", px4_qos
        )

        self.create_subscription(
            VehicleStatus, "/fmu/out/vehicle_status", self._on_status, px4_qos
        )
        self.create_subscription(
            VehicleLocalPosition,
            "/fmu/out/vehicle_local_position",
            self._on_local_pos,
            px4_qos,
        )

        self._arming_state: int = 0
        self._nav_state: int = 0
        self._z_m: float = 0.0        # NED Z (negative = up)
        self._offboard_counter: int = 0
        self._phase: str = "pre_arm"  # pre_arm → arm → offboard → climb → hover

        self._timer = self.create_timer(0.1, self._step)  # 10 Hz

        self.get_logger().info(
            f"ArmAndTakeoff started — target altitude {self.TARGET_ALT_M} m"
        )

    def _on_status(self, msg: VehicleStatus) -> None:
        self._arming_state = msg.arming_state
        self._nav_state    = msg.nav_state

    def _on_local_pos(self, msg: VehicleLocalPosition) -> None:
        self._z_m = msg.z  # NED: negative when above ground

    def _step(self) -> None:
        """State machine step at 10 Hz."""
        self._publish_offboard_mode()

        if self._phase == "pre_arm":
            # Need at least 10 offboard heartbeats before arming
            self._offboard_counter += 1
            self._publish_hover_setpoint()
            if self._offboard_counter >= 10:
                self.get_logger().info("Sending ARM command…")
                self._send_vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
                self._phase = "arm"

        elif self._phase == "arm":
            self._publish_hover_setpoint()
            # arming_state == 2 means ARMED
            if self._arming_state == 2:
                self.get_logger().info("Armed. Switching to OFFBOARD mode…")
                self._send_vehicle_command(
                    VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0  # mode 6 = offboard
                )
                self._phase = "offboard"

        elif self._phase == "offboard":
            self._publish_hover_setpoint()
            # nav_state 14 = OFFBOARD
            if self._nav_state == 14:
                self.get_logger().info("Offboard engaged. Climbing…")
                self._phase = "climb"

        elif self._phase == "climb":
            target_ned_z = -self.TARGET_ALT_M
            current_alt  = -self._z_m          # convert NED Z to altitude
            self.get_logger().info(
                f"Climbing: alt={current_alt:.2f}m / target={self.TARGET_ALT_M}m"
            )
            if current_alt >= self.TARGET_ALT_M - 0.1:
                self.get_logger().info(
                    f"Target altitude reached ({current_alt:.2f} m). Hovering."
                )
                self._phase = "hover"
            else:
                self._publish_climb_setpoint()

        elif self._phase == "hover":
            self._publish_hover_setpoint()

    def _publish_offboard_mode(self) -> None:
        msg = OffboardControlMode()
        msg.timestamp    = self.get_clock().now().nanoseconds // 1000
        msg.position     = False
        msg.velocity     = True
        msg.acceleration = False
        msg.attitude     = False
        msg.body_rate    = False
        self.offboard_pub_.publish(msg)

    def _publish_hover_setpoint(self) -> None:
        msg = TrajectorySetpoint()
        msg.timestamp   = self.get_clock().now().nanoseconds // 1000
        msg.velocity[0] = 0.0
        msg.velocity[1] = 0.0
        msg.velocity[2] = 0.0
        import math
        msg.position[0] = float("nan")
        msg.position[1] = float("nan")
        msg.position[2] = float("nan")
        self.traj_pub_.publish(msg)

    def _publish_climb_setpoint(self) -> None:
        msg = TrajectorySetpoint()
        msg.timestamp   = self.get_clock().now().nanoseconds // 1000
        msg.velocity[0] = 0.0
        msg.velocity[1] = 0.0
        msg.velocity[2] = -self.CLIMB_SPEED   # NED: negative = up
        msg.position[0] = float("nan")
        msg.position[1] = float("nan")
        msg.position[2] = float("nan")
        self.traj_pub_.publish(msg)

    def _send_vehicle_command(
        self, command: int, param1: float = 0.0, param2: float = 0.0
    ) -> None:
        msg = VehicleCommand()
        msg.timestamp        = self.get_clock().now().nanoseconds // 1000
        msg.command          = command
        msg.param1           = param1
        msg.param2           = param2
        msg.target_system    = 1
        msg.target_component = 1
        msg.source_system    = 1
        msg.source_component = 1
        msg.from_external    = True
        self.cmd_pub_.publish(msg)


def main() -> None:
    rclpy.init()
    node = ArmAndTakeoff()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
