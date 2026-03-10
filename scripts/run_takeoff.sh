#!/usr/bin/env bash
# Start arm_and_takeoff.py in background and keep running
set +u
source /opt/ros/humble/setup.bash
source /mnt/c/CORTEXIS/Drone_new_method/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set -u

echo "Starting arm_and_takeoff.py..."
python3 -u /mnt/c/CORTEXIS/Drone_new_method/scripts/arm_and_takeoff.py 2>&1 | tee /tmp/takeoff.log
