# picamera.py 코드 설명

## 1. 코드 목적

`picamera.py`는 라즈베리파이에 연결된 PiCamera 영상을 노트북 브라우저에서 볼 수 있도록 스트리밍하는 코드이다.

이 프로젝트에서 PiCamera는 로봇의 눈 역할을 한다. 따라서 `picamera.py`는 단순한 카메라 테스트 코드가 아니라, 사용자가 로봇이 보는 화면을 실시간으로 확인하게 해주는 핵심 모듈이다.

```text
PiCamera
  ↓
picamera.py
  ↓
Flask MJPEG Streaming
  ↓
노트북 브라우저
```

---

## 2. 시스템 안에서의 역할

전체 시스템에서 `picamera.py`는 로봇 시야 피드백을 담당한다.

사용자는 노트북 브라우저에 표시된 PiCamera 영상을 바라본다. 동시에 노트북 웹캠은 사용자의 눈을 촬영하여 gaze tracking을 수행한다.

```text
로봇 PiCamera 영상
  ↓
노트북 화면에 스트리밍
  ↓
사용자가 그 화면을 봄
  ↓
노트북 웹캠이 사용자 시선 측정
  ↓
시선 방향에 따라 로봇 카메라가 움직임
```

따라서 `picamera.py`가 없으면 사용자는 로봇이 현재 무엇을 보고 있는지 알 수 없고, 시선 제어 시스템도 의미가 약해진다.

---

## 3. 주요 설정값

```python
HOST = "0.0.0.0"
PORT = 8000
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
JPEG_QUALITY = 80
```

| 값 | 의미 |
|---|---|
| `HOST = "0.0.0.0"` | 같은 네트워크의 다른 기기에서 접속 가능하게 함 |
| `PORT = 8000` | 웹서버 포트 번호 |
| `FRAME_WIDTH = 640` | 카메라 영상 가로 크기 |
| `FRAME_HEIGHT = 480` | 카메라 영상 세로 크기 |
| `JPEG_QUALITY = 80` | 스트리밍 이미지 압축 품질 |

노트북에서는 다음 주소로 접속한다.

```text
http://라즈베리파이_IP주소:8000
```

---

## 4. bootstrap_rpi_libs 함수

```python
def bootstrap_rpi_libs():
```

이 함수는 라즈베리파이에서 Picamera2와 libcamera 라이브러리 경로를 잡기 위한 초기 설정 코드이다.

특히 Ubuntu 환경에서 Picamera2/libcamera 관련 라이브러리 경로가 기본적으로 잘 잡히지 않을 수 있기 때문에, `.rpi-root-0.3` 또는 `.rpi-root` 폴더 안의 라이브러리 경로를 환경변수에 등록한다.

주요 환경변수는 다음과 같다.

| 환경변수 | 역할 |
|---|---|
| `LD_LIBRARY_PATH` | libcamera 관련 공유 라이브러리 경로 추가 |
| `LIBCAMERA_DATA_DIR` | libcamera 데이터 파일 위치 지정 |
| `LIBCAMERA_IPA_MODULE_PATH` | IPA 모듈 경로 지정 |
| `LIBCAMERA_IPA_CONFIG_PATH` | IPA 설정 파일 경로 지정 |

환경변수를 적용한 뒤에는 `os.execv()`를 이용해 현재 파이썬 프로세스를 다시 실행한다.

---

## 5. Flask 웹서버 구조

```python
app = Flask(__name__)
```

Flask는 웹서버를 만들기 위해 사용된다.

이 코드에는 두 개의 주요 라우트가 있다.

| 주소 | 역할 |
|---|---|
| `/` | 웹페이지 표시 |
| `/video_feed` | MJPEG 카메라 스트림 제공 |

브라우저가 `/`에 접속하면 HTML 페이지가 뜨고, 그 안의 `<img>` 태그가 `/video_feed`를 불러와 영상을 표시한다.

---

## 6. camera_worker 함수

```python
def camera_worker():
```

이 함수는 별도 프로세스에서 실행되며 PiCamera2를 직접 제어한다.

주요 흐름은 다음과 같다.

```text
Picamera2 객체 생성
  ↓
640x480 RGB888 설정
  ↓
카메라 시작
  ↓
프레임 캡처
  ↓
OpenCV로 BGR 변환
  ↓
JPEG로 인코딩
  ↓
frame_queue에 저장
```

코드에서는 다음 부분이 카메라 설정에 해당한다.

```python
camera = Picamera2()
config = camera.create_preview_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
camera.configure(config)
camera.start()
```

그리고 반복문에서 프레임을 계속 캡처한다.

```python
frame = camera.capture_array()
```

OpenCV를 이용해 JPEG로 압축한다.

```python
ok, encoded = cv2.imencode(".jpg", frame, ...)
```

---

## 7. frame_queue를 사용하는 이유

```python
frame_queue = multiprocessing.Queue(maxsize=2)
```

카메라 캡처 프로세스와 Flask 웹서버 프로세스는 서로 다른 속도로 동작할 수 있다.

따라서 중간에 queue를 두고 최신 프레임을 전달한다.

`put_latest_frame()` 함수는 queue가 가득 차면 오래된 프레임을 버리고 최신 프레임을 넣는다.

```text
오래된 프레임 제거
  ↓
최신 프레임 저장
  ↓
브라우저로 전송
```

이 구조 덕분에 지연이 계속 쌓이는 것을 줄일 수 있다.

---

## 8. generate_stream 함수

```python
def generate_stream():
```

이 함수는 queue에서 JPEG 프레임을 꺼내 브라우저에 MJPEG 형식으로 계속 전송한다.

```python
yield (
    b"--frame\r\n"
    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
)
```

MJPEG는 여러 장의 JPEG 이미지를 연속으로 보내서 영상처럼 보이게 하는 방식이다.

---

## 9. get_local_ip 함수

```python
def get_local_ip():
```

이 함수는 라즈베리파이의 현재 네트워크 IP 주소를 확인한다.

프로그램 실행 시 다음과 같은 형태로 접속 주소를 출력한다.

```text
Open this address: http://192.168.x.x:8000
```

노트북 브라우저에서 이 주소로 접속하면 PiCamera 영상이 보인다.

---

## 10. main 함수 흐름

```python
def main():
```

전체 실행 흐름은 다음과 같다.

```text
camera_worker를 별도 프로세스로 실행
  ↓
카메라 시작 여부 확인
  ↓
라즈베리파이 IP 주소 출력
  ↓
Flask 서버 실행
  ↓
브라우저로 카메라 영상 스트리밍
```

Flask 서버는 다음 코드로 실행된다.

```python
app.run(host=HOST, port=PORT, threaded=True)
```

`HOST = "0.0.0.0"`이기 때문에 같은 Wi-Fi에 연결된 노트북에서도 접속할 수 있다.

---

## 11. 이 코드가 중요한 이유

초기 시스템에서는 MediaPipe gaze tracking을 노트북 화면만 기준으로 수행할 수 있었다. 하지만 로봇 시야를 실제로 제어하려면 사용자가 로봇이 보고 있는 장면을 확인해야 한다.

`picamera.py`는 라즈베리파이에 달린 로봇 카메라 영상을 노트북 화면에 띄워준다.

즉, 사용자는 노트북 화면을 보지만, 실제로는 로봇의 시야를 보고 있는 것이다.

```text
사용자 → 노트북 화면을 봄
노트북 화면 → 라즈베리파이 PiCamera 영상
PiCamera → 로봇의 실제 시야
```

따라서 `picamera.py`는 사용자 시선과 로봇 시야를 연결하는 피드백 모듈이다.

---

## 12. 핵심 요약

`picamera.py`는 라즈베리파이 PiCamera 영상을 Flask 기반 웹 스트리밍으로 노트북에 전달한다. 이 영상은 사용자가 바라보는 화면이 되고, 노트북 웹캠은 그 사용자의 시선을 측정한다. 따라서 이 코드는 사용자 맞춤형 시선 제어 시스템에서 로봇 시야 피드백을 담당하는 핵심 코드이다.
