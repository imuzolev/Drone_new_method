#!/usr/bin/env python3
"""Quick test: can we receive PX4 DDS topics via ROS 2?"""
import signal
import time
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from px4_msgs.msg import SensorCombined, VehicleAttitude

signal.signal(signal.SIGINT, signal.SIG_DFL)
signal.signal(signal.SIGTERM, signal.SIG_DFL)


class Px4TestSub(Node):
    def __init__(self):
        super().__init__("px4_test_sub")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )
        self.got_sensor = False
        self.got_attitude = False
        self.create_subscription(SensorCombined, "/fmu/out/sensor_combined", self._cb_sensor, qos)
        self.create_subscription(VehicleAttitude, "/fmu/out/vehicle_attitude", self._cb_att, qos)
        print("Subscribed to sensor_combined + vehicle_attitude (BEST_EFFORT/VOLATILE)", flush=True)
        print(f"rclpy.ok() = {rclpy.ok()}", flush=True)

    def _cb_sensor(self, msg):
        if not self.got_sensor:
            print(
                f"GOT sensor_combined: gyro=({msg.gyro_rad[0]:.4f}, {msg.gyro_rad[1]:.4f}, {msg.gyro_rad[2]:.4f})",
                flush=True,
            )
            self.got_sensor = True

    def _cb_att(self, msg):
        if not self.got_attitude:
            print(
                f"GOT vehicle_attitude: q=({msg.q[0]:.4f}, {msg.q[1]:.4f}, {msg.q[2]:.4f}, {msg.q[3]:.4f})",
                flush=True,
            )
            self.got_attitude = True


def main():
    rclpy.init(signal_handler_options=rclpy.SignalHandlerOptions.NO)
    node = Px4TestSub()
    start = time.monotonic()
    timeout_sec = 8.0
    while (time.monotonic() - start) < timeout_sec:
        rclpy.spin_once(node, timeout_sec=0.5)
        if node.got_sensor and node.got_attitude:
            break
    if not node.got_sensor:
        print("WARN: NO sensor_combined data received", flush=True)
    if not node.got_attitude:
        print("WARN: NO vehicle_attitude data received", flush=True)
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
