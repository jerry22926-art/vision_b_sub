import socket
import threading
import time
from io import BytesIO

from flask import Flask, Response, render_template_string


HOST = "0.0.0.0"
PORT = 8000
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
JPEG_QUALITY = 80


app = Flask(__name__)

camera_lock = threading.Lock()
latest_frame = None
camera_error = None


PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Raspberry Pi Camera</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Arial, sans-serif;
      background: #111;
      color: #f5f5f5;
    }

    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      box-sizing: border-box;
    }

    main {
      width: min(960px, 100%);
    }

    h1 {
      margin: 0 0 16px;
      font-size: clamp(24px, 4vw, 42px);
      font-weight: 700;
    }

    .camera {
      position: relative;
      width: 100%;
      aspect-ratio: 4 / 3;
      background: #000;
      border: 1px solid #333;
      border-radius: 8px;
      overflow: hidden;
    }

    img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .status {
      position: absolute;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
      box-sizing: border-box;
      color: #f5f5f5;
      background: #000;
      text-align: center;
      font-size: 18px;
      line-height: 1.5;
    }

    p {
      color: #bdbdbd;
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <main>
    <h1>Raspberry Pi Camera</h1>
    <div class="camera">
      <img id="stream" src="/video_feed" alt="Raspberry Pi camera live stream">
      <div id="status" class="status">카메라 영상을 불러오는 중입니다.</div>
    </div>
    <p>노트북 브라우저에서 이 라즈베리파이의 IP 주소와 포트 8000으로 접속하세요.</p>
  </main>
  <script>
    const stream = document.getElementById("stream");
    const status = document.getElementById("status");

    stream.addEventListener("load", () => {
      status.style.display = "none";
    });

    stream.addEventListener("error", () => {
      status.style.display = "flex";
      status.textContent = "카메라가 아직 준비되지 않았습니다. 다른 프로그램이 카메라를 사용 중이면 종료한 뒤 잠시 기다려 주세요.";
      setTimeout(() => {
        stream.src = "/video_feed?t=" + Date.now();
      }, 2000);
    });
  </script>
</body>
</html>
"""


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "라즈베리파이_IP주소"


def start_picamera2():
    from picamera2 import Picamera2

    camera = Picamera2()
    config = camera.create_still_configuration(
        main={"size": (FRAME_WIDTH, FRAME_HEIGHT)}
    )
    camera.configure(config)
    camera.start()
    time.sleep(1)
    return camera


def camera_loop():
    global latest_frame, camera_error

    while True:
        picamera = None
        video_capture = None

        try:
            try:
                picamera = start_picamera2()
                camera_error = None
                print("Picamera2 camera started.")
            except Exception as exc:
                print(f"Picamera2 start failed: {exc}")
                print("Trying OpenCV VideoCapture(0).")
                import cv2

                video_capture = cv2.VideoCapture(0)
                video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

                if not video_capture.isOpened():
                    raise RuntimeError("Cannot open camera with Picamera2 or OpenCV.")
                camera_error = None

            while True:
                if picamera is not None:
                    stream = BytesIO()
                    picamera.capture_file(stream, format="jpeg")
                    frame = stream.getvalue()
                else:
                    ok, frame = video_capture.read()
                    if not ok:
                        raise RuntimeError("Failed to read frame from camera.")

                    ok, encoded = cv2.imencode(
                        ".jpg",
                        frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
                    )
                    if not ok:
                        continue
                    frame = encoded.tobytes()

                with camera_lock:
                    latest_frame = frame

                time.sleep(0.03)

        except Exception as exc:
            camera_error = str(exc)
            with camera_lock:
                latest_frame = None
            print(f"Camera error: {camera_error}")
            print("Retrying camera in 2 seconds.")
            time.sleep(2)
        finally:
            if picamera is not None:
                picamera.stop()
            if video_capture is not None:
                video_capture.release()


def generate_stream():
    while True:
        with camera_lock:
            frame = latest_frame

        if frame is None:
            time.sleep(0.1)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )
        time.sleep(0.05)


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    threading.Thread(target=camera_loop, daemon=True).start()

    local_ip = get_local_ip()
    print(f"Open this address on your laptop: http://{local_ip}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)
