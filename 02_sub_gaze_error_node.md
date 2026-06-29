# SubGazeErrorNode 코드 설명

## 1. 코드 목적

이 코드는 ROS2에서 `/gaze_error` 토픽을 구독하고, 들어온 시선 오차값에 Butterworth Low Pass Filter를 적용한 뒤 `/gaze_error_cmd` 토픽으로 다시 발행하는 노드이다.

즉, 원본 gaze error를 바로 서보모터에 넣지 않고 부드럽게 만들어주는 중간 필터 역할을 한다.

```text
/gaze_error
  ↓
Butterworth Low Pass Filter
  ↓
/gaze_error_cmd
```

---

## 2. 왜 필터가 필요한가?

MediaPipe 기반 gaze tracking 결과는 작은 노이즈와 흔들림이 많을 수 있다.

사용자의 눈이 실제로 가만히 있어도 홍채 좌표는 프레임마다 조금씩 흔들릴 수 있다. 이 값을 그대로 서보모터에 넣으면 모터가 계속 떨리거나 불안정하게 움직일 수 있다.

따라서 이 코드에서는 2차 Butterworth Low Pass Filter를 사용해 빠른 흔들림을 줄이고, 느린 움직임만 통과시킨다.

---

## 3. ButterworthLowPassFilter 클래스

```python
class ButterworthLowPassFilter:
```

이 클래스는 하나의 스칼라 신호에 대해 2차 Butterworth 저역통과 필터를 적용한다.

이 시스템에서는 x 방향 gaze error와 y 방향 gaze error를 각각 따로 필터링한다.

```python
self.x_filter = ButterworthLowPassFilter(...)
self.y_filter = ButterworthLowPassFilter(...)
```

---

## 4. 주요 파라미터

```python
self.declare_parameter('input_topic', '/gaze_error')
self.declare_parameter('output_topic', '/gaze_error_cmd')
self.declare_parameter('sampling_frequency', 30.0)
self.declare_parameter('cutoff_frequency', 1.0)
```

| 파라미터 | 의미 |
|---|---|
| `input_topic` | 원본 gaze error를 받는 토픽 |
| `output_topic` | 필터링된 gaze error를 내보내는 토픽 |
| `sampling_frequency` | gaze error가 들어오는 주파수, 기본 30 Hz |
| `cutoff_frequency` | 필터 차단 주파수, 기본 1 Hz |

`cutoff_frequency`가 낮을수록 더 부드럽지만 반응이 느려진다. 높을수록 반응은 빠르지만 노이즈가 더 많이 남는다.

---

## 5. 콜백 함수 흐름

```python
def gaze_error_callback(self, msg):
```

이 함수는 `/gaze_error` 메시지가 들어올 때마다 실행된다.

```python
cmd_msg = Vector3()
cmd_msg.x = self.x_filter.update(msg.x)
cmd_msg.y = self.y_filter.update(msg.y)
cmd_msg.z = msg.z
```

- `msg.x`: 원본 x 방향 시선 오차
- `msg.y`: 원본 y 방향 시선 오차
- `cmd_msg.x`: 필터링된 x 방향 시선 오차
- `cmd_msg.y`: 필터링된 y 방향 시선 오차
- `msg.z`: 필터링하지 않고 그대로 전달

이후 필터링된 결과를 발행한다.

```python
self.publisher.publish(cmd_msg)
```

---

## 6. 시스템 안에서의 위치

이 노드는 MediaPipe gaze tracking과 서보모터 제어 사이에 위치한다.

```text
MediaPipe / Gaze Tracking
  ↓
/gaze_error
  ↓
SubGazeErrorNode
  ↓
/gaze_error_cmd
  ↓
ServoNode
```

따라서 이 노드는 제어 안정성을 높이기 위한 신호 전처리 모듈이라고 볼 수 있다.

---

## 7. 핵심 요약

`SubGazeErrorNode`는 사용자의 시선 오차값을 부드럽게 만들어 서보모터가 덜 떨리고 안정적으로 움직이도록 하는 ROS2 필터 노드이다.
