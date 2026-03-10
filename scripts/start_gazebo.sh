#!/usr/bin/env bash
# Launch Gazebo Harmonic with the warehouse_phase0 world.
# Usage from WSL:  bash /mnt/c/CORTEXIS/Drone_new_method/scripts/start_gazebo.sh
# Usage from Win:  wsl -d Ubuntu-22.04 -u imuzolev -- bash /mnt/c/CORTEXIS/Drone_new_method/scripts/start_gazebo.sh
set -eu
set -o pipefail 2>/dev/null || true

PROJECT_WSL="/mnt/c/CORTEXIS/Drone_new_method"
WORLD="${PROJECT_WSL}/simulation/worlds/warehouse_phase0.sdf"

export GZ_SIM_RESOURCE_PATH="${PROJECT_WSL}/simulation/models:${HOME}/PX4-Autopilot/Tools/simulation/gz/models:${GZ_SIM_RESOURCE_PATH:-}"

if [ ! -f "$WORLD" ]; then
    echo "ERROR: World file not found: ${WORLD}"
    exit 1
fi

echo "=== Gazebo Harmonic — warehouse_phase0 ==="
echo "World: ${WORLD}"
echo "Resource paths: ${GZ_SIM_RESOURCE_PATH}"
echo ""
echo "Camera controls:"
echo "  Right-click drag  — orbit"
echo "  Middle-click drag — pan"
echo "  Scroll wheel      — zoom"
echo "  Right-click model → Follow / Move To"
echo ""

gz sim "$WORLD"
