// Copyright 2024 Drone New Method Project
// SPDX-License-Identifier: Apache-2.0

#include "barcode_scanner/barcode_scanner_node.hpp"

#include <cv_bridge/cv_bridge.h>
#include <opencv2/imgproc.hpp>

#ifdef HAS_ZXING
#include <ZXing/ReadBarcode.h>
#endif

#include <sstream>
#include <string>

namespace barcode_scanner
{

BarcodeScannerNode::BarcodeScannerNode(const rclcpp::NodeOptions & options)
: Node("barcode_scanner_node", options)
{
  skip_frames_ = declare_parameter("skip_frames", 0);
  auto camera_topic = declare_parameter(
    "camera_topic", std::string("/drone/camera/image_raw"));

  // QoS — sensor input, reliable output
  auto sensor_qos = rclcpp::QoS(rclcpp::KeepLast(5))
    .best_effort().durability_volatile();
  auto cmd_qos = rclcpp::QoS(rclcpp::KeepLast(10))
    .reliable().durability_volatile();
  auto status_qos = rclcpp::QoS(rclcpp::KeepLast(1))
    .reliable().transient_local();

  det_pub_ = create_publisher<std_msgs::msg::String>(
    "/drone/perception/barcode/detections", cmd_qos);
  status_pub_ = create_publisher<std_msgs::msg::String>(
    "/barcode_scanner_node/status", status_qos);

  img_sub_ = create_subscription<sensor_msgs::msg::Image>(
    camera_topic, sensor_qos,
    [this](sensor_msgs::msg::Image::ConstSharedPtr msg) {
      on_image(std::move(msg));
    });

  status_timer_ = create_wall_timer(
    std::chrono::milliseconds(500),
    std::bind(&BarcodeScannerNode::on_status_timer, this));

  last_image_stamp_ = now();

#ifdef HAS_ZXING
  RCLCPP_INFO(get_logger(),
    "BarcodeScannerNode started — ZXing ENABLED, topic=%s, skip=%d",
    camera_topic.c_str(), skip_frames_);
#else
  RCLCPP_WARN(get_logger(),
    "BarcodeScannerNode started — ZXing DISABLED (built without), topic=%s",
    camera_topic.c_str());
#endif
}

// ── Callbacks ──────────────────────────────────────────────────────────────

void BarcodeScannerNode::on_image(
  sensor_msgs::msg::Image::ConstSharedPtr msg)
{
  receiving_images_ = true;
  last_image_stamp_ = now();

  if (skip_frames_ > 0 && (frame_counter_++ % (skip_frames_ + 1)) != 0) {
    return;
  }

  decode_and_publish(*msg);
}

void BarcodeScannerNode::on_status_timer()
{
  auto elapsed_ms =
    std::chrono::duration_cast<std::chrono::milliseconds>(
      (now() - last_image_stamp_).to_chrono<std::chrono::nanoseconds>())
    .count();

  std_msgs::msg::String status;
  if (!receiving_images_ || elapsed_ms > 2000) {
    status.data = "FAILED";
  } else {
    status.data = "OK";
  }
  status_pub_->publish(status);
}

// ── Core decode logic ──────────────────────────────────────────────────────

void BarcodeScannerNode::decode_and_publish(
  const sensor_msgs::msg::Image & img)
{
  // Convert to grayscale via cv_bridge
  cv_bridge::CvImageConstPtr cv_ptr;
  try {
    cv_ptr = cv_bridge::toCvShare(
      std::make_shared<sensor_msgs::msg::Image>(img), "mono8");
  } catch (const cv_bridge::Exception & e) {
    RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000,
      "cv_bridge failed: %s", e.what());
    publish_detection("", "", 0.0);
    return;
  }

#ifdef HAS_ZXING
  const auto & gray = cv_ptr->image;

  ZXing::ImageView view(
    gray.data,
    gray.cols,
    gray.rows,
    ZXing::ImageFormat::Lum,
    static_cast<int>(gray.step));

  auto results = ZXing::ReadBarcodes(view);

  if (results.empty()) {
    publish_detection("", "", 0.0);
    return;
  }

  for (const auto & r : results) {
    publish_detection(r.text(), ZXing::ToString(r.format()), 1.0);
    ++total_detections_;
  }
#else
  // No ZXing — always report "no barcode"
  publish_detection("", "", 0.0);
#endif
}

void BarcodeScannerNode::publish_detection(
  const std::string & value,
  const std::string & format,
  double confidence)
{
  std::ostringstream oss;
  oss << R"({"barcode_value":")" << value
      << R"(","format":")" << format
      << R"(","confidence":)" << confidence << "}";

  std_msgs::msg::String msg;
  msg.data = oss.str();
  det_pub_->publish(msg);
}

}  // namespace barcode_scanner

// ── main ───────────────────────────────────────────────────────────────────

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<barcode_scanner::BarcodeScannerNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
