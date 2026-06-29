# 전체 시스템 설명: 사용자 맞춤형 시선 기반 로봇 시야 제어 시스템

## 1. 시스템 목표

이 시스템의 목표는 사용자의 시선을 이용해서 로봇에 장착된 카메라의 방향을 제어하는 것이다.

사용자는 노트북 화면에 표시되는 로봇 카메라 영상을 바라본다. 노트북 웹캠은 사용자의 눈과 얼굴을 촬영하고, MediaPipe 기반 gaze tracking을 통해 사용자가 화면의 어느 방향을 보고 있는지 추정한다. 이후 계산된 gaze error를 ROS2 토픽으로 전달하고, 라즈베리파이 쪽 서보모터가 그 오차에 따라 pan/tilt 방향으로 움직인다.

결과적으로 사용자가 화면의 특정 방향을 바라보면, 로봇의 카메라도 그 방향으로 움직이게 된다.

---

## 2. 전체 구조

```text
[라즈베리파이 / 로봇]

PiCamera
  ↓
picamera.py
  ↓
Flask MJPEG Streaming
  ↓
Wi-Fi / Network
  ↓

[노트북]

브라우저에서 로봇 시야 확인
  ↓
사용자가 화면을 바라봄
  ↓
노트북 웹캠
  ↓
MediaPipe Iris / Gaze Tracking
  ↓
사용자별 캘리브레이션 기준과 비교
  ↓
gaze_error 계산
  ↓
ROS2 publish: /gaze_error
  ↓

[라즈베리파이 / ROS2]

SubGazeErrorNode
  ↓
Butterworth Low Pass Filter
  ↓
ROS2 publish: /gaze_error_cmd
  ↓
ServoNode
  ↓
PCA9685 + Pan/Tilt Servo
  ↓
PiCamera 방향 변경
```

---

## 3. 카메라를 두 개 사용하는 이유

이 시스템에서는 카메라가 두 개 사용된다.

| 카메라 | 위치 | 역할 |
|---|---|---|
| PiCamera | 라즈베리파이 / 로봇 | 로봇이 실제로 보고 있는 장면을 촬영 |
| 노트북 웹캠 | 노트북 | 사용자의 얼굴과 눈을 촬영하여 gaze tracking 수행 |

PiCamera는 로봇의 눈 역할을 한다. 이 카메라 영상은 `picamera.py`를 통해 노트북 브라우저에 스트리밍된다.

노트북 웹캠은 사용자의 눈을 보는 센서 역할을 한다. 이 웹캠 영상으로 MediaPipe가 홍채와 눈 위치를 추정하고, 사용자가 화면의 어느 방향을 바라보는지 계산한다.

즉, PiCamera는 로봇 시야를 제공하고, 노트북 웹캠은 사용자 시선을 입력으로 받는다.

---

## 4. 사용자별 캘리브레이션이 필요한 이유

사람마다 눈의 위치, 얼굴 크기, 웹캠과의 거리, 앉은 자세, 시선 기준점이 모두 다르다.

따라서 모든 사용자에게 동일한 gaze 기준을 적용하면 정확도가 떨어질 수 있다. 이를 해결하기 위해 시스템 초기에는 사용자별 캘리브레이션을 수행한다.

캘리브레이션 과정에서는 사용자가 화면 중앙이나 특정 기준점을 바라보게 하고, 이때의 홍채 좌표와 얼굴 기준값을 저장한다. 이후 실시간 gaze tracking 결과를 이 기준값과 비교하여 gaze error를 계산한다.

```text
초기 사용자 캘리브레이션
  ↓
개인 기준 gaze 좌표 저장
  ↓
실시간 홍채 좌표 측정
  ↓
기준값과 현재값 비교
  ↓
gaze error 계산
```

이 과정 덕분에 시스템은 사용자 맞춤형 시선 제어가 가능해진다.

---

## 5. ROS2 토픽 흐름

시스템의 핵심 ROS2 토픽 흐름은 다음과 같다.

```text
/gaze_error
  ↓
SubGazeErrorNode
  ↓
/gaze_error_cmd
  ↓
ServoNode
  ↓
Pan/Tilt Servo 제어
```

### `/gaze_error`

MediaPipe gaze tracking 결과로부터 계산된 원본 시선 오차값이다.

- `x`: 화면 중심 기준 좌우 오차
- `y`: 화면 중심 기준 상하 오차
- `z`: 추가 상태값 또는 confidence 용도로 사용 가능

### `/gaze_error_cmd`

Butterworth Low Pass Filter를 거친 부드러운 시선 오차값이다. 서보모터는 이 값을 입력으로 받아 움직인다.

---

## 6. 각 코드의 역할

| 파일 | 역할 |
|---|---|
| `picamera.py` | 라즈베리파이 PiCamera 영상을 노트북 브라우저로 스트리밍 |
| `sub_gaze_error_node.py` | `/gaze_error`를 받아 Butterworth Low Pass Filter 적용 후 `/gaze_error_cmd` 발행 |
| `servo_node.py` | `/gaze_error_cmd`를 받아 PCA9685 기반 pan/tilt 서보모터 제어 |

---

## 7. 시스템 관점에서의 의미

이 시스템은 단순히 카메라 화면을 보여주는 구조가 아니다.

사용자의 시선 입력, 로봇 카메라 영상 피드백, 서보모터 제어가 연결된 폐루프 시스템이다.

```text
사용자 시선
  ↓
시선 오차 계산
  ↓
서보모터 제어
  ↓
로봇 카메라 방향 변화
  ↓
노트북 화면에 새로운 로봇 시야 표시
  ↓
사용자가 다시 화면을 바라봄
```

따라서 이 프로젝트의 핵심 개념은 사용자 맞춤형 gaze tracking을 이용한 로봇 시야 제어라고 정리할 수 있다.
