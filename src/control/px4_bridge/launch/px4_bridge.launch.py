"""Launch px4_bridge_node with YAML parameters."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('px4_bridge')

    config_file = LaunchConfiguration('config_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value=os.path.join(pkg_dir, 'config', 'px4_bridge_params.yaml'),
            description='Full path to px4_bridge parameter YAML',
        ),
        Node(
            package='px4_bridge',
            executable='px4_bridge_node',
            name='px4_bridge_node',
            parameters=[config_file],
            output='screen',
        ),
    ])
