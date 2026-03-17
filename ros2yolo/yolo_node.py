import os
import threading

import cv2
import numpy as np
import rclpy
import yaml
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovariance
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from vision_msgs.msg import BoundingBox2D, Detection2D, Detection2DArray
from vision_msgs.msg import ObjectHypothesis, ObjectHypothesisWithPose

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


class YoloNode(Node):
    def __init__(self):
        super().__init__('yolo_node')

        cfg = self._load_config()
        predict_cfg = cfg.get('predict', {}) or {}
        node_cfg = cfg.get('node', {}) or {}

        # Backward compatibility for old key name.
        if 'weights' in predict_cfg and 'model' not in predict_cfg:
            predict_cfg['model'] = predict_cfg['weights']

        # ROS I/O and visualization params.
        self.declare_parameter('image_topic', node_cfg.get('image_topic', '/camera/image'))
        self.declare_parameter('camera_info_topic', node_cfg.get('camera_info_topic', '/camera/camera_info'))
        self.declare_parameter('output_image_topic', node_cfg.get('output_image_topic', '/yolo/image'))
        self.declare_parameter('detections_topic', node_cfg.get('detections_topic', '/yolo/detections'))
        self.declare_parameter('debug', bool(node_cfg.get('debug', False)))
        self.declare_parameter('line_thickness', int(node_cfg.get('line_thickness', 2)))
        self.declare_parameter('hide_labels', bool(node_cfg.get('hide_labels', False)))
        self.declare_parameter('hide_conf', bool(node_cfg.get('hide_conf', False)))

        # Predict params (single, merged set).
        self.declare_parameter('model', predict_cfg.get('model', 'yolo11s-roadsight.pt'))
        self.declare_parameter('imgsz', int(predict_cfg.get('imgsz', 640)))
        self.declare_parameter('conf', float(predict_cfg.get('conf', 0.5)))
        self.declare_parameter('iou', float(predict_cfg.get('iou', 0.45)))
        self.declare_parameter('device', predict_cfg.get('device', 0))
        self.declare_parameter('max_det', int(predict_cfg.get('max_det', 1000)))
        self.declare_parameter('augment', bool(predict_cfg.get('augment', False)))
        self.declare_parameter('classes', predict_cfg.get('classes', []))
        self.declare_parameter('half', bool(predict_cfg.get('half', False)))

        image_topic = str(self.get_parameter('image_topic').value)
        camera_info_topic = str(self.get_parameter('camera_info_topic').value)
        output_image_topic = str(self.get_parameter('output_image_topic').value)
        detections_topic = str(self.get_parameter('detections_topic').value)

        self.debug = bool(self.get_parameter('debug').value)
        self.line_thickness = max(1, int(self.get_parameter('line_thickness').value))
        self.hide_labels = bool(self.get_parameter('hide_labels').value)
        self.hide_conf = bool(self.get_parameter('hide_conf').value)

        self.model_path = str(self.get_parameter('model').value)
        self.predict_args = {
            'imgsz': int(self.get_parameter('imgsz').value),
            'conf': float(self.get_parameter('conf').value),
            'iou': float(self.get_parameter('iou').value),
            'device': self.get_parameter('device').value,
            'max_det': int(self.get_parameter('max_det').value),
            'augment': bool(self.get_parameter('augment').value),
            'half': bool(self.get_parameter('half').value),
        }
        classes = self.get_parameter('classes').value
        if classes:
            self.predict_args['classes'] = list(classes)

        # Use same threshold consistently for model inference and publishing filter.
        self.confidence_threshold = float(self.predict_args['conf'])

        self.bridge = CvBridge()
        self.latest_camera_info = None
        self.lock = threading.Lock()

        self.sub_info = self.create_subscription(CameraInfo, camera_info_topic, self.camera_info_cb, 10)
        self.sub_image = self.create_subscription(Image, image_topic, self.image_cb, 1)
        self.pub_image = self.create_publisher(Image, output_image_topic, 10)
        self.pub_detections = self.create_publisher(Detection2DArray, detections_topic, 10)

        if YOLO is None:
            self.get_logger().error('ultralytics.YOLO not available. Install `ultralytics` package.')
            self.model = None
        else:
            try:
                self.model = YOLO(self.model_path)
                self.get_logger().info(f'Loaded model: {self.model_path}')
            except Exception as e:
                self.get_logger().error(f'Failed to load model {self.model_path}: {e}')
                self.model = None

        if self.debug:
            self.get_logger().info(f'Effective predict config: {self.predict_args}')
            self.get_logger().info(
                f'Node config: image_topic={image_topic}, camera_info_topic={camera_info_topic}, '
                f'output_image_topic={output_image_topic}, detections_topic={detections_topic}, '
                f'line_thickness={self.line_thickness}, hide_labels={self.hide_labels}, hide_conf={self.hide_conf}'
            )

    def _load_config(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
            with open(config_path, 'r', encoding='utf-8') as cf:
                return yaml.safe_load(cf) or {}
        except Exception as e:
            self.get_logger().warn(f'Failed to load config.yaml, using defaults: {e}')
            return {}

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

        if self.debug:
            h, w = cv_image.shape[:2]
            self.get_logger().info(f'image_cb: frame_id={msg.header.frame_id} size={w}x{h}')

        try:
            results = self.model(cv_image, **self.predict_args)
        except Exception as e:
            self.get_logger().error(f'Inference error: {e}')
            return

        detections = []
        annotated = cv_image.copy()

        res = results[0] if isinstance(results, (list, tuple)) else results
        boxes = getattr(res, 'boxes', None)
        names = getattr(self.model, 'names', {}) if self.model is not None else {}

        if self.debug:
            num_boxes = len(boxes) if boxes is not None else 0
            self.get_logger().info(f'Inference returned {num_boxes} boxes')

        if boxes is not None:
            for i, box in enumerate(boxes):
                xyxy = box.xyxy[0].cpu().numpy() if hasattr(box.xyxy, 'cpu') else np.array(box.xyxy[0])
                x1, y1, x2, y2 = [int(x) for x in xyxy]
                conf = float(box.conf[0]) if hasattr(box, 'conf') else float(box.conf)

                if self.debug:
                    self.get_logger().info(f'Box {i}: raw_conf={conf:.3f} bbox=({x1},{y1},{x2},{y2})')

                if conf < self.confidence_threshold:
                    continue

                cls = int(box.cls[0]) if hasattr(box, 'cls') else int(box.cls)
                label = names.get(cls, str(cls))
                detections.append({'label': label, 'confidence': conf, 'bbox': [x1, y1, x2, y2]})

                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), self.line_thickness)
                if not self.hide_labels:
                    text = label if self.hide_conf else f'{label} {conf:.2f}'
                    cv2.putText(
                        annotated,
                        text,
                        (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1,
                    )

        try:
            out_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
            out_msg.header = msg.header
            self.pub_image.publish(out_msg)
        except Exception as e:
            self.get_logger().error(f'Failed to publish annotated image: {e}')

        try:
            det_array = Detection2DArray()
            det_array.header = msg.header
            for d in detections:
                det = Detection2D()
                x1, y1, x2, y2 = d['bbox']

                bbox = BoundingBox2D()
                bbox.center.position.x = float((x1 + x2) / 2.0)
                bbox.center.position.y = float((y1 + y2) / 2.0)
                bbox.center.theta = 0.0
                bbox.size_x = float(x2 - x1)
                bbox.size_y = float(y2 - y1)
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
