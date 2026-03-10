// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#include "lidar_preprocessor/lidar_preprocessor_node.hpp"

#include <cmath>
#include <cstring>
#include <string>
#include <vector>

namespace lidar_preprocessor
{

LidarPreprocessor::LidarPreprocessor(const rclcpp::NodeOptions & options)
: Node("lidar_preprocessor_node", options)
{
  // --- Declare parameters (all from YAML) ---
  z_ground_threshold_  = declare_parameter("z_ground_threshold", 0.05);
  z_ceiling_threshold_ = declare_parameter("z_ceiling_threshold", 4.0);
  max_range_           = declare_parameter("max_range", 8.0);
  min_range_           = declare_parameter("min_range", 0.10);
  input_topic_         = declare_parameter("input_topic",
    std::string("/drone/perception/lidar/raw/points"));
  output_topic_        = declare_parameter("output_topic",
    std::string("/drone/perception/lidar/filtered"));
  target_frame_        = declare_parameter("target_frame", std::string("world"));
  use_tf_transform_    = declare_parameter("use_tf_transform", true);

  // --- TF2 ---
  tf_buffer_   = std::make_shared<tf2_ros::Buffer>(get_clock());
  tf_listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_buffer_);

  // --- QoS (ros2_conventions.mdc: sensors = BEST_EFFORT, VOLATILE, depth=5) ---
  auto sensor_qos = rclcpp::QoS(rclcpp::KeepLast(5))
    .best_effort()
    .durability_volatile();

  auto status_qos = rclcpp::QoS(rclcpp::KeepLast(1))
    .reliable()
    .transient_local();

  // --- Publishers ---
  filtered_pub_ = create_publisher<sensor_msgs::msg::PointCloud2>(
    output_topic_, sensor_qos);

  status_pub_ = create_publisher<std_msgs::msg::String>(
    "/lidar_preprocessor/status", status_qos);

  // --- Subscriber ---
  cloud_sub_ = create_subscription<sensor_msgs::msg::PointCloud2>(
    input_topic_, sensor_qos,
    [this](sensor_msgs::msg::PointCloud2::ConstSharedPtr msg) {
      on_cloud(std::move(msg));
    });

  // --- Status timer at 2 Hz ---
  status_timer_ = create_wall_timer(
    std::chrono::milliseconds(500),
    std::bind(&LidarPreprocessor::on_status_timer, this));

  RCLCPP_INFO(
    get_logger(),
    "LidarPreprocessor started — in=%s  out=%s  "
    "z=[%.2f, %.2f]  range=[%.2f, %.2f]  tf=%s→%s",
    input_topic_.c_str(), output_topic_.c_str(),
    z_ground_threshold_, z_ceiling_threshold_,
    min_range_, max_range_,
    use_tf_transform_ ? "sensor" : "none",
    use_tf_transform_ ? target_frame_.c_str() : "sensor");
}

// ============================================================
//  Callbacks — dispatch only
// ============================================================

void LidarPreprocessor::on_cloud(
  sensor_msgs::msg::PointCloud2::ConstSharedPtr msg)
{
  last_cloud_stamp_ = now();
  ++messages_in_;

  // Create a copy to override the frame_id to base_link since we don't have 
  // the full Gazebo TF tree (base_link -> lidar_link) published to ROS 2.
  // The LiDAR is at z=0.06m relative to base_link, which is negligible for our Z-filters.
  sensor_msgs::msg::PointCloud2 cloud_msg = *msg;
  cloud_msg.header.frame_id = "base_link";

  // Transform to fixed world frame so z-filter works in world coordinates,
  // not sensor frame. Falls back to sensor frame if TF not available.
  sensor_msgs::msg::PointCloud2 cloud_for_filter;
  if (use_tf_transform_) {
    try {
      tf_buffer_->transform(cloud_msg, cloud_for_filter, target_frame_,
        tf2::durationFromSec(0.05));
      tf_warn_printed_ = false;
    } catch (const tf2::TransformException & ex) {
      if (!tf_warn_printed_) {
        RCLCPP_WARN(get_logger(),
          "TF transform to '%s' failed: %s — filtering in sensor frame",
          target_frame_.c_str(), ex.what());
        tf_warn_printed_ = true;
      }
      cloud_for_filter = cloud_msg;
    }
  } else {
    cloud_for_filter = cloud_msg;
  }

  auto filtered = filter_cloud(cloud_for_filter);
  filtered_pub_->publish(filtered);
  ++messages_out_;
}

void LidarPreprocessor::on_status_timer()
{
  auto msg = std_msgs::msg::String();

  if (last_cloud_stamp_.nanoseconds() == 0) {
    // Never received a cloud yet
    msg.data = "FAILED";
  } else {
    const double age = (now() - last_cloud_stamp_).seconds();
    if (age < kDegradedTimeoutSec) {
      msg.data = "OK";
    } else if (age < kFailedTimeoutSec) {
      msg.data = "DEGRADED";
    } else {
      msg.data = "FAILED";
    }
  }

  status_pub_->publish(msg);
}

// ============================================================
//  Core filtering — ground removal + range crop + height band
// ============================================================

sensor_msgs::msg::PointCloud2 LidarPreprocessor::filter_cloud(
  const sensor_msgs::msg::PointCloud2 & input)
{
  // Validate fields
  if (!cloud_has_field(input, "x") ||
      !cloud_has_field(input, "y") ||
      !cloud_has_field(input, "z"))
  {
    RCLCPP_WARN_THROTTLE(
      get_logger(), *get_clock(), 5000,
      "Input PointCloud2 missing x/y/z fields — passing through empty cloud");
    sensor_msgs::msg::PointCloud2 empty;
    empty.header = input.header;
    empty.fields = input.fields;
    empty.point_step = input.point_step;
    empty.row_step   = 0;
    empty.height     = 1;
    empty.width      = 0;
    empty.is_dense   = true;
    return empty;
  }

  // Locate byte offsets for x, y, z
  int x_off = -1, y_off = -1, z_off = -1;
  for (const auto & f : input.fields) {
    if (f.name == "x") { x_off = static_cast<int>(f.offset); }
    if (f.name == "y") { y_off = static_cast<int>(f.offset); }
    if (f.name == "z") { z_off = static_cast<int>(f.offset); }
  }

  const size_t num_points  = static_cast<size_t>(input.width) * input.height;
  const uint32_t step      = input.point_step;

  // Pre-allocate output data (worst case: all points pass)
  std::vector<uint8_t> out_data;
  out_data.reserve(num_points * step);

  uint32_t kept = 0;

  for (size_t i = 0; i < num_points; ++i) {
    const uint8_t * ptr = &input.data[i * step];

    float x, y, z;
    std::memcpy(&x, ptr + x_off, sizeof(float));
    std::memcpy(&y, ptr + y_off, sizeof(float));
    std::memcpy(&z, ptr + z_off, sizeof(float));

    // Skip NaN / Inf
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
      continue;
    }

    // Ground removal: discard points below ground threshold
    if (z < static_cast<float>(z_ground_threshold_)) { continue; }

    // Ceiling removal: discard points above ceiling threshold
    if (z > static_cast<float>(z_ceiling_threshold_)) { continue; }

    // Range crop: compute horizontal range (XY plane)
    const double range = std::sqrt(
      static_cast<double>(x) * x + static_cast<double>(y) * y);

    if (range < min_range_ || range > max_range_) { continue; }

    // Point passes — append its bytes to output buffer
    out_data.insert(out_data.end(), ptr, ptr + step);
    ++kept;
  }

  // Build output cloud
  sensor_msgs::msg::PointCloud2 output;
  output.header     = input.header;
  output.fields     = input.fields;
  output.point_step = step;
  output.height     = 1;
  output.width      = kept;
  output.row_step   = step * kept;
  output.is_dense   = true;
  output.is_bigendian = input.is_bigendian;
  output.data       = std::move(out_data);

  RCLCPP_DEBUG(
    get_logger(),
    "Filtered %zu → %u points (%.1f%%)",
    num_points, kept,
    num_points > 0 ? (100.0 * kept / num_points) : 0.0);

  return output;
}

// ============================================================
//  Helpers
// ============================================================

bool LidarPreprocessor::cloud_has_field(
  const sensor_msgs::msg::PointCloud2 & cloud, const std::string & name)
{
  for (const auto & f : cloud.fields) {
    if (f.name == name) { return true; }
  }
  return false;
}

}  // namespace lidar_preprocessor

// ============================================================
//  main
// ============================================================

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<lidar_preprocessor::LidarPreprocessor>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
