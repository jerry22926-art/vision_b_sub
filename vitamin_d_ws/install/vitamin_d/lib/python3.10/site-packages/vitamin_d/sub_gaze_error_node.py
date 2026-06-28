import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Vector3


class ButterworthLowPassFilter:
    """Second-order Butterworth low-pass filter for a scalar signal."""

    def __init__(self, cutoff_frequency, sampling_frequency):
        nyquist_frequency = sampling_frequency / 2.0
        if cutoff_frequency <= 0.0:
            raise ValueError('cutoff_frequency must be greater than zero')
        if cutoff_frequency >= nyquist_frequency:
            raise ValueError(
                'cutoff_frequency must be less than half the sampling_frequency'
            )

        k = math.tan(math.pi * cutoff_frequency / sampling_frequency)
        norm = 1.0 / (1.0 + math.sqrt(2.0) * k + k * k)

        self.b0 = k * k * norm
        self.b1 = 2.0 * self.b0
        self.b2 = self.b0
        self.a1 = 2.0 * (k * k - 1.0) * norm
        self.a2 = (1.0 - math.sqrt(2.0) * k + k * k) * norm

        self.initialized = False
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    def update(self, value):
        value = float(value)

        # Start from the first received value to avoid a zero-to-signal transient.
        if not self.initialized:
            self.x1 = value
            self.x2 = value
            self.y1 = value
            self.y2 = value
            self.initialized = True

        filtered_value = (
            self.b0 * value
            + self.b1 * self.x1
            + self.b2 * self.x2
            - self.a1 * self.y1
            - self.a2 * self.y2
        )

        self.x2 = self.x1
        self.x1 = value
        self.y2 = self.y1
        self.y1 = filtered_value
        return filtered_value


class SubGazeErrorNode(Node):
    def __init__(self):
        super().__init__('sub_gaze_error_node')

        self.declare_parameter('input_topic', '/gaze_error')
        self.declare_parameter('output_topic', '/gaze_error_cmd')
        self.declare_parameter('sampling_frequency', 30.0)
        self.declare_parameter('cutoff_frequency', 2.0)

        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value
        sampling_frequency = float(
            self.get_parameter('sampling_frequency').value
        )
        cutoff_frequency = float(
            self.get_parameter('cutoff_frequency').value
        )

        self.x_filter = ButterworthLowPassFilter(
            cutoff_frequency,
            sampling_frequency,
        )
        self.y_filter = ButterworthLowPassFilter(
            cutoff_frequency,
            sampling_frequency,
        )

        self.publisher = self.create_publisher(Vector3, output_topic, 10)
        self.subscription = self.create_subscription(
            Vector3,
            input_topic,
            self.gaze_error_callback,
            10,
        )

        self.get_logger().info(
            f'Subscribing {input_topic} and publishing filtered gaze error '
            f'to {output_topic} (2nd-order Butterworth LPF: '
            f'fs={sampling_frequency:.1f} Hz, fc={cutoff_frequency:.1f} Hz)'
        )

    def gaze_error_callback(self, msg):
        cmd_msg = Vector3()
        cmd_msg.x = self.x_filter.update(msg.x)
        cmd_msg.y = self.y_filter.update(msg.y)
        cmd_msg.z = msg.z

        self.publisher.publish(cmd_msg)
        self.get_logger().info(
            f'Raw x: {msg.x:.2f}, y: {msg.y:.2f} -> '
            f'filtered x: {cmd_msg.x:.2f}, y: {cmd_msg.y:.2f}'
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
