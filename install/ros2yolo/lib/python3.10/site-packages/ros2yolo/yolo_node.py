import json
import threading
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String
from vision_msgs.msg import Detection2D, Detection2DArray, BoundingBox2D
from vision_msgs.msg import ObjectHypothesis, ObjectHypothesisWithPose
from geometry_msgs.msg import PoseStamped, PoseWithCovariance
from cv_bridge import CvBridge
import cv2
import os
import yaml

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


class YoloNode(Node):
    def __init__(self):
        super().__init__('yolo_node')
        # load defaults from config.yaml (package root)
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
            with open(config_path, 'r') as cf:
                cfg = yaml.safe_load(cf) or {}
        except Exception:
            cfg = {}

        self.declare_parameter('image_topic', cfg.get('image_topic', '/camera/image'))
        self.declare_parameter('camera_info_topic', cfg.get('camera_info_topic', '/camera/camera_info'))
        self.declare_parameter('model', cfg.get('model', 'yolo11s-roadsight.pt'))
        self.declare_parameter('confidence_threshold', cfg.get('confidence_threshold', 0.5))
        self.declare_parameter('debug', cfg.get('debug', False))

        image_topic = self.get_parameter('image_topic').get_parameter_value().string_value
        camera_info_topic = self.get_parameter('camera_info_topic').get_parameter_value().string_value
        model_path = self.get_parameter('model').get_parameter_value().string_value

        self.bridge = CvBridge()
        self.latest_camera_info = None

        self.sub_info = self.create_subscription(CameraInfo, camera_info_topic, self.camera_info_cb, 10)
        self.sub_image = self.create_subscription(Image, image_topic, self.image_cb, 1)

        self.pub_image = self.create_publisher(Image, '/yolo/image', 10)
        self.pub_detections = self.create_publisher(Detection2DArray, '/yolo/detections', 10)

        if YOLO is None:
            self.get_logger().error('ultralytics.YOLO not available. Install `ultralytics` package.')
            self.model = None
        else:
            try:
                self.model = YOLO(model_path)
                self.get_logger().info(f'Loaded model: {model_path}')
            except Exception as e:
                self.get_logger().error(f'Failed to load model {model_path}: {e}')
                self.model = None

        # confidence threshold for published detections
        try:
            self.confidence_threshold = float(self.get_parameter('confidence_threshold').get_parameter_value().double_value)
        except Exception:
            # fallback if parameter type isn't double
            self.confidence_threshold = float(self.get_parameter('confidence_threshold').get_parameter_value().integer_value or 0.5)

        try:
            self.debug = bool(self.get_parameter('debug').get_parameter_value().bool_value)
        except Exception:
            self.debug = False

        self.lock = threading.Lock()

    def camera_info_cb(self, msg: CameraInfo):
        with self.lock:
            self.latest_camera_info = msg

    def image_cb(self, msg: Image):
        if self.model is None:
            return

        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f'CvBridge conversion error: {e}')
            return

        if getattr(self, 'debug', False):
            try:
                h, w = cv_image.shape[:2]
            except Exception:
                h = w = 0
            self.get_logger().info(f'image_cb: frame_id={msg.header.frame_id} size={w}x{h}')

        # Run inference
        try:
            if getattr(self, 'debug', False):
                self.get_logger().info('Running inference...')
            results = self.model(cv_image)
        except Exception as e:
            self.get_logger().error(f'Inference error: {e}')
            return

        detections = []
        annotated = cv_image.copy()

        # ultralytics returns a Results object or list; handle accordingly
        res = results[0] if isinstance(results, (list, tuple)) else results

        boxes = getattr(res, 'boxes', None)
        names = getattr(self.model, 'names', {}) if self.model is not None else {}

        if getattr(self, 'debug', False):
            num_boxes = len(boxes) if boxes is not None else 0
            self.get_logger().info(f'Inference returned {num_boxes} boxes')

        if boxes is not None:
            for i, box in enumerate(boxes):
                # box.xyxy, box.conf, box.cls
                xyxy = box.xyxy[0].cpu().numpy() if hasattr(box.xyxy, 'cpu') else np.array(box.xyxy[0])
                x1, y1, x2, y2 = [int(x) for x in xyxy]
                conf = float(box.conf[0]) if hasattr(box, 'conf') else float(box.conf)
                if getattr(self, 'debug', False):
                    self.get_logger().info(f'Box {i}: raw_conf={conf:.3f} bbox=({x1},{y1},{x2},{y2})')
                # filter by confidence threshold
                if conf < self.confidence_threshold:
                    if getattr(self, 'debug', False):
                        self.get_logger().info(f'Box {i} filtered (conf {conf:.3f} < {self.confidence_threshold})')
                    continue
                cls = int(box.cls[0]) if hasattr(box, 'cls') else int(box.cls)
                label = names.get(cls, str(cls))

                if getattr(self, 'debug', False):
                    self.get_logger().info(f'Publishing detection: label={label} conf={conf:.3f}')

                detections.append({'label': label, 'confidence': conf, 'bbox': [x1, y1, x2, y2]})

                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(annotated, f'{label} {conf:.2f}', (x1, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Publish annotated image
        try:
            out_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
            out_msg.header = msg.header
            self.pub_image.publish(out_msg)
        except Exception as e:
            self.get_logger().error(f'Failed to publish annotated image: {e}')

        # Publish detections as vision_msgs/Detection2DArray
        try:
            det_array = Detection2DArray()
            det_array.header = msg.header
            for d in detections:
                det = Detection2D()
                # bbox center and size
                x1, y1, x2, y2 = d['bbox']
                cx = float((x1 + x2) / 2.0)
                cy = float((y1 + y2) / 2.0)
                w = float(x2 - x1)
                h = float(y2 - y1)
                bbox = BoundingBox2D()
                bbox.center.position.x = cx
                bbox.center.position.y = cy
                bbox.center.theta = 0.0
                bbox.size_x = w
                bbox.size_y = h
                det.bbox = bbox

                hyp = ObjectHypothesis()
                hyp.class_id = d['label']
                hyp.score = float(d['confidence'])

                ohwp = ObjectHypothesisWithPose()
                ohwp.hypothesis = hyp
                ohwp.pose = PoseWithCovariance()
                det.results = [ohwp]

                det_array.detections.append(det)

            self.pub_detections.publish(det_array)
        except Exception as e:
            self.get_logger().error(f'Failed to publish Detection2DArray: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = YoloNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
