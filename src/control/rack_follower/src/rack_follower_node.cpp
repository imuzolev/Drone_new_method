// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#include "rack_follower/rack_follower_node.hpp"

#include <sensor_msgs/point_cloud2_iterator.hpp>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <string>

namespace rack_follower
{

RackFollower::RackFollower(const rclcpp::NodeOptions & options)
: Node("rack_follower_node", options)
{
  // --- Declare parameters (all from YAML) ---
  target_distance_     = declare_parameter("target_distance", 0.8);
  kp_                  = declare_parameter("kp", 0.5);
  kd_                  = declare_parameter("kd", 0.1);
  base_speed_          = declare_parameter("base_speed", 0.3);
  max_error_           = declare_parameter("max_error", 0.4);
  watchdog_timeout_ms_ = declare_parameter("watchdog_timeout_ms", 200);
  follow_left_         = declare_parameter("follow_left", true);
  filter_z_min_        = declare_parameter("filter_z_min", 0.3);
  filter_z_max_        = declare_parameter("filter_z_max", 3.5);
  filter_x_range_      = declare_parameter("filter_x_range", 2.0);
  output_frame_id_     = declare_parameter("output_frame_id", std::string("base_link"));

  // --- QoS profiles (from ros2_conventions.mdc) ---
  auto sensor_qos = rclcpp::QoS(rclcpp::KeepLast(5))
    .best_effort()
    .durability_volatile();

  auto cmd_qos = rclcpp::QoS(rclcpp::KeepLast(10))
    .reliable()
    .durability_volatile();

  auto status_qos = rclcpp::QoS(rclcpp::KeepLast(1))
    .reliable()
    .transient_local();

  // --- Publishers ---
  cmd_vel_pub_ = create_publisher<geometry_msgs::msg::TwistStamped>(
    "/drone/control/rack_follower/cmd_vel", cmd_qos);

  status_pub_ = create_publisher<std_msgs::msg::String>(
    "/drone/control/rack_follower/status", status_qos);

  wall_dist_pub_ = create_publisher<std_msgs::msg::Float32>(
    "/drone/control/rack_follower/wall_distance", cmd_qos);

  // --- Subscriber ---
  lidar_sub_ = create_subscription<sensor_msgs::msg::PointCloud2>(
    "/drone/perception/lidar/filtered", sensor_qos,
    [this](sensor_msgs::msg::PointCloud2::ConstSharedPtr msg) {
      on_lidar(std::move(msg));
    });

  // --- Watchdog timer: polls at 50 ms, triggers at watchdog_timeout_ms ---
  watchdog_timer_ = create_wall_timer(
    std::chrono::milliseconds(50),
    std::bind(&RackFollower::on_watchdog, this));

  // --- Status publisher at 2 Hz ---
  status_timer_ = create_wall_timer(
    std::chrono::milliseconds(500),
    std::bind(&RackFollower::on_status_timer, this));

  // Start in FAILED until first LiDAR message arrives
  prev_compute_time_ = now();

  RCLCPP_INFO(
    get_logger(),
    "RackFollower started — target=%.2fm  Kp=%.2f  Kd=%.2f  "
    "base_speed=%.2fm/s  follow_left=%s  watchdog=%dms",
    target_distance_, kp_, kd_, base_speed_,
    follow_left_ ? "true" : "false", watchdog_timeout_ms_);
}

// ============================================================
//  Callbacks — dispatch only (project rule: no business logic)
// ============================================================

void RackFollower::on_lidar(
  sensor_msgs::msg::PointCloud2::ConstSharedPtr msg)
{
  lidar_alive_ = true;
  compute_control(*msg);
}

void RackFollower::on_watchdog()
{
  if (!lidar_alive_) {
    publish_zero_velocity();
    return;
  }

  const auto elapsed = now() - prev_compute_time_;
  const auto elapsed_ms =
    std::chrono::duration_cast<std::chrono::milliseconds>(
      elapsed.to_chrono<std::chrono::nanoseconds>()).count();

  if (elapsed_ms > watchdog_timeout_ms_) {
    RCLCPP_WARN_THROTTLE(
      get_logger(), *get_clock(), 1000,
      "Watchdog: no LiDAR data for %ldms — zero velocity", elapsed_ms);
    lidar_alive_ = false;
    current_status_ = Status::FAILED;
    has_prev_error_ = false;
    publish_zero_velocity();
  }
}

void RackFollower::on_status_timer()
{
  auto msg = std_msgs::msg::String();
  msg.data = status_string();
  status_pub_->publish(msg);
}

// ============================================================
//  Core PD controller  (Section 5.1 algorithm)
// ============================================================

void RackFollower::compute_control(
  const sensor_msgs::msg::PointCloud2 & cloud)
{
  const double measured = extract_wall_distance(cloud);

  // Publish measured distance for downstream (scan_policy_fsm)
  auto dist_msg = std_msgs::msg::Float32();
  dist_msg.data = static_cast<float>(measured);
  wall_dist_pub_->publish(dist_msg);

  if (!std::isfinite(measured)) {
    RCLCPP_WARN_THROTTLE(
      get_logger(), *get_clock(), 2000,
      "No valid wall points — publishing zero velocity");
    current_status_ = Status::DEGRADED;
    has_prev_error_ = false;
    publish_zero_velocity();
    return;
  }

  // error = target_distance - measured_distance
  const double error = target_distance_ - measured;
  const double abs_error = std::abs(error);

  // PD: derivative term
  double derror_dt = 0.0;
  const auto current_time = now();
  if (has_prev_error_) {
    const double dt = (current_time - prev_compute_time_).seconds();
    if (dt > 1e-6) {
      derror_dt = (error - prev_error_) / dt;
    }
  }
  prev_error_ = error;
  prev_compute_time_ = current_time;
  has_prev_error_ = true;

  const double lateral_correction = kp_ * error + kd_ * derror_dt;

  // Sign convention: positive error = too close to wall
  //   Left  wall (Y>0): push away = negative Y → negate
  //   Right wall (Y<0): push away = positive Y → keep
  const double vy = follow_left_ ? -lateral_correction : lateral_correction;

  // Forward speed: slow down proportionally to lateral error,
  // stop completely when abs_error >= max_error  (Section 5.1 formula)
  const double vx = std::clamp(
    base_speed_ * (1.0 - abs_error / max_error_), 0.0, base_speed_);

  publish_cmd_vel(vx, vy);

  // Update status
  if (abs_error < max_error_ * 0.5) {
    current_status_ = Status::OK;
  } else {
    current_status_ = Status::DEGRADED;
  }
}

// ============================================================
//  PointCloud processing — extract minimum lateral distance
// ============================================================

double RackFollower::extract_wall_distance(
  const sensor_msgs::msg::PointCloud2 & cloud)
{
  const size_t num_points = cloud.width * cloud.height;
  if (num_points == 0) {
    return std::numeric_limits<double>::infinity();
  }

  if (!cloud_has_field(cloud, "x") ||
      !cloud_has_field(cloud, "y") ||
      !cloud_has_field(cloud, "z"))
  {
    RCLCPP_WARN_THROTTLE(
      get_logger(), *get_clock(), 5000,
      "PointCloud2 missing x/y/z fields");
    return std::numeric_limits<double>::infinity();
  }

  // Locate byte offsets for x, y, z
  int x_off = -1, y_off = -1, z_off = -1;
  for (const auto & f : cloud.fields) {
    if (f.name == "x") { x_off = static_cast<int>(f.offset); }
    if (f.name == "y") { y_off = static_cast<int>(f.offset); }
    if (f.name == "z") { z_off = static_cast<int>(f.offset); }
  }

  double min_lateral = std::numeric_limits<double>::infinity();
  const uint32_t step = cloud.point_step;

  for (size_t i = 0; i < num_points; ++i) {
    const uint8_t * ptr = &cloud.data[i * step];
    float x, y, z;
    std::memcpy(&x, ptr + x_off, sizeof(float));
    std::memcpy(&y, ptr + y_off, sizeof(float));
    std::memcpy(&z, ptr + z_off, sizeof(float));

    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
      continue;
    }

    // Height band filter (world-frame Z)
    if (z < filter_z_min_ || z > filter_z_max_) { continue; }

    // Forward range filter (only points near the drone along X)
    if (std::abs(x) > filter_x_range_) { continue; }

    double lateral;
    if (follow_left_) {
      if (y <= 0.0f) { continue; }
      lateral = static_cast<double>(y);
    } else {
      if (y >= 0.0f) { continue; }
      lateral = static_cast<double>(-y);
    }

    if (lateral < min_lateral) {
      min_lateral = lateral;
    }
  }

  return min_lateral;
}

// ============================================================
//  Helpers
// ============================================================

void RackFollower::publish_cmd_vel(double vx, double vy)
{
  geometry_msgs::msg::TwistStamped msg;
  msg.header.stamp    = now();
  msg.header.frame_id = output_frame_id_;
  msg.twist.linear.x  = vx;
  msg.twist.linear.y  = vy;
  msg.twist.linear.z  = 0.0;
  msg.twist.angular.x = 0.0;
  msg.twist.angular.y = 0.0;
  msg.twist.angular.z = 0.0;
  cmd_vel_pub_->publish(msg);
}

void RackFollower::publish_zero_velocity()
{
  publish_cmd_vel(0.0, 0.0);
}

const char * RackFollower::status_string() const
{
  switch (current_status_) {
    case Status::OK:       return "OK";
    case Status::DEGRADED: return "DEGRADED";
    case Status::FAILED:   return "FAILED";
    default:               return "FAILED";
  }
}

bool RackFollower::cloud_has_field(
  const sensor_msgs::msg::PointCloud2 & cloud, const std::string & name)
{
  for (const auto & f : cloud.fields) {
    if (f.name == name) { return true; }
  }
  return false;
}

}  // namespace rack_follower

// ============================================================
//  main
// ============================================================

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rack_follower::RackFollower>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
