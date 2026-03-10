// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#ifndef LIDAR_PREPROCESSOR__LIDAR_PREPROCESSOR_NODE_HPP_
#define LIDAR_PREPROCESSOR__LIDAR_PREPROCESSOR_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <std_msgs/msg/string.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_sensor_msgs/tf2_sensor_msgs.hpp>

#include <chrono>
#include <memory>
#include <string>
#include <vector>

namespace lidar_preprocessor
{

class LidarPreprocessor : public rclcpp::Node
{
public:
  explicit LidarPreprocessor(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  // Callbacks — dispatch only
  void on_cloud(sensor_msgs::msg::PointCloud2::ConstSharedPtr msg);
  void on_status_timer();

  // Core processing
  sensor_msgs::msg::PointCloud2 filter_cloud(
    const sensor_msgs::msg::PointCloud2 & input);

  // Helpers
  static bool cloud_has_field(
    const sensor_msgs::msg::PointCloud2 & cloud, const std::string & name);

  // Publishers
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr filtered_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;

  // Subscriber
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr cloud_sub_;

  // Timers
  rclcpp::TimerBase::SharedPtr status_timer_;

  // TF2
  std::shared_ptr<tf2_ros::Buffer>            tf_buffer_;
  std::shared_ptr<tf2_ros::TransformListener> tf_listener_;

  // Parameters (all from YAML, no magic numbers)
  double z_ground_threshold_;  // remove points below this height [m]
  double z_ceiling_threshold_; // remove points above this height [m]
  double max_range_;            // remove points beyond this distance [m]
  double min_range_;            // remove points closer than this [m]
  std::string input_topic_;
  std::string output_topic_;
  std::string target_frame_;   // fixed frame for z-filtering (e.g. "world")
  bool        use_tf_transform_;

  // Runtime state
  uint64_t messages_in_{0};
  uint64_t messages_out_{0};
  bool     tf_warn_printed_{false};
  rclcpp::Time last_cloud_stamp_{0, 0, RCL_ROS_TIME};
  // Timeout after which status becomes DEGRADED (then FAILED)
  static constexpr double kDegradedTimeoutSec = 1.0;
  static constexpr double kFailedTimeoutSec   = 3.0;
};

}  // namespace lidar_preprocessor

#endif  // LIDAR_PREPROCESSOR__LIDAR_PREPROCESSOR_NODE_HPP_
