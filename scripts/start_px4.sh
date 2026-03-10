#!/usr/bin/env bash
# Start PX4 SITL with Gazebo warehouse world
export PX4_GZ_WORLD=warehouse_phase0
export PX4_GZ_MODEL_POSE="-9,0,0.2,0,0,0"
export GZ_SIM_RESOURCE_PATH="/mnt/c/CORTEXIS/Drone_new_method/simulation/models:/home/imuzolev/PX4-Autopilot/Tools/simulation/gz/models"

rm -f /tmp/px4_sitl* /tmp/px4-* 2>/dev/null || true

cd /home/imuzolev/PX4-Autopilot
exec make px4_sitl gz_x500_warehouse
