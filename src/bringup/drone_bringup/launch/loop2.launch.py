"""
Loop 2 — Rack Follower bringup launch file.

Starts all four nodes required for autonomous aisle traversal:
  1. lidar_preprocessor  — raw PointCloud2 → filtered PointCloud2
  2. rack_follower        — filtered cloud → cmd_vel (PD wall-follower)
  3. twist_mux            — cmd_vel arbitration by priority
  4. px4_bridge           — /cmd_vel_out → PX4 TrajectorySetpoint (XRCE-DDS)
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import SetParameter


def generate_launch_description():
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use /clock from Gazebo simulation",
    )
    use_sim_time = LaunchConfiguration("use_sim_time")

    set_sim_time = SetParameter(name="use_sim_time", value=use_sim_time)

    lidar_dir  = get_package_share_directory("lidar_preprocessor")
    rack_dir   = get_package_share_directory("rack_follower")
    mux_dir    = get_package_share_directory("twist_mux_config")
    bridge_dir = get_package_share_directory("px4_bridge")

    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(lidar_dir, "launch", "lidar_preprocessor.launch.py")
        ),
    )

    rack_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(rack_dir, "launch", "rack_follower.launch.py")
        ),
    )

    mux_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(mux_dir, "launch", "twist_mux.launch.py")
        ),
    )

    bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bridge_dir, "launch", "px4_bridge.launch.py")
        ),
    )

    return LaunchDescription([
        use_sim_time_arg,
        set_sim_time,
        LogInfo(msg="[Loop2] Starting Rack Follower pipeline (4 nodes)..."),
        lidar_launch,
        rack_launch,
        mux_launch,
        bridge_launch,
        LogInfo(msg="[Loop2] All nodes launched."),
    ])
