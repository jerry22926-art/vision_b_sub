import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Vector3


class SubGazeErrorNode(Node):
    def __init__(self):
        super().__init__('sub_gaze_error_node')

        self.declare_parameter('input_topic', '/gaze_error')
        self.declare_parameter('output_topic', '/gaze_error_cmd')

        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value

        self.publisher = self.create_publisher(Vector3, output_topic, 10)
        self.subscription = self.create_subscription(
            Vector3,
            input_topic,
            self.gaze_error_callback,
            10,
        )

        self.get_logger().info(
            f'Subscribing {input_topic} and publishing received gaze error to {output_topic}'
        )

    def gaze_error_callback(self, msg):
        cmd_msg = Vector3()
        cmd_msg.x = msg.x
        cmd_msg.y = msg.y
        cmd_msg.z = msg.z

        self.publisher.publish(cmd_msg)
        self.get_logger().info(
            f'Published /gaze_error_cmd x: {cmd_msg.x:.4f}, y: {cmd_msg.y:.4f}, z: {cmd_msg.z:.4f}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = SubGazeErrorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
