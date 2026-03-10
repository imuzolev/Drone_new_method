"""Launch barcode_scanner_node (C++) and scan_policy_fsm (Python)."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory("barcode_scanner")
    config_file = LaunchConfiguration("config_file")

    return LaunchDescription([
        DeclareLaunchArgument(
            "config_file",
            default_value=os.path.join(pkg, "config", "barcode_scanner_params.yaml"),
            description="Full path to barcode_scanner parameter YAML",
        ),

        # C++ decoder node
        Node(
            package="barcode_scanner",
            executable="barcode_scanner_node",
            name="barcode_scanner_node",
            parameters=[config_file],
            output="screen",
        ),

        # Python FSM node
        Node(
            package="barcode_scanner",
            executable="scan_policy_fsm.py",
            name="scan_policy_fsm_node",
            parameters=[config_file],
            output="screen",
        ),
    ])
