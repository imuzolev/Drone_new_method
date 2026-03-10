#!/usr/bin/env bash
# Sends CameraTrack NONE to release camera from follow mode
for i in 1 2 3 4 5; do
    gz topic -t /gui/camera/track -m gz.msgs.CameraTrack -p "track_mode: 0"
    sleep 0.3
done
echo "Sent 5 x track_mode:NONE to /gui/camera/track"
