from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    pkg_dir = get_package_share_directory("lidar_preprocessor")
    params_file = os.path.join(pkg_dir, "config", "lidar_preprocessor_params.yaml")

    lidar_preprocessor_node = Node(
        package="lidar_preprocessor",
        executable="lidar_preprocessor_node",
        name="lidar_preprocessor_node",
        output="screen",
        parameters=[params_file],
    )

    return LaunchDescription([lidar_preprocessor_node])
