# ServoNode 코드 설명

## 1. 코드 목적

이 코드는 ROS2에서 `/gaze_error_cmd` 토픽을 구독하고, 그 값을 이용해 PCA9685에 연결된 pan/tilt 서보모터를 제어하는 노드이다.

즉, 필터링된 시선 오차값을 실제 모터 움직임으로 변환하는 제어 코드이다.

```text
/gaze_error_cmd
  ↓
ServoNode
  ↓
PCA9685
  ↓
Pan/Tilt Servo
```

---

## 2. 하드웨어 구성

이 코드는 다음 하드웨어를 전제로 한다.

| 부품 | 역할 |
|---|---|
| Raspberry Pi | ROS2 노드 실행 |
| PCA9685 | I2C 기반 PWM 서보 드라이버 |
| Pan Servo | 좌우 방향 제어 |
| Tilt Servo | 상하 방향 제어 |
| PiCamera | 서보에 의해 방향이 바뀌는 로봇 시야 카메라 |

PCA9685를 사용하는 이유는 라즈베리파이 GPIO만으로 여러 서보를 안정적으로 제어하기 어렵기 때문이다. PCA9685는 서보 제어용 PWM 신호를 대신 만들어준다.

---

## 3. 주요 파라미터

```python
self.declare_parameter('input_topic', '/gaze_error_cmd')
self.declare_parameter('pan_channel', 0)
self.declare_parameter('tilt_channel', 1)
```

| 파라미터 | 의미 |
|---|---|
| `input_topic` | 필터링된 gaze error를 받는 토픽 |
| `pan_channel` | PCA9685의 pan 서보 채널 |
| `tilt_channel` | PCA9685의 tilt 서보 채널 |

---

## 4. 서보 각도 범위

```python
self.declare_parameter('pan_center_angle', 90.0)
self.declare_parameter('pan_min_angle', 20.0)
self.declare_parameter('pan_max_angle', 160.0)
self.declare_parameter('tilt_center_angle', 40.0)
self.declare_parameter('tilt_min_angle', 20.0)
self.declare_parameter('tilt_max_angle', 60.0)
```

| 값 | 의미 |
|---|---|
| `pan_center_angle` | pan 서보 초기 중심 각도 |
| `pan_min_angle` | pan 최소 각도 |
| `pan_max_angle` | pan 최대 각도 |
| `tilt_center_angle` | tilt 서보 초기 중심 각도 |
| `tilt_min_angle` | tilt 최소 각도 |
| `tilt_max_angle` | tilt 최대 각도 |

각도를 제한하는 이유는 서보가 기구적으로 무리한 범위까지 움직이는 것을 막기 위해서이다.

---

## 5. gain과 deadzone

```python
self.declare_parameter('pan_gain', 0.02)
self.declare_parameter('tilt_gain', 0.01)
self.declare_parameter('deadzone', 2.0)
```

| 파라미터 | 의미 |
|---|---|
| `pan_gain` | x 방향 gaze error가 pan 각도에 반영되는 정도 |
| `tilt_gain` | y 방향 gaze error가 tilt 각도에 반영되는 정도 |
| `deadzone` | 작은 오차를 무시하는 범위 |

`gain`이 크면 서보가 빠르고 크게 움직인다. 하지만 너무 크면 흔들리거나 과하게 반응할 수 있다.

`deadzone`은 작은 노이즈로 인해 서보가 계속 떨리는 것을 막는다.

---

## 6. 콜백 함수 흐름

```python
def gaze_error_callback(self, msg):
```

이 함수는 `/gaze_error_cmd`가 들어올 때마다 실행된다.

먼저 작은 오차는 무시한다.

```python
x_error = 0.0 if abs(msg.x) < self.deadzone else msg.x
y_error = 0.0 if abs(msg.y) < self.deadzone else msg.y
```

그 다음 gaze error에 gain을 곱해서 서보 각도를 업데이트한다.

```python
self.pan_angle = self.pan_angle - (x_error * self.pan_gain)
self.tilt_angle = self.tilt_angle - (y_error * self.tilt_gain)
```

이후 각도가 제한 범위를 넘지 않도록 clamp한다.

```python
self.clamp(angle, min_angle, max_angle)
```

마지막으로 실제 서보에 각도를 적용한다.

```python
self.set_servo_angles(self.pan_angle, self.tilt_angle)
```

---

## 7. 시스템 안에서의 의미

이 노드는 사용자의 시선 오차를 실제 로봇 카메라 방향 변화로 바꾸는 마지막 제어 단계이다.

```text
사용자가 화면 오른쪽을 봄
  ↓
x 방향 gaze error 발생
  ↓
ServoNode가 pan angle 변경
  ↓
PiCamera가 오른쪽으로 회전
  ↓
스트리밍 화면도 오른쪽 방향으로 바뀜
```

---

## 8. 종료 시 동작

```python
def destroy_node(self):
```

노드가 종료될 때 서보를 중심 위치로 되돌리고 PCA9685를 종료한다.

```python
self.set_servo_angles(self.pan_center_angle, self.tilt_center_angle)
self.pca.deinit()
```

이는 프로그램 종료 후 서보가 이상한 위치에 남아있지 않게 하기 위한 안전 처리이다.

---

## 9. 핵심 요약

`ServoNode`는 필터링된 gaze error를 받아 pan/tilt 서보 각도로 변환하는 ROS2 제어 노드이다. 이 노드 덕분에 사용자의 시선 방향이 실제 로봇 카메라 방향 변화로 연결된다.
