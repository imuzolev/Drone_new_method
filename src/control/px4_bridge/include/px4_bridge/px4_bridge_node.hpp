// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#ifndef PX4_BRIDGE__PX4_BRIDGE_NODE_HPP_
#define PX4_BRIDGE__PX4_BRIDGE_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist_stamped.hpp>
#include <px4_msgs/msg/offboard_control_mode.hpp>
#include <px4_msgs/msg/trajectory_setpoint.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <std_msgs/msg/string.hpp>

#include <atomic>
#include <string>

namespace px4_bridge
{

class Px4Bridge : public rclcpp::Node
{
public:
  explicit Px4Bridge(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  // Callbacks — dispatch only (project rule)
  void on_cmd_vel(geometry_msgs::msg::TwistStamped::ConstSharedPtr msg);
  void on_vehicle_status(px4_msgs::msg::VehicleStatus::ConstSharedPtr msg);
  void on_control_timer();
  void on_status_timer();

  // Core logic
  void publish_setpoints();
  void publish_offboard_mode();
  void publish_hover_setpoint();

  // Helpers
  static double clamp_velocity(double v, double limit);
  const char * status_string() const;

  // Publishers
  rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr traj_pub_;
  rclcpp::Publisher<px4_msgs::msg::OffboardControlMode>::SharedPtr offboard_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;

  // Subscribers
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr cmd_vel_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr vehicle_status_sub_;

  // Timers
  rclcpp::TimerBase::SharedPtr control_timer_;
  rclcpp::TimerBase::SharedPtr status_timer_;

  // --- Parameters (all from YAML, no magic numbers) ---
  double max_velocity_xy_;
  double max_velocity_z_;
  int    watchdog_timeout_ms_;

  // --- Runtime state ---
  double target_vx_{0.0};
  double target_vy_{0.0};
  double target_vz_{0.0};
  double target_yawspeed_{0.0};

  rclcpp::Time last_cmd_vel_time_;
  std::atomic<uint8_t> arming_state_{0};
  bool cmd_vel_received_{false};

  enum class Status : uint8_t { OK, DEGRADED, FAILED };
  Status current_status_{Status::FAILED};
};

}  // namespace px4_bridge

#endif  // PX4_BRIDGE__PX4_BRIDGE_NODE_HPP_
