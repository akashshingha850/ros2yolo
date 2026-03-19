FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    python3-pip \
    ca-certificates \
    libgl1 libglib2.0-0 \
    ros-humble-cv-bridge ros-humble-vision-msgs \
  && rm -rf /var/lib/apt/lists/*

# Optional packages (commented out). Uncomment when you need them:
# RUN apt-get update \
#   && apt-get install -y --no-install-recommends \
#     python3-venv python3-opencv libgl1 libglib2.0-0 ffmpeg \
#     ros-humble-ros2cli ros-humble-ros2topic \
#   && rm -rf /var/lib/apt/lists/*

# Small helper to source ROS2 in interactive shells (harmless to keep).
RUN printf '#!/bin/sh\nif [ -f /opt/ros/humble/setup.bash ]; then\n  . /opt/ros/humble/setup.bash\nfi\nif [ -f /home/ubuntu/ros2_ws/install/setup.bash ]; then\n  . /home/ubuntu/ros2_ws/install/setup.bash\nfi\n' > /etc/profile.d/ros2.sh \
  && chmod +x /etc/profile.d/ros2.sh

# Wrapper for `ros2` so it works even when shell startup files aren't
# sourced (e.g. `docker exec ros2 ...`). Keep — it's small and convenient.
RUN printf '#!/bin/bash\nif [ -f /opt/ros/humble/setup.bash ]; then\n  . /opt/ros/humble/setup.bash\nfi\nif [ -f /home/ubuntu/ros2_ws/install/setup.bash ]; then\n  . /home/ubuntu/ros2_ws/install/setup.bash\nfi\nexec /opt/ros/humble/bin/ros2 "$@"\n' > /usr/local/bin/ros2 \
  && chmod +x /usr/local/bin/ros2

WORKDIR /workspace/ros2yolo

# Copy project and install Python deps (requirements.txt / editable install).
COPY . /workspace/ros2yolo

RUN python3 -m pip install --upgrade pip setuptools wheel \
  && if [ -f requirements.txt ]; then python3 -m pip install --no-cache-dir -r requirements.txt; fi \
  && python3 -m pip install --no-cache-dir -e .

RUN chmod +x /workspace/ros2yolo/start_yolo.sh || true

ENTRYPOINT ["/workspace/ros2yolo/start_yolo.sh"]
