#!/usr/bin/env python3
"""Compute rack_follower lateral error RMS from a rosbag2 recording."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def iter_topic_values(
    bag_path: Path,
    topic_name: str,
) -> Iterable[float]:
    """Yield finite Float32 values from a rosbag2 bag for the given topic."""
    storage_options = rosbag2_py.StorageOptions(
        uri=str(bag_path),
        storage_id="sqlite3",
    )
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )

    reader = rosbag2_py.SequentialReader()
    reader.open(storage_options, converter_options)

    topic_types = {
        topic.name: topic.type
        for topic in reader.get_all_topics_and_types()
    }
    if topic_name not in topic_types:
        raise ValueError(f"Topic not found in bag: {topic_name}")

    msg_type = get_message(topic_types[topic_name])

    while reader.has_next():
        current_topic, data, _timestamp = reader.read_next()
        if current_topic != topic_name:
            continue
        msg = deserialize_message(data, msg_type)
        value = float(msg.data)
        if math.isfinite(value):
            yield value


def compute_rms(values: list[float]) -> float:
    if not values:
        raise ValueError("No finite samples found.")
    return math.sqrt(sum(v * v for v in values) / len(values))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute lateral_error RMS from rosbag2.",
    )
    parser.add_argument("bag_path", help="Path to rosbag2 directory")
    parser.add_argument(
        "--topic",
        default="/drone/control/rack_follower/lateral_error",
        help="Float32 topic to analyze",
    )
    parser.add_argument(
        "--max-rms",
        type=float,
        default=0.10,
        help="Acceptance threshold in meters",
    )
    args = parser.parse_args()

    bag_path = Path(args.bag_path)
    values = list(iter_topic_values(bag_path, args.topic))
    rms = compute_rms(values)
    max_abs = max(abs(v) for v in values)

    print(f"bag: {bag_path}")
    print(f"topic: {args.topic}")
    print(f"samples: {len(values)}")
    print(f"lateral_error_rms_m: {rms:.4f}")
    print(f"max_abs_error_m: {max_abs:.4f}")
    print(f"acceptance_lt_{args.max_rms:.2f}m: {'PASS' if rms < args.max_rms else 'FAIL'}")


if __name__ == "__main__":
    main()
