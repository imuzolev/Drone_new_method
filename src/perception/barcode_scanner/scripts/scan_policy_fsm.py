#!/usr/bin/env python3
# Copyright 2024 Drone New Method Project
# SPDX-License-Identifier: Apache-2.0

"""Scan Policy FSM — barcode scanning workflow manager (Section 5.2).

States
------
APPROACH   → flying toward rack, waiting for rack_follower to stabilize
SCANNING   → moving along aisle at base_speed, reading barcodes
HOVER_SCAN → hovering for re-read of a bad slot
ADJUSTING  → shifting target distance ±adjust_step_m
DONE       → aisle pass complete
"""

from __future__ import annotations

import json
from enum import Enum, auto
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped, TwistStamped
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import Float32, String

from barcode_scanner.slot_kpi import SlotKPI, SlotKPIWriter


# ── FSM states ──────────────────────────────────────────────────────────────

class State(Enum):
    APPROACH = auto()
    SCANNING = auto()
    HOVER_SCAN = auto()
    ADJUSTING = auto()
    DONE = auto()


# ── Node ────────────────────────────────────────────────────────────────────

class ScanPolicyFSM(Node):

    def __init__(self) -> None:
        super().__init__("scan_policy_fsm_node")

        # ── parameters (all from YAML) ──────────────────────────────────
        self._p_quality_thr: float = self.declare_parameter(
            "scan_quality_threshold", 0.6).value
        self._p_max_attempts: int = self.declare_parameter(
            "max_attempts", 6).value
        self._p_hover_attempts: int = self.declare_parameter(
            "hover_attempts_before_adjust", 3).value
        self._p_hover_dur: float = self.declare_parameter(
            "hover_duration_sec", 2.0).value
        self._p_adjust_step: float = self.declare_parameter(
            "adjust_step_m", 0.1).value
        self._p_aisle_end: float = self.declare_parameter(
            "aisle_end_x", 9.0).value
        self._p_aisle_start: float = self.declare_parameter(
            "aisle_start_x", -9.0).value
        self._p_slot_width: float = self.declare_parameter(
            "slot_width_m", 1.5).value
        self._p_aisle_id: str = self.declare_parameter(
            "aisle_id", "aisle_0").value
        self._p_stable_dur: float = self.declare_parameter(
            "stable_duration_sec", 1.0).value
        self._p_min_dwell: float = self.declare_parameter(
            "min_slot_dwell_sec", 1.0).value
        fsm_hz: float = self.declare_parameter("fsm_rate_hz", 10.0).value
        kpi_dir: str = self.declare_parameter(
            "kpi_output_dir", "/tmp/Drone_new_method/kpi").value

        # ── QoS ─────────────────────────────────────────────────────────
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST, depth=5)
        cmd_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST, depth=10)
        status_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST, depth=1)

        # ── publishers ──────────────────────────────────────────────────
        self._pub_quality = self.create_publisher(
            Float32, "/drone/perception/barcode/scan_quality", cmd_qos)
        self._pub_hover_vel = self.create_publisher(
            TwistStamped, "/drone/perception/barcode/cmd_vel", cmd_qos)
        self._pub_status = self.create_publisher(
            String, "/drone/perception/barcode/status", status_qos)
        self._pub_adjust = self.create_publisher(
            Float32, "/drone/perception/barcode/target_distance_adjust", cmd_qos)

        # ── subscribers (callbacks = dispatch only) ─────────────────────
        self.create_subscription(
            String, "/drone/perception/barcode/detections",
            self._on_detection, sensor_qos)
        self.create_subscription(
            String, "/drone/control/rack_follower/status",
            self._on_rack_status, sensor_qos)
        self.create_subscription(
            Float32, "/drone/control/rack_follower/wall_distance",
            self._on_wall_dist, sensor_qos)
        self.create_subscription(
            PoseWithCovarianceStamped, "/drone/slam/pose",
            self._on_pose, sensor_qos)

        # ── timers ──────────────────────────────────────────────────────
        self.create_timer(1.0 / fsm_hz, self._tick)
        self.create_timer(0.5, self._publish_status)

        # ── runtime state ───────────────────────────────────────────────
        self._state = State.APPROACH
        self._rack_status: str = "FAILED"
        self._rack_stable_since: Optional[float] = None
        self._wall_dist: float = float("inf")
        self._drone_x: float = self._p_aisle_start

        self._slot_idx: int = -1
        self._slot_attempts: int = 0
        self._slot_hover_attempts: int = 0
        self._slot_start_t: float = 0.0
        self._slot_resolved: bool = False

        self._last_det: Optional[dict] = None
        self._det_fresh: bool = False
        self._best_det: Optional[dict] = None

        self._hover_start_t: float = 0.0
        self._adjust_sign: int = 1

        self._kpi = SlotKPIWriter(kpi_dir)

        self.get_logger().info(
            f"ScanPolicyFSM started — quality_thr={self._p_quality_thr} "
            f"max_attempts={self._p_max_attempts} aisle={self._p_aisle_id} "
            f"KPI → {self._kpi.filepath}")

    # ====================================================================
    #  Callbacks — dispatch only (project rule)
    # ====================================================================

    def _on_detection(self, msg: String) -> None:
        try:
            self._last_det = json.loads(msg.data)
            self._det_fresh = True
        except (json.JSONDecodeError, TypeError):
            pass

    def _on_rack_status(self, msg: String) -> None:
        prev = self._rack_status
        self._rack_status = msg.data
        if prev != "OK" and msg.data == "OK":
            self._rack_stable_since = self._now_sec()
        elif msg.data != "OK":
            self._rack_stable_since = None

    def _on_wall_dist(self, msg: Float32) -> None:
        self._wall_dist = msg.data

    def _on_pose(self, msg: PoseWithCovarianceStamped) -> None:
        self._drone_x = msg.pose.pose.position.x

    def _publish_status(self) -> None:
        msg = String()
        msg.data = self._state.name
        self._pub_status.publish(msg)

    # ====================================================================
    #  FSM tick
    # ====================================================================

    def _tick(self) -> None:
        handler = {
            State.APPROACH: self._tick_approach,
            State.SCANNING: self._tick_scanning,
            State.HOVER_SCAN: self._tick_hover,
            State.ADJUSTING: self._tick_adjusting,
        }.get(self._state)
        if handler:
            handler()

    # ── APPROACH ────────────────────────────────────────────────────────

    def _tick_approach(self) -> None:
        if self._rack_stable_since is None:
            return
        if self._now_sec() - self._rack_stable_since >= self._p_stable_dur:
            self.get_logger().info("Rack follower stable → SCANNING")
            self._state = State.SCANNING
            self._enter_slot(self._pos_to_slot(self._drone_x))

    # ── SCANNING ────────────────────────────────────────────────────────

    def _tick_scanning(self) -> None:
        # Aisle end check
        if self._drone_x >= self._p_aisle_end:
            self._finalize_slot(
                "SUCCESS" if self._best_det else "PARTIAL")
            self._go_done()
            return

        # Slot tracking
        new_slot = self._pos_to_slot(self._drone_x)
        if new_slot != self._slot_idx and new_slot >= 0:
            if self._slot_idx >= 0:
                status = "SUCCESS" if self._best_det else "PARTIAL"
                self._finalize_slot(status)
            self._enter_slot(new_slot)

        # Evaluate quality
        quality = self._eval_quality()
        self._pub_quality_msg(quality)

        # Trigger HOVER_SCAN after dwelling with no good read
        time_in_slot = self._now_sec() - self._slot_start_t
        if (not self._slot_resolved
                and time_in_slot > self._p_min_dwell
                and quality < self._p_quality_thr
                and self._best_det is None
                and self._slot_idx >= 0):
            self.get_logger().info(
                f"Slot {self._slot_idx}: quality {quality:.2f} "
                f"< {self._p_quality_thr} → HOVER_SCAN")
            self._state = State.HOVER_SCAN
            self._hover_start_t = self._now_sec()
            self._slot_hover_attempts = 0

    # ── HOVER_SCAN ──────────────────────────────────────────────────────

    def _tick_hover(self) -> None:
        self._pub_hover_zero()

        quality = self._eval_quality()
        self._pub_quality_msg(quality)

        if quality >= self._p_quality_thr:
            self.get_logger().info("Good read during hover → SCANNING")
            self._slot_resolved = True
            self._state = State.SCANNING
            return

        elapsed = self._now_sec() - self._hover_start_t
        if elapsed < self._p_hover_dur:
            return

        self._slot_hover_attempts += 1
        self._slot_attempts += 1

        if self._slot_attempts >= self._p_max_attempts:
            self.get_logger().warn(
                f"Slot {self._slot_idx}: {self._p_max_attempts} "
                f"attempts exhausted → MANUAL_REVIEW")
            self._finalize_slot("MANUAL_REVIEW")
            self._slot_resolved = True
            self._state = State.SCANNING
            return

        if self._slot_hover_attempts >= self._p_hover_attempts:
            self.get_logger().info("Hover attempts spent → ADJUSTING")
            self._state = State.ADJUSTING
            self._adjust_sign *= -1
            return

        self._hover_start_t = self._now_sec()

    # ── ADJUSTING ───────────────────────────────────────────────────────

    def _tick_adjusting(self) -> None:
        self._pub_hover_zero()

        adj = Float32()
        adj.data = self._p_adjust_step * self._adjust_sign
        self._pub_adjust.publish(adj)

        self.get_logger().info(
            f"Distance adjust {adj.data:+.2f}m → back to HOVER_SCAN")
        self._state = State.HOVER_SCAN
        self._hover_start_t = self._now_sec()
        self._slot_hover_attempts = 0

    # ====================================================================
    #  Slot management
    # ====================================================================

    def _enter_slot(self, idx: int) -> None:
        self._slot_idx = idx
        self._slot_attempts = 0
        self._slot_hover_attempts = 0
        self._slot_start_t = self._now_sec()
        self._slot_resolved = False
        self._last_det = None
        self._det_fresh = False
        self._best_det = None
        self.get_logger().debug(f"Entered slot {idx}")

    def _finalize_slot(self, status: str) -> None:
        if self._slot_idx < 0:
            return
        time_spent = self._now_sec() - self._slot_start_t
        slot_id = f"L_{self._slot_idx + 1}"

        bc_val = self._best_det.get("barcode_value", "") if self._best_det else ""
        conf = self._best_det.get("confidence", 0.0) if self._best_det else 0.0
        success = conf >= self._p_quality_thr

        kpi = SlotKPI(
            slot_id=slot_id,
            aisle_id=self._p_aisle_id,
            attempt_count=max(self._slot_attempts, 1),
            success=success,
            scan_quality=conf,
            time_spent_sec=round(time_spent, 2),
            barcode_value=bc_val,
            confidence=conf,
            status=status,
        )
        self._kpi.write(kpi)
        self.get_logger().info(
            f"Slot {slot_id}: {status}  conf={conf:.2f}  "
            f"attempts={kpi.attempt_count}  t={kpi.time_spent_sec:.1f}s")

    def _go_done(self) -> None:
        self._state = State.DONE
        self.get_logger().info(
            f"Aisle {self._p_aisle_id} DONE — KPI → {self._kpi.filepath}")

    # ====================================================================
    #  Helpers
    # ====================================================================

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def _pos_to_slot(self, x: float) -> int:
        idx = int((x - self._p_aisle_start) / self._p_slot_width)
        return max(0, min(idx, 11))

    def _eval_quality(self) -> float:
        if not self._det_fresh or self._last_det is None:
            return 0.0
        self._det_fresh = False
        conf = float(self._last_det.get("confidence", 0.0))
        val = self._last_det.get("barcode_value", "")
        if conf > 0.0 and val:
            if (self._best_det is None
                    or conf > self._best_det.get("confidence", 0.0)):
                self._best_det = dict(self._last_det)
        return conf

    def _pub_quality_msg(self, quality: float) -> None:
        msg = Float32()
        msg.data = quality
        self._pub_quality.publish(msg)

    def _pub_hover_zero(self) -> None:
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        self._pub_hover_vel.publish(msg)

    def destroy_node(self) -> None:
        self._kpi.close()
        super().destroy_node()


# ── entry point ─────────────────────────────────────────────────────────────

def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ScanPolicyFSM()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
