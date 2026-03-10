// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#include "px4_bridge/px4_bridge_node.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>

namespace px4_bridge
{

static constexpr uint8_t kArmingStateArmed = 2;
static constexpr float kNaN = std::numeric_limits<float>::quiet_NaN();

Px4Bridge::Px4Bridge(const rclcpp::NodeOptions & options)
: Node("px4_bridge_node", options)
{
  max_velocity_xy_     = declare_parameter("max_velocity_xy", 2.0);
  max_velocity_z_      = declare_parameter("max_velocity_z", 1.0);
  watchdog_timeout_ms_ = declare_parameter("watchdog_timeout_ms", 200);

  // QoS — commands in, PX4 best-effort out
  auto cmd_qos = rclcpp::QoS(rclcpp::KeepLast(10))
    .reliable()
    .durability_volatile();

  auto px4_qos = rclcpp::QoS(rclcpp::KeepLast(5))
    .best_effort()
    .durability_volatile();

  auto status_qos = rclcpp::QoS(rclcpp::KeepLast(1))
    .reliable()
    .transient_local();

  // --- Publishers ---
  traj_pub_ = create_publisher<px4_msgs::msg::TrajectorySetpoint>(
    "/fmu/in/trajectory_setpoint", px4_qos);

  offboard_pub_ = create_publisher<px4_msgs::msg::OffboardControlMode>(
    "/fmu/in/offboard_control_mode", px4_qos);

  status_pub_ = create_publisher<std_msgs::msg::String>(
    "/drone/control/px4_bridge/status", status_qos);

  // --- Subscribers ---
  cmd_vel_sub_ = create_subscription<geometry_msgs::msg::Twist>(
    "/cmd_vel_out", cmd_qos,
    [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
      on_cmd_vel(std::move(msg));
    });

  vehicle_status_sub_ = create_subscription<px4_msgs::msg::VehicleStatus>(
    "/fmu/out/vehicle_status_v2", px4_qos,
    [this](px4_msgs::msg::VehicleStatus::ConstSharedPtr msg) {
      on_vehicle_status(std::move(msg));
    });

  odometry_sub_ = create_subscription<px4_msgs::msg::VehicleOdometry>(
    "/fmu/out/vehicle_odometry", px4_qos,
    [this](px4_msgs::msg::VehicleOdometry::ConstSharedPtr msg) {
      on_vehicle_odometry(std::move(msg));
    });

  tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);

  // 50 Hz control loop — PX4 requires continuous setpoint stream
  control_timer_ = create_wall_timer(
    std::chrono::milliseconds(20),
    std::bind(&Px4Bridge::on_control_timer, this));

  // 2 Hz status
  status_timer_ = create_wall_timer(
    std::chrono::milliseconds(500),
    std::bind(&Px4Bridge::on_status_timer, this));

  last_cmd_vel_time_ = now();

  RCLCPP_INFO(
    get_logger(),
    "Px4Bridge started — max_vel_xy=%.1fm/s  max_vel_z=%.1fm/s  watchdog=%dms",
    max_velocity_xy_, max_velocity_z_, watchdog_timeout_ms_);
}

// ============================================================
//  Callbacks — dispatch only (project rule)
// ============================================================

void Px4Bridge::on_cmd_vel(
  geometry_msgs::msg::Twist::ConstSharedPtr msg)
{
  target_vx_       = msg->linear.x;
  target_vy_       = msg->linear.y;
  target_vz_       = msg->linear.z;
  target_yawspeed_ = msg->angular.z;
  last_cmd_vel_time_ = now();
  cmd_vel_received_  = true;
}

void Px4Bridge::on_vehicle_status(
  px4_msgs::msg::VehicleStatus::ConstSharedPtr msg)
{
  arming_state_.store(msg->arming_state);
}

void Px4Bridge::on_vehicle_odometry(
  px4_msgs::msg::VehicleOdometry::ConstSharedPtr msg)
{
  geometry_msgs::msg::TransformStamped t;
  t.header.stamp = get_clock()->now();
  t.header.frame_id = "world";
  t.child_frame_id = "base_link";
  
  // Позиция NED -> ENU
  t.transform.translation.x = msg->position[1];
  t.transform.translation.y = msg->position[0];
  t.transform.translation.z = -msg->position[2];
  
  // Кватернион NED/FRD -> ENU/FLU
  t.transform.rotation.w = msg->q[0];
  t.transform.rotation.x = msg->q[2];
  t.transform.rotation.y = msg->q[1];
  t.transform.rotation.z = -msg->q[3];
  
  tf_broadcaster_->sendTransform(t);
  
  // Сохраняем текущий Yaw (в системе NED)
  current_yaw_ned_ = atan2(2.0 * (msg->q[0] * msg->q[3] + msg->q[1] * msg->q[2]),
                           1.0 - 2.0 * (msg->q[2] * msg->q[2] + msg->q[3] * msg->q[3]));
}

void Px4Bridge::on_control_timer()
{
  // Always publish offboard mode so PX4 can engage offboard
  publish_offboard_mode();

  // SAFETY: never publish velocity commands if not armed
  if (arming_state_.load() != kArmingStateArmed) {
    current_status_ = cmd_vel_received_ ? Status::DEGRADED : Status::FAILED;
    return;
  }

  // Watchdog (safety_rules.mdc RULE 2): no cmd_vel for >200ms → hover
  const auto elapsed = now() - last_cmd_vel_time_;
  const auto elapsed_ms =
    std::chrono::duration_cast<std::chrono::milliseconds>(
      elapsed.to_chrono<std::chrono::nanoseconds>()).count();

  if (!cmd_vel_received_ || elapsed_ms > watchdog_timeout_ms_) {
    if (cmd_vel_received_) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 1000,
        "Watchdog: no cmd_vel for %ldms — publishing hover setpoint",
        elapsed_ms);
    }
    publish_hover_setpoint();
    current_status_ = Status::DEGRADED;
    return;
  }

  publish_setpoints();
  current_status_ = Status::OK;
}

void Px4Bridge::on_status_timer()
{
  auto msg = std_msgs::msg::String();
  msg.data = status_string();
  status_pub_->publish(msg);
}

// ============================================================
//  PX4 setpoint publishing
// ============================================================

void Px4Bridge::publish_offboard_mode()
{
  px4_msgs::msg::OffboardControlMode msg{};
  msg.timestamp    = get_clock()->now().nanoseconds() / 1000;
  msg.position     = false;
  msg.velocity     = true;
  msg.acceleration = false;
  msg.attitude     = false;
  msg.body_rate    = false;
  offboard_pub_->publish(msg);
}

void Px4Bridge::publish_setpoints()
{
  const double vx = clamp_velocity(target_vx_, max_velocity_xy_);
  const double vy = clamp_velocity(target_vy_, max_velocity_xy_);
  const double vz = clamp_velocity(target_vz_, max_velocity_z_);

  px4_msgs::msg::TrajectorySetpoint msg{};
  msg.timestamp = get_clock()->now().nanoseconds() / 1000;

  // ROS body (FLU) → PX4 local NED
  double psi = current_yaw_ned_;

  // Пересчет Body FLU -> Local NED
  msg.velocity[0] = static_cast<float>(vx * cos(psi) + vy * sin(psi)); // North
  msg.velocity[1] = static_cast<float>(vx * sin(psi) - vy * cos(psi)); // East
  msg.velocity[2] = static_cast<float>(-vz);                           // Down

  // Unused axes: NaN = "don't care"
  msg.position[0]     = kNaN;
  msg.position[1]     = kNaN;
  msg.position[2]     = kNaN;
  msg.acceleration[0] = kNaN;
  msg.acceleration[1] = kNaN;
  msg.acceleration[2] = kNaN;
  msg.jerk[0]         = kNaN;
  msg.jerk[1]         = kNaN;
  msg.jerk[2]         = kNaN;
  msg.yaw             = kNaN;
  
  // Угловая скорость по Z напрямую передается (Body Z и NED D отличаются знаком)
  // поэтому для поворота влево (ROS +Z) нужно отправить отрицательный yawspeed в PX4
  msg.yawspeed        = static_cast<float>(-target_yawspeed_);

  traj_pub_->publish(msg);
}

void Px4Bridge::publish_hover_setpoint()
{
  px4_msgs::msg::TrajectorySetpoint msg{};
  msg.timestamp = get_clock()->now().nanoseconds() / 1000;

  msg.velocity[0] = 0.0f;
  msg.velocity[1] = 0.0f;
  msg.velocity[2] = 0.0f;

  msg.position[0]     = kNaN;
  msg.position[1]     = kNaN;
  msg.position[2]     = kNaN;
  msg.acceleration[0] = kNaN;
  msg.acceleration[1] = kNaN;
  msg.acceleration[2] = kNaN;
  msg.jerk[0]         = kNaN;
  msg.jerk[1]         = kNaN;
  msg.jerk[2]         = kNaN;
  msg.yaw             = kNaN;
  msg.yawspeed        = 0.0f;

  traj_pub_->publish(msg);
}

// ============================================================
//  Helpers
// ============================================================

double Px4Bridge::clamp_velocity(double v, double limit)
{
  return std::clamp(v, -limit, limit);
}

const char * Px4Bridge::status_string() const
{
  switch (current_status_) {
    case Status::OK:       return "OK";
    case Status::DEGRADED: return "DEGRADED";
    case Status::FAILED:   return "FAILED";
    default:               return "FAILED";
  }
}

}  // namespace px4_bridge

// ============================================================
//  main
// ============================================================

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<px4_bridge::Px4Bridge>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
