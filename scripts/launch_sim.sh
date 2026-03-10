#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WORLD_FILE="${PROJECT_ROOT}/simulation/worlds/warehouse_phase0.sdf"
PX4_DIR="${HOME}/PX4-Autopilot"

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export GZ_SIM_RESOURCE_PATH="${PROJECT_ROOT}/simulation/models:${PX4_DIR}/Tools/simulation/gz/models:${GZ_SIM_RESOURCE_PATH:-}"

set +u
source /opt/ros/humble/setup.bash
source "${PROJECT_ROOT}/install/setup.bash" 2>/dev/null || true
set -u

echo "=== Drone New Method Phase 0 — Simulation Launcher ==="
echo "Project root: ${PROJECT_ROOT}"
echo "World file:   ${WORLD_FILE}"
echo "GZ resources: ${GZ_SIM_RESOURCE_PATH}"
echo ""

if [ ! -f "$WORLD_FILE" ]; then
    echo "ERROR: World file not found: ${WORLD_FILE}"
    exit 1
fi

echo "Cleaning up any stale processes..."
pkill -9 -f "px4_sitl_default/bin/px4" 2>/dev/null || true
pkill -9 -f "PX4_SIM_MODEL=" 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "ruby.*gz" 2>/dev/null || true
pkill -9 -f MicroXRCEAgent 2>/dev/null || true
pkill -9 -f parameter_bridge 2>/dev/null || true
rm -f /tmp/px4_sitl* /tmp/px4-* 2>/dev/null || true
sleep 3

PIDS=()

echo "[1/4] Starting PX4 SITL + Gazebo (x500_warehouse in warehouse_phase0)..."
export PX4_GZ_WORLD=warehouse_phase0
export PX4_GZ_MODEL_POSE="-9,0,0.2,0,0,0"
cd "${PX4_DIR}"
setsid make px4_sitl gz_x500_warehouse &
PX4_PID=$!
PIDS+=("$PX4_PID")
sleep 18

echo "[2/4] Starting Micro-XRCE-DDS Agent..."
setsid MicroXRCEAgent udp4 -p 8888 &
DDS_PID=$!
PIDS+=("$DDS_PID")
sleep 2

echo "[3/4] Starting ros_gz_bridge (Gazebo Transport → ROS 2)..."
ros2 run ros_gz_bridge parameter_bridge \
    /drone/perception/lidar/raw/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked \
    /drone/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image \
    /drone/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo \
    /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock &
BRIDGE_PID=$!
PIDS+=("$BRIDGE_PID")
sleep 2

echo "[4/4] Verifying ROS 2 topics..."
ros2 topic list 2>/dev/null | grep -E "drone|clock" || echo "  (waiting for topics...)"

echo ""
echo "=== All processes started ==="
echo "  PX4 SITL PID:    ${PX4_PID}"
echo "  DDS Agent PID:   ${DDS_PID}"
echo "  GZ Bridge PID:   ${BRIDGE_PID}"
echo ""
echo "Key ROS 2 topics:"
echo "  /drone/perception/lidar/raw/points  (PointCloud2)"
echo "  /drone/camera/image_raw             (Image)"
echo "  /fmu/out/*                          (PX4 via DDS)"
echo ""
echo "Press Ctrl+C to stop all processes."

cleanup() {
    echo ""
    echo "Shutting down..."
    for pid in "${PIDS[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    pkill -f "gz sim" 2>/dev/null || true
    sleep 1
    for pid in "${PIDS[@]}"; do
        kill -9 "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo "All processes stopped."
}

trap cleanup SIGINT SIGTERM EXIT
wait "${PIDS[@]}" 2>/dev/null
