#!/usr/bin/env bash
# Attach camera to follow the drone
gz topic -t /gui/camera/track -m gz.msgs.CameraTrack \
  -p "track_mode: 2, follow_target: {name: \"x500_warehouse_0\", type: 2}, follow_offset: {x: -2, y: -2, z: 2}"
echo "Camera follow: ON (x500_warehouse_0)"
