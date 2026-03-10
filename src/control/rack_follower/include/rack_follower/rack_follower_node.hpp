// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#ifndef RACK_FOLLOWER__RACK_FOLLOWER_NODE_HPP_
#define RACK_FOLLOWER__RACK_FOLLOWER_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <std_msgs/msg/float32.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/bool.hpp>

#include <string>

namespace rack_follower
{

class RackFollower : public rclcpp::Node
{
public:
  explicit RackFollower(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  // Callbacks — dispatch only, no business logic (project rule)
  void on_lidar(sensor_msgs::msg::PointCloud2::ConstSharedPtr msg);
  void on_distance_adjust(std_msgs::msg::Float32::ConstSharedPtr msg);
  void on_reset_distance(std_msgs::msg::Bool::ConstSharedPtr msg);
  void on_watchdog();
  void on_status_timer();

  // Core logic
  void compute_control(const sensor_msgs::msg::PointCloud2 & cloud);
  double extract_wall_distance(const sensor_msgs::msg::PointCloud2 & cloud);

  // Helpers
  void publish_cmd_vel(double vx, double vy);
  void publish_zero_velocity();
  const char * status_string() const;
  static bool cloud_has_field(
    const sensor_msgs::msg::PointCloud2 & cloud, const std::string & name);

  // Publishers
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr wall_dist_pub_;
  rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr lateral_error_pub_;

  // Subscriber
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr lidar_sub_;
  rclcpp::Subscription<std_msgs::msg::Float32>::SharedPtr dist_adjust_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr reset_dist_sub_;

  // Timers
  rclcpp::TimerBase::SharedPtr watchdog_timer_;
  rclcpp::TimerBase::SharedPtr status_timer_;

  // --- Parameters (all from YAML, no magic numbers) ---
  double target_distance_;
  double base_target_distance_;
  double kp_;
  double kd_;
  double base_speed_;
  double max_error_;
  int    watchdog_timeout_ms_;
  bool   follow_left_;
  double filter_z_min_;
  double filter_z_max_;
  double filter_x_range_;
  std::string output_frame_id_;

  // --- Runtime state ---
  double prev_error_{0.0};
  rclcpp::Time prev_compute_time_;
  bool   has_prev_error_{false};
  bool   lidar_alive_{false};

  enum class Status : uint8_t { OK, DEGRADED, FAILED };
  Status current_status_{Status::FAILED};
};

}  // namespace rack_follower

#endif  // RACK_FOLLOWER__RACK_FOLLOWER_NODE_HPP_
