import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from geometry_msgs.msg import PointStamped


class PinkBallDetector(Node):
    def __init__(self):
        super().__init__('pink_ball_detector')
        self.bridge = CvBridge()
        self.position_publisher = self.create_publisher(PointStamped, "/pink_ball/center_px", 10)
        self.subscription = self.create_subscription(
            Image, '/camera/image', self.on_image, 10
        )

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([140, 70, 70]), np.array([179, 255, 255]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 30:
                (x, y), radius = cv2.minEnclosingCircle(c)
                cv2.circle(frame, (round(x), round(y)), round(radius), (0, 255, 0), 2)
                cv2.putText(frame, 'Pink Ball', (round(x), max(20, round(y)-15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                position = PointStamped()
                position.header = msg.header
                position.point.x = float(x)
                position.point.y = float(y)
                position.point.z = float(radius)  # radius in pixels
                self.position_publisher.publish(position)
                self.get_logger().info(f'Pink ball: x={x:.0f}, y={y:.0f}', throttle_duration_sec=2.0)
        cv2.imshow('Pink Ball Detection', frame)
        cv2.waitKey(1)


def main():
    rclpy.init()
    node = PinkBallDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        cv2.destroyAllWindows()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
