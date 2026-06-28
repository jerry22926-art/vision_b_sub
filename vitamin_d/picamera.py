import multiprocessing
import os
import queue
import socket
import sys
import time
from pathlib import Path


def bootstrap_rpi_libs():
    project_root = Path(__file__).resolve().parents[1]
    rpi_root = project_root / ".rpi-root-0.3"
    if not rpi_root.exists():
        rpi_root = project_root / ".rpi-root"
    fallback_root = project_root / ".rpi-root"
    rpi_lib = rpi_root / "usr/lib/aarch64-linux-gnu"
    fallback_lib = fallback_root / "usr/lib/aarch64-linux-gnu"
    rpi_data = rpi_root / "usr/share/libcamera"
    rpi_ipa_data = rpi_data / "ipa"
    rpi_ipa_vc4 = rpi_ipa_data / "rpi/vc4"
    rpi_ipa_pisp = rpi_ipa_data / "rpi/pisp"
    rpi_ipa = rpi_lib / "libcamera"

    if not rpi_lib.exists():
        return

    lib_paths = [str(rpi_lib)]
    if fallback_lib.exists() and fallback_lib != rpi_lib:
        lib_paths.append(str(fallback_lib))
    lib_path = ":".join(lib_paths)
    current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")

    os.environ["LIBCAMERA_DATA_DIR"] = str(rpi_data)
    os.environ["LIBCAMERA_IPA_MODULE_PATH"] = str(rpi_ipa)
    os.environ["LIBCAMERA_IPA_PROXY_PATH"] = str(rpi_ipa)
    os.environ["LIBCAMERA_IPA_CONFIG_PATH"] = ":".join(
        [str(rpi_ipa_data), str(rpi_ipa_vc4), str(rpi_ipa_pisp)]
    )

    if os.environ.get("PICAMERA_RPI_LIBS") == "1":
        return

    os.environ["LD_LIBRARY_PATH"] = (
        f"{lib_path}:{current_ld_path}" if current_ld_path else lib_path
    )
    os.environ["PICAMERA_RPI_LIBS"] = "1"
    os.execv(sys.executable, [sys.executable, *sys.argv])


bootstrap_rpi_libs()

import cv2
from flask import Flask, Response, render_template_string


HOST = "0.0.0.0"
PORT = 8000
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
JPEG_QUALITY = 80


app = Flask(__name__)
frame_queue = multiprocessing.Queue(maxsize=2)
status_queue = multiprocessing.Queue()


PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #111;
      color: #f5f5f5;
      font-family: Arial, sans-serif;
    }

    main {
      width: min(960px, 95vw);
    }

    img {
      width: 100%;
      background: #000;
      border-radius: 8px;
      display: block;
    }

    p {
      color: #bbb;
      line-height: 1.5;
    }
  </style>
</head>
<body>
  <main>
    <img src="/video_feed" alt="Picamera2 live stream">
    <p>Ctrl+C</p>
  </main>
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


def put_latest_frame(jpeg_frame):
    while frame_queue.full():
        try:
            frame_queue.get_nowait()
        except queue.Empty:
            break

    frame_queue.put(jpeg_frame)


def camera_worker():
    try:
        from picamera2 import Picamera2

        camera = Picamera2()
        config = camera.create_preview_configuration(
            main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
        )
        camera.configure(config)
        camera.start()
        status_queue.put(("ok", "Picamera2 camera started."))
        time.sleep(1)

        while True:
            frame = camera.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
            )
            if ok:
                put_latest_frame(encoded.tobytes())
    except Exception as exc:
        status_queue.put(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        if "camera" in locals():
            camera.stop()


def generate_stream():
    while True:
        try:
            frame = frame_queue.get(timeout=1)
        except queue.Empty:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def main():
    camera_process = multiprocessing.Process(target=camera_worker, daemon=True)
    camera_process.start()

    time.sleep(3)
    if not camera_process.is_alive():
        while not status_queue.empty():
            kind, message = status_queue.get()
            if kind == "error":
                raise RuntimeError(f"Picamera2 startup failed: {message}")

        raise RuntimeError(
            "Picamera2 process exited during startup. "
            "This usually means the installed Picamera2/libcamera stack crashed."
        )

    while not status_queue.empty():
        kind, message = status_queue.get()
        if kind == "error":
            raise RuntimeError(f"Picamera2 startup failed: {message}")
        print(message)

    local_ip = get_local_ip()
    print(f"Open this address: http://{local_ip}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)


if __name__ == "__main__":
    main()
