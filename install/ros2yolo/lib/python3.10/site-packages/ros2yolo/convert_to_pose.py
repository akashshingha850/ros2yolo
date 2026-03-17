import rclpy
from rclpy.node import Node
from vision_msgs.msg import Detection2DArray
from sensor_msgs.msg import CameraInfo, Image
from geometry_msgs.msg import Pose, PoseArray, PoseStamped
from cv_bridge import CvBridge
import numpy as np
import math


class ConvertToPose(Node):
    def __init__(self):
        super().__init__('convert_to_pose')

        self.declare_parameter('detections_topic', '/yolo/detections')
        self.declare_parameter('depth_topic', '/camera/depth/image_raw')

        detections_topic = self.get_parameter('detections_topic').get_parameter_value().string_value
        depth_topic = self.get_parameter('depth_topic').get_parameter_value().string_value

        self.sub_det = self.create_subscription(Detection2DArray, detections_topic, self.detections_cb, 10)
        self.sub_info = self.create_subscription(CameraInfo, '/camera/camera_info', self.info_cb, 10)
        self.sub_depth = self.create_subscription(Image, depth_topic, self.depth_cb, 10)

        self.pub_poses = self.create_publisher(PoseArray, '/yolo/waypoints', 10)

        self.bridge = CvBridge()
        self.latest_info = None
        self.latest_depth = None

    def info_cb(self, msg: CameraInfo):
        self.latest_info = msg

    def depth_cb(self, msg: Image):
        try:
            depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
            self.latest_depth = (depth, msg.header)
        except Exception as e:
            self.get_logger().error(f'Failed to convert depth image: {e}')

    def detections_cb(self, msg: Detection2DArray):
        if self.latest_info is None or self.latest_depth is None:
            return

        depth_img, depth_header = self.latest_depth
        info = self.latest_info

        fx = info.k[0]
        fy = info.k[4]
        cx = info.k[2]
        cy = info.k[5]

        pose_array = PoseArray()
        pose_array.header = msg.header

        for det in msg.detections:
            cx_img = int(det.bbox.center.x)
            cy_img = int(det.bbox.center.y)

            # check bounds
            h, w = depth_img.shape[:2]
            if cx_img < 0 or cx_img >= w or cy_img < 0 or cy_img >= h:
                continue

            z = float(depth_img[cy_img, cx_img])
            if z == 0 or not np.isfinite(z):
                continue

            x = (cx_img - cx) * z / fx
            y = (cy_img - cy) * z / fy

            p = Pose()
            p.position.x = float(x)
            p.position.y = float(y)
            p.position.z = float(z)
            # orientation: face-forward (no rotation)
            p.orientation.w = 1.0

            pose_array.poses.append(p)

        if len(pose_array.poses) > 0:
            self.pub_poses.publish(pose_array)


def main(args=None):
    rclpy.init(args=args)
    node = ConvertToPose()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()
