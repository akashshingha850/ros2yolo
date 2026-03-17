#!/usr/bin/env bash
set -e

# Source ROS and workspace environments if present
if [ -d /opt/ros ]; then
  DISTRO=$(ls /opt/ros | head -n1 || true)
  if [ -n "$DISTRO" ] && [ -f "/opt/ros/$DISTRO/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "/opt/ros/$DISTRO/setup.bash"
  fi
fi

if [ -f "/home/ubuntu/ros2_ws/install/setup.bash" ]; then
  # shellcheck disable=SC1091
  source "/home/ubuntu/ros2_ws/install/setup.bash"
fi

# base dir (script location)
BASEDIR="$(cd "$(dirname "$0")" && pwd)"

# activate optional venv
if [ -f "/home/ubuntu/ros2_ws/src/ros2yolo/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "/home/ubuntu/ros2_ws/src/ros2yolo/.venv/bin/activate"
fi

# Use system python but include venv site-packages so rclpy (from ROS) and
# ultralytics (from venv) can be imported. Run in foreground; no backgrounding,
# logging, or automatic stopping — you will manage that manually.
VENV_SITE="$BASEDIR/.venv/lib/python3.10/site-packages"
export PYTHONPATH="$BASEDIR:$VENV_SITE:${PYTHONPATH:-}"
python3 -u -m ros2yolo.yolo_node
