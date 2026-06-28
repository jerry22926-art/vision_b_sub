import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Vector3

try:
    import board
    from adafruit_motor import servo
    from adafruit_pca9685 import PCA9685
except ImportError as exc:
    board = None
    servo = None
    PCA9685 = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class ServoNode(Node):
    def __init__(self):
        super().__init__('servo_node')

        if IMPORT_ERROR is not None:
            raise RuntimeError(
                'PCA9685 servo libraries are not installed. '
                'Install adafruit-circuitpython-pca9685 and adafruit-circuitpython-motor.'
            ) from IMPORT_ERROR

        self.declare_parameter('input_topic', '/gaze_error_cmd')
        self.declare_parameter('pan_channel', 0)
        self.declare_parameter('tilt_channel', 1)
        self.declare_parameter('pan_center_angle', 90.0)
        self.declare_parameter('pan_min_angle', 20.0)
        self.declare_parameter('pan_max_angle', 160.0)
        self.declare_parameter('tilt_center_angle', 40.0)
        self.declare_parameter('tilt_min_angle', 20.0)
        self.declare_parameter('tilt_max_angle', 60.0)
        self.declare_parameter('pan_gain', 0.02)
        self.declare_parameter('tilt_gain', 0.01)
        self.declare_parameter('deadzone', 2.0)

        input_topic = self.get_parameter('input_topic').value
        pan_channel = self.get_parameter('pan_channel').value
        tilt_channel = self.get_parameter('tilt_channel').value

        self.pan_center_angle = float(
            self.get_parameter('pan_center_angle').value
        )
        self.pan_min_angle = float(self.get_parameter('pan_min_angle').value)
        self.pan_max_angle = float(self.get_parameter('pan_max_angle').value)
        self.tilt_center_angle = float(
            self.get_parameter('tilt_center_angle').value
        )
        self.tilt_min_angle = float(
            self.get_parameter('tilt_min_angle').value
        )
        self.tilt_max_angle = float(
            self.get_parameter('tilt_max_angle').value
        )
        self.pan_gain = float(self.get_parameter('pan_gain').value)
        self.tilt_gain = float(self.get_parameter('tilt_gain').value)
        self.deadzone = float(self.get_parameter('deadzone').value)

        self.i2c = board.I2C()
        self.pca = PCA9685(self.i2c)
        self.pca.frequency = 50

        self.pan_servo = servo.Servo(
            self.pca.channels[pan_channel],
            min_pulse=500,
            max_pulse=2500,
        )
        self.tilt_servo = servo.Servo(
            self.pca.channels[tilt_channel],
            min_pulse=500,
            max_pulse=2500,
        )

        self.pan_angle = self.pan_center_angle
        self.tilt_angle = self.tilt_center_angle
        self.set_servo_angles(self.pan_angle, self.tilt_angle)

        self.subscription = self.create_subscription(
            Vector3,
            input_topic,
            self.gaze_error_callback,
            10,
        )

        self.get_logger().info(
            f'Servo node ready. Subscribing {input_topic}, '
            f'PCA9685 channels pan={pan_channel}, tilt={tilt_channel}'
        )

    def gaze_error_callback(self, msg):
        x_error = 0.0 if abs(msg.x) < self.deadzone else msg.x
        y_error = 0.0 if abs(msg.y) < self.deadzone else msg.y

        self.pan_angle = self.clamp(
            self.pan_angle - (x_error * self.pan_gain),
            self.pan_min_angle,
            self.pan_max_angle,
        )
        self.tilt_angle = self.clamp(
            self.tilt_angle - (y_error * self.tilt_gain),
            self.tilt_min_angle,
            self.tilt_max_angle,
        )

        self.set_servo_angles(self.pan_angle, self.tilt_angle)
        self.get_logger().info(
            f'gaze_error x: {msg.x:.2f}, y: {msg.y:.2f}, z: {msg.z:.2f} '
            f'-> pan: {self.pan_angle:.1f}, tilt: {self.tilt_angle:.1f}'
        )

    def set_servo_angles(self, pan_angle, tilt_angle):
        self.pan_servo.angle = pan_angle
        self.tilt_servo.angle = tilt_angle

    @staticmethod
    def clamp(angle, min_angle, max_angle):
        return max(min_angle, min(max_angle, angle))

    def destroy_node(self):
        self.set_servo_angles(
            self.pan_center_angle,
            self.tilt_center_angle,
        )
        self.pca.deinit()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ServoNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
