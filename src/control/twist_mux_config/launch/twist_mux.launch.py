"""Launch twist_mux with Drone New Method priority configuration."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('twist_mux_config')

    config_file = LaunchConfiguration('config_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value=os.path.join(pkg_dir, 'config', 'twist_mux.yaml'),
            description='Full path to twist_mux parameter YAML',
        ),
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            parameters=[config_file],
            remappings=[
                ('cmd_vel_out', '/cmd_vel_out'),
            ],
            output='screen',
        ),
    ])
