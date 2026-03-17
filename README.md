# ros2yolo

ROS2 node that subscribes to `/camera/image` and `/camera/camera_info`, runs YOLO inference, and publishes:

- `/yolo/image` (annotated image)
- `/yolo/detections` (JSON string with detections)

Quick start:

1. Install dependencies (preferably in your ROS2 environment):

```bash
# ros2yolo

Lightweight ROS2 node that subscribes to an image stream, runs Ultralytics YOLO inference, and publishes annotated images and Detection2DArray messages.

**Features:**
- Publishes annotated frames and detections to configurable topics.
- Uses a single, minimal configuration file: [config.yaml](config.yaml).
- Runtime overrides via ROS parameters supported.

**Requirements**
- Python 3.10+ with a virtual environment recommended
- ROS 2 (matching your distro)
- Python packages listed in requirements.txt (install into the venv)
- OpenCV and cv_bridge system packages for ROS image conversion

**Install (recommended)**
1. Create and activate a virtualenv (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# ensure system packages: sudo apt install ros-<distro>-cv-bridge python3-opencv
```

**Build**
- Use the included helper to handle common colcon/pip issues:

```bash
./build_yolo.sh
source install/setup.bash
```

Or build normally with colcon in your workspace root:

```bash
colcon build --packages-select ros2yolo
source install/setup.bash
```

**Configuration**
- The node reads settings from [config.yaml](config.yaml). The file contains two sections:
	- `predict`: model and inference tuning (`model`, `imgsz`, `conf`, `iou`, `max_det`, `device`, `classes`, ...)
	- `node`: ROS topics and visualization (`image_topic`, `output_image_topic`, `detections_topic`, `debug`, ...)
- You can also override any parameter at runtime via ROS args, for example:

```bash
ros2 run ros2ylo yolo_node --ros-args -p model:=/path/to/weights.pt -p conf:=0.8
```

**Run (examples)**
- Run in foreground using the start script (now minimal, no automatic background/logging):

```bash
./start_yolo.sh
```

- Run via ros2 directly (useful for param overrides):

```bash
ros2 run ros2yolo yolo_node --ros-args -p image_topic:=/camera/image -p model:=yolo11s-roadsight.pt
```

**Tuning to reduce false positives**
- Increase `predict.conf` (confidence) to drop weak detections (e.g., 0.7–0.9).
- Lower `predict.iou` (e.g., 0.3–0.5) to make NMS suppress overlaps more aggressively.
- Reduce `predict.max_det` to limit the number of returned boxes per frame.
- Restrict `predict.classes` to only the classes you care about.
- If false positives persist, improve the model via fine-tuning with more negative examples.

**Debugging**
- Enable `node.debug: true` in [config.yaml](config.yaml) or pass `-p debug:=true` to print effective configuration and per-frame logs.

**Troubleshooting**
- If `colcon build` fails due to setuptools editable issues, use `./build_yolo.sh` which falls back to pip editable install.
- If `config.yaml` seems ignored, ensure it's valid YAML (no tabs) and located at the package root.

**Files of interest**
- Node implementation: [ros2yolo/ros2yolo/yolo_node.py](ros2yolo/ros2yolo/yolo_node.py)
- Config: [config.yaml](config.yaml)
- Helpers: [build_yolo.sh](build_yolo.sh), [start_yolo.sh](start_yolo.sh)

If you'd like, I can add a short example showing how to run the node against a test video file and record detections.
