#!/usr/bin/env python3
import sys
try:
    from px4_msgs.msg import VehicleCommand, VehicleStatus, VehicleLocalPosition
    from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint
    print("px4_msgs OK")
    sys.exit(0)
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)
