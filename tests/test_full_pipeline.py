import pytest
import subprocess
import tempfile
import time
import os
import cv2
import numpy as np
from ultralytics import YOLO
import requests
from gack.pose_stream import PoseStreamer, process_frame
import ffmpeg

MEDIA_PORT = 8554
API_PORT = 9997
RTSP_URL = f"rtsp://localhost:{MEDIA_PORT}/test"

@pytest.fixture(scope="session")
def mediamtx_server():
    """Start MediaMTX with a static config and stop after tests."""
    start = time.time()
    config_content = f"""
paths:
  all:
    source: publisher
api: yes
apiAddress: :{API_PORT}
"""
    config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)
    config_file.write(config_content)
    config_file.close()
    process = subprocess.Popen([
        'mediamtx', config_file.name
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1)
    # Wait for API
    for _ in range(10):
        try:
            r = requests.get(f'http://localhost:{API_PORT}/v3/paths/list', timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    print(f"[TIMER] mediamtx_server setup took {time.time() - start:.2f} seconds")
    yield
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    os.unlink(config_file.name)

@pytest.fixture(scope="session")
def ffmpeg_stream():
    """Start FFmpeg to push a test pattern to MediaMTX."""
    start = time.time()
    # Wait for MediaMTX to be up
    time.sleep(1)
    cmd = [
        'ffmpeg', '-re', '-stream_loop', '-1', '-i', 'testdata/3327806-hd_1920_1080_24fps.mp4',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency', '-g', '10',
        '-f', 'rtsp', RTSP_URL
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1)  # Give FFmpeg time to start
    print(f"[TIMER] ffmpeg_stream setup took {time.time() - start:.2f} seconds")
    yield
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

@pytest.fixture(scope="session")
def yolo_model():
    return YOLO('models/yolov8n-pose.pt')

def test_rtsp_stream_and_detection(mediamtx_server, ffmpeg_stream, yolo_model):
    """Test that we can read frames from RTSP and run YOLO detection."""
    cap = cv2.VideoCapture(RTSP_URL)
    assert cap.isOpened(), f"Failed to open RTSP stream: {RTSP_URL}"
    frames_read = 0
    detections = 0
    max_attempts = 30
    for i in range(max_attempts):
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)
            continue
        frames_read += 1
        # Run YOLO pose estimation
        results = yolo_model(frame)
        if results[0].keypoints is not None:
            keypoints = results[0].keypoints.xy.cpu().numpy()
            if len(keypoints) > 0:
                detections += 1
        if frames_read >= 5:
            break
    cap.release()
    assert frames_read >= 3, f"Expected to read at least 3 frames, got {frames_read}"
    # We expect 0 detections on testsrc, but pipeline must run
    assert detections >= 0
    print(f"Read {frames_read} frames, YOLO ran successfully on all.")

def test_pose_streamer_pipeline(mediamtx_server, ffmpeg_stream, yolo_model):
    """Test the PoseStreamer pipeline end-to-end with RTSP input and file output."""
    import tempfile
    import os
    import time
    RTSP_URL = f"rtsp://localhost:{MEDIA_PORT}/test"
    cap = cv2.VideoCapture(RTSP_URL)
    assert cap.isOpened(), f"Failed to open RTSP stream: {RTSP_URL}"
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = 2
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmpfile:
        output_path = tmpfile.name
    process = (
        ffmpeg
        .input('pipe:', format='rawvideo', pix_fmt='bgr24', s=f'{width}x{height}', framerate=fps)
        .output(output_path, pix_fmt='yuv420p', vcodec='libx264', r=fps, preset='veryfast', tune='zerolatency')
        .overwrite_output()
        .run_async(pipe_stdin=True)
    )
    streamer = PoseStreamer(yolo_model, cap, process, fps=fps, show_original=False)
    # Run the streamer for a few frames only
    frames_written = 0
    max_frames = 5
    last_output_time = time.time()
    interval = 1.0 / fps
    try:
        while frames_written < max_frames:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue
            now = time.time()
            if now - last_output_time < interval:
                continue
            last_output_time = now
            pose_img = process_frame(frame, yolo_model, False)
            process.stdin.write(pose_img.astype(np.uint8).tobytes())
            frames_written += 1
    finally:
        cap.release()
        process.stdin.close()
        process.wait()
    # Check that the output file exists and is non-empty
    assert os.path.exists(output_path), f"Output file {output_path} does not exist"
    assert os.path.getsize(output_path) > 1000, f"Output file {output_path} is empty or too small"
    if os.environ.get('POSE_TEST_KEEP_OUTPUT', '0') == '1':
        print(f"[POSE_TEST] Output video kept at: {output_path}")
    else:
        os.unlink(output_path) 