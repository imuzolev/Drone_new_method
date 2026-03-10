#!/usr/bin/env python3
"""Check PX4 preflight status and local position validity."""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from px4_msgs.msg import VehicleStatus, VehicleLocalPosition
import time

def main():
    rclpy.init(signal_handler_options=rclpy.SignalHandlerOptions.NO)
    node = rclpy.create_node('preflight_checker')

    qos = QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=5
    )

    got_status = [False]
    def status_cb(msg):
        if not got_status[0]:
            got_status[0] = True
            print('=== VehicleStatus ===')
            for attr in sorted(dir(msg)):
                if 'pre_flight' in attr or 'arming' in attr or 'nav_state' in attr:
                    print(f'  {attr}={getattr(msg, attr)}')

    node.create_subscription(VehicleStatus, '/fmu/out/vehicle_status_v2', status_cb, qos)

    got_pos = [False]
    def pos_cb(msg):
        if not got_pos[0]:
            got_pos[0] = True
            print('=== VehicleLocalPosition ===')
            for attr in ['xy_valid', 'z_valid', 'v_xy_valid', 'v_z_valid',
                         'xy_global', 'z_global', 'x', 'y', 'z', 'heading',
                         'heading_good_for_control']:
                val = getattr(msg, attr, 'N/A')
                if isinstance(val, float):
                    print(f'  {attr}={val:.4f}')
                else:
                    print(f'  {attr}={val}')

    node.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1', pos_cb, qos)

    start = time.time()
    while time.time() - start < 8:
        rclpy.spin_once(node, timeout_sec=0.5)
        if got_status[0] and got_pos[0]:
            break

    if not got_status[0]:
        print('WARNING: No VehicleStatus received')
    if not got_pos[0]:
        print('WARNING: No VehicleLocalPosition received')

    rclpy.try_shutdown()

if __name__ == '__main__':
    main()
