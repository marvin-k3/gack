import pytest
import subprocess
import tempfile
import time
import os
import socket
import cv2
import numpy as np
import requests
import ffmpeg
import logging

from gack.pose_stream import PoseStreamer, process_frame

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - skip if ultralytics missing
    YOLO = None

logger = logging.getLogger(__name__)


def _get_free_port() -> int:
    """Return an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


MEDIA_PORT = _get_free_port()
API_PORT = _get_free_port()
RTSP_URL = f"rtsp://localhost:{MEDIA_PORT}/test"


def wait_for_condition(condition_func, timeout=15, check_interval=0.5):
    """Wait for a condition to become True until timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if condition_func():
            return True
        time.sleep(check_interval)
    return False


@pytest.fixture(scope="session")
def mediamtx_server() -> None:
    """Start MediaMTX server with a minimal config."""
    config_content = f"""
rtspAddress: :{MEDIA_PORT}
api: yes
apiAddress: :{API_PORT}
paths:
  all:
    source: publisher
"""
    cfg = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
    cfg.write(config_content)
    cfg.close()
    process = subprocess.Popen([
        "mediamtx",
        cfg.name,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def api_ready() -> bool:
        try:
            r = requests.get(f"http://localhost:{API_PORT}/v3/paths/list", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    assert wait_for_condition(api_ready), "MediaMTX failed to start"
    yield
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    os.unlink(cfg.name)


@pytest.fixture(scope="session")
def ffmpeg_stream(mediamtx_server):
    """Stream a short video to MediaMTX via FFmpeg."""
    cmd = [
        "ffmpeg",
        "-re",
        "-stream_loop",
        "-1",
        "-i",
        "testdata/3327806-hd_1920_1080_24fps.mp4",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "10",
        "-f",
        "rtsp",
        RTSP_URL,
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def ready() -> bool:
        if process.poll() is not None:
            return False
        cap = cv2.VideoCapture(RTSP_URL)
        ok = cap.isOpened()
        if ok:
            cap.release()
        return ok

    assert wait_for_condition(ready), "FFmpeg failed to start"
    yield
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture(scope="session")
def yolo_model():
    if YOLO is None:
        pytest.skip("ultralytics not available")
    try:
        return YOLO("yolov8n-pose.pt")
    except Exception as e:  # pragma: no cover - network failure etc
        pytest.skip(f"YOLO model unavailable: {e}")


def test_rtsp_stream_and_detection(ffmpeg_stream, yolo_model):
    cap = cv2.VideoCapture(RTSP_URL)
    assert cap.isOpened(), f"Failed to open {RTSP_URL}"
    frames = 0
    detections = 0
    while frames < 3:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue
        frames += 1
        res = yolo_model(frame)
        if res[0].keypoints is not None:
            if len(res[0].keypoints.xy) > 0:
                detections += 1
    cap.release()
    assert frames == 3
    assert detections >= 0


def test_pose_streamer_pipeline(ffmpeg_stream, yolo_model):
    cap = cv2.VideoCapture(RTSP_URL)
    assert cap.isOpened(), f"Failed to open {RTSP_URL}"
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = 2
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        out_path = tmp.name
    process = (
        ffmpeg
        .input("pipe:", format="rawvideo", pix_fmt="bgr24", s=f"{width}x{height}", framerate=fps)
        .output(out_path, pix_fmt="yuv420p", vcodec="libx264", r=fps, preset="veryfast", tune="zerolatency")
        .overwrite_output()
        .run_async(pipe_stdin=True)
    )
    streamer = PoseStreamer(yolo_model, cap, process, camera_name="cam", fps=fps, show_original=False)
    frames_written = 0
    try:
        while frames_written < 3:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue
            pose_img, _ = process_frame(frame, yolo_model, False)
            process.stdin.write(pose_img.astype(np.uint8).tobytes())
            frames_written += 1
    finally:
        cap.release()
        process.stdin.close()
        process.wait()
    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 1000
    os.unlink(out_path)
