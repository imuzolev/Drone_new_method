// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#ifndef BARCODE_SCANNER__BARCODE_SCANNER_NODE_HPP_
#define BARCODE_SCANNER__BARCODE_SCANNER_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <std_msgs/msg/string.hpp>

#include <string>

namespace barcode_scanner
{

class BarcodeScannerNode : public rclcpp::Node
{
public:
  explicit BarcodeScannerNode(
    const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  // Callback — dispatch only (project rule)
  void on_image(sensor_msgs::msg::Image::ConstSharedPtr msg);
  void on_status_timer();

  // Core logic
  void decode_and_publish(const sensor_msgs::msg::Image & img);
  void publish_detection(
    const std::string & value,
    const std::string & format,
    double confidence);

  // Publishers
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr det_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;

  // Subscriber
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr img_sub_;

  // Timers
  rclcpp::TimerBase::SharedPtr status_timer_;

  // Parameters
  int skip_frames_;

  // State
  int frame_counter_{0};
  int total_detections_{0};
  rclcpp::Time last_image_stamp_;
  bool receiving_images_{false};
};

}  // namespace barcode_scanner

#endif  // BARCODE_SCANNER__BARCODE_SCANNER_NODE_HPP_
