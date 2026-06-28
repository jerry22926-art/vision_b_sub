import multiprocessing
import os
import shutil
import socket
import subprocess
import sys
import time

import cv2
import numpy as np
from flask import Flask, Response, render_template_string


HOST = "0.0.0.0"
PORT = 8000
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
RAW_WIDTH = 640
RAW_HEIGHT = 480
RAW_FRAME_BYTES = RAW_WIDTH * RAW_HEIGHT * 2
WINDOW_NAME = "Camera"
VIDEO_DEVICES = ("/dev/video0", "/dev/video14", "/dev/video15", "/dev/video21", "/dev/video22")
RAW_FRAME_PATH = "/tmp/imx219_frame.raw"
USE_PICAMERA2 = os.environ.get("USE_PICAMERA2") == "1"

PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IMX219 Camera</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #111; color: #eee; font-family: Arial, sans-serif; }
    main { width: min(960px, 95vw); }
    img { width: 100%; background: #000; border-radius: 8px; }
  </style>
</head>
<body>
  <main>
    <h1>IMX219 Camera</h1>
    <img src="/video_feed" alt="camera stream">
    <p>종료하려면 터미널에서 Ctrl+C를 누르세요.</p>
  </main>
</body>
</html>
"""


app = Flask(__name__)


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "라즈베리파이_IP주소"


def has_gui_display():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def print_camera_status():
    print("Checking camera status...")
    media_graph = ""

    media_ctl = shutil.which("media-ctl")
    if media_ctl and os.path.exists("/dev/media0"):
        result = subprocess.run(
            [media_ctl, "-p", "-d", "/dev/media0"],
            check=False,
            capture_output=True,
            text=True,
        )
        media_graph = result.stdout
        if "imx219" in media_graph and "unicam-image" in media_graph:
            print("media-ctl: IMX219 sensor is connected to unicam.")

    vcgencmd = shutil.which("vcgencmd")
    if vcgencmd:
        result = subprocess.run(
            [vcgencmd, "get_camera"],
            check=False,
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip() or result.stderr.strip()
        print(f"vcgencmd get_camera: {status}")

        if (
            "detected=0" in status
            and "libcamera interfaces=0" in status
            and "imx219" not in media_graph
        ):
            print(
                "Camera is not detected by the OS. "
                "Check the CSI cable direction, camera module, and boot camera overlay settings."
            )
        elif "detected=0" in status and "imx219" in media_graph:
            print("vcgencmd is not reliable here, but the IMX219 media graph is present.")

    devices = [device for device in VIDEO_DEVICES if os.path.exists(device)]
    print(f"Existing video devices: {', '.join(devices) if devices else 'none'}")


def show_picamera2():
    from picamera2 import Picamera2

    camera = Picamera2()
    config = camera.create_preview_configuration(
        main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
    )
    camera.configure(config)
    camera.start()
    time.sleep(1)

    print("Picamera2 started. Press 'q' to quit.")
    try:
        while True:
            frame = camera.capture_array()
            cv2.imshow(WINDOW_NAME, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()


def show_opencv_device(device, ready_queue=None):
    camera = cv2.VideoCapture(device, cv2.CAP_V4L2)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"Cannot open {device}.")

    print(f"OpenCV started with {device}. Press 'q' to quit.", flush=True)

    try:
        first_frame = True
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError(f"{device} opened but did not return frames.")

            if first_frame and ready_queue is not None:
                ready_queue.put(("ready", device))
                first_frame = False

            cv2.imshow(WINDOW_NAME, frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


def configure_imx219_raw_mode():
    media_ctl = shutil.which("media-ctl")
    if media_ctl:
        subprocess.run(
            [
                media_ctl,
                "-d",
                "/dev/media0",
                "--set-v4l2",
                f'"imx219 10-0010":0 [fmt:SRGGB10_1X10/{RAW_WIDTH}x{RAW_HEIGHT} field:none]',
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def raw_to_bgr(raw_bytes):
    if len(raw_bytes) != RAW_FRAME_BYTES:
        raise RuntimeError(f"Unexpected raw frame size: {len(raw_bytes)}, expected {RAW_FRAME_BYTES}.")

    raw = np.frombuffer(raw_bytes, dtype=np.uint16).reshape((RAW_HEIGHT, RAW_WIDTH))
    bayer_8bit = np.right_shift(raw, 2).clip(0, 255).astype(np.uint8)
    return cv2.cvtColor(bayer_8bit, cv2.COLOR_BayerRG2BGR)


def read_exact(stream, size):
    chunks = []
    remaining = size

    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def capture_raw_frame_once():
    configure_imx219_raw_mode()
    command = [
        "v4l2-ctl",
        "-d",
        "/dev/video0",
        f"--set-fmt-video=width={RAW_WIDTH},height={RAW_HEIGHT},pixelformat=RG10",
        "--stream-mmap",
        "--stream-count=1",
        f"--stream-to={RAW_FRAME_PATH}",
    ]
    subprocess.run(command, check=True, timeout=5, stdout=subprocess.DEVNULL)

    with open(RAW_FRAME_PATH, "rb") as raw_file:
        return raw_to_bgr(raw_file.read())


def iter_raw_frames():
    configure_imx219_raw_mode()
    command = [
        "v4l2-ctl",
        "-d",
        "/dev/video0",
        f"--set-fmt-video=width={RAW_WIDTH},height={RAW_HEIGHT},pixelformat=RG10",
        "--stream-mmap=3",
        "--stream-count=100000000",
        "--stream-to=-",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )

    try:
        while True:
            raw_bytes = read_exact(process.stdout, RAW_FRAME_BYTES)
            if len(raw_bytes) != RAW_FRAME_BYTES:
                break
            yield raw_to_bgr(raw_bytes)
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def show_v4l2_raw_imx219():
    if not shutil.which("v4l2-ctl"):
        raise RuntimeError("v4l2-ctl is not installed.")
    if not os.path.exists("/dev/video0"):
        raise RuntimeError("/dev/video0 does not exist.")

    if not has_gui_display():
        show_v4l2_raw_imx219_web()
        return

    print("V4L2 raw IMX219 capture started. Press 'q' to quit.")

    for frame in iter_raw_frames():
        cv2.imshow(WINDOW_NAME, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


def generate_raw_stream():
    for frame in iter_raw_frames():
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
        )


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/video_feed")
def video_feed():
    return Response(generate_raw_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")


def show_v4l2_raw_imx219_web():
    local_ip = get_local_ip()
    print("No GUI display found. Starting browser camera stream.")
    print(f"Open this address: http://{local_ip}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)


def run_opencv_child(device, ready_queue):
    try:
        show_opencv_device(device, ready_queue)
    except Exception as exc:
        ready_queue.put(("error", device, f"{type(exc).__name__}: {exc}"))


def try_opencv_device(device, timeout=8):
    ready_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=run_opencv_child, args=(device, ready_queue))
    process.start()

    try:
        message = ready_queue.get(timeout=timeout)
    except Exception:
        process.terminate()
        process.join(2)
        raise RuntimeError(f"{device} did not produce a frame within {timeout} seconds.")

    if message[0] == "ready":
        process.join()
        return

    process.join(2)
    raise RuntimeError(message[2])


def main():
    print_camera_status()

    try:
        show_v4l2_raw_imx219()
        return
    except Exception as exc:
        print(f"V4L2 raw IMX219 failed: {type(exc).__name__}: {exc}")

    if USE_PICAMERA2:
        try:
            show_picamera2()
            return
        except Exception as exc:
            print(f"Picamera2 failed: {type(exc).__name__}: {exc}")
    else:
        print("Skipping Picamera2. Set USE_PICAMERA2=1 to try it.")

    if not has_gui_display():
        raise RuntimeError("No GUI display is available for OpenCV fallback.")

    last_error = None
    for device in VIDEO_DEVICES:
        if not os.path.exists(device):
            continue

        try:
            try_opencv_device(device)
            return
        except Exception as exc:
            last_error = exc
            print(f"OpenCV failed with {device}: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        "No camera backend could produce frames. "
        "If vcgencmd says detected=0, this must be fixed at the OS/boot/hardware level first."
    ) from last_error


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)


'''
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

'''
