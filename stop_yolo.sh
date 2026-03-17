#!/usr/bin/env bash
set -e

# Stop user-owned yolo_node processes gracefully then force; then sudo fallback.
PIDS=$(pgrep -u "$USER" -f 'yolo_node' || true)
if [ -n "$PIDS" ]; then
  for pid in $PIDS; do
    kill -TERM "$pid" >/dev/null 2>&1 || true
  done
  sleep 2
  PIDS=$(pgrep -u "$USER" -f 'yolo_node' || true)
  if [ -n "$PIDS" ]; then
    for pid in $PIDS; do
      kill -KILL "$pid" >/dev/null 2>&1 || true
    done
  fi
fi

# sudo fallback for remaining processes (may prompt for password)
REMAINING=$(pgrep -f 'yolo_node' || true)
if [ -n "$REMAINING" ]; then
  echo "Attempting sudo kill of remaining yolo_node PIDs: $REMAINING"
  for pid in $REMAINING; do
    sudo kill -TERM "$pid" >/dev/null 2>&1 || true
  done
  sleep 2
  REMAINING=$(pgrep -f 'yolo_node' || true)
  if [ -n "$REMAINING" ]; then
    for pid in $REMAINING; do
      sudo kill -KILL "$pid" >/dev/null 2>&1 || true
    done
  fi
fi

echo "Stopped yolo_node processes (if any)."
