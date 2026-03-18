FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# system deps for OpenCV/ultralytics
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    python3-venv python3-pip python3-opencv libgl1 libglib2.0-0 ffmpeg ca-certificates \
    ros-humble-cv-bridge ros-humble-vision-msgs \
    ros-humble-ros2cli ros-humble-ros2topic \
  && rm -rf /var/lib/apt/lists/*

# Make `ros2` available in exec/interactive shells: add profile and source it
RUN printf '#!/bin/sh\nif [ -f /opt/ros/humble/setup.bash ]; then\n  . /opt/ros/humble/setup.bash\nfi\nif [ -f /home/ubuntu/ros2_ws/install/setup.bash ]; then\n  . /home/ubuntu/ros2_ws/install/setup.bash\nfi\n' > /etc/profile.d/ros2.sh \
  && chmod +x /etc/profile.d/ros2.sh \
  && if [ -f /etc/bash.bashrc ]; then printf '\n# Source ROS2 setup for interactive shells\nif [ -f /etc/profile.d/ros2.sh ]; then\n  . /etc/profile.d/ros2.sh\nfi\n' >> /etc/bash.bashrc; fi

# Provide a wrapper so `/usr/local/bin/ros2` works even when shell startup files
# aren't sourced (e.g. `docker exec ros2 ...`). The wrapper sources the ROS
# environment and execs the real `ros2` script.
RUN printf '#!/bin/bash\nif [ -f /opt/ros/humble/setup.bash ]; then\n  . /opt/ros/humble/setup.bash\nfi\nif [ -f /home/ubuntu/ros2_ws/install/setup.bash ]; then\n  . /home/ubuntu/ros2_ws/install/setup.bash\nfi\nexec /opt/ros/humble/bin/ros2 "$@"\n' > /usr/local/bin/ros2 \
  && chmod +x /usr/local/bin/ros2

WORKDIR /workspace/ros2yolo

# copy project
COPY . /workspace/ros2yolo

# create venv and install python deps
RUN python3 -m pip install --upgrade pip setuptools wheel \
  && if [ -f requirements.txt ]; then python3 -m pip install --no-cache-dir -r requirements.txt; fi \
  && python3 -m pip install --no-cache-dir -e .

RUN chmod +x /workspace/ros2yolo/start_yolo.sh || true

ENTRYPOINT ["/workspace/ros2yolo/start_yolo.sh"]
