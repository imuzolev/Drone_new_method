"""Launch rack_follower_node with YAML parameters."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('rack_follower')

    config_file = LaunchConfiguration('config_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value=os.path.join(pkg_dir, 'config', 'rack_follower_params.yaml'),
            description='Full path to rack_follower parameter YAML',
        ),
        Node(
            package='rack_follower',
            executable='rack_follower_node',
            name='rack_follower_node',
            parameters=[config_file],
            output='screen',
        ),
    ])
