import cv2
import numpy as np
from ultralytics import YOLO
import ffmpeg
import time
from dotenv import load_dotenv
import os
import signal
import sys
import threading


def process_frame(frame, model, show_original=False):
    """Run pose estimation and draw skeletons on the frame."""
    results = model(frame)
    poses = results[0].keypoints.xy.cpu().numpy() if results[0].keypoints is not None else []

    if show_original:
        pose_img = frame.copy()
    else:
        pose_img = np.zeros_like(frame)

    for person in poses:
        for x, y in person:
            cv2.circle(pose_img, (int(x), int(y)), 3, (0, 255, 0), -1)
        skeleton = [
            (5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12),
            (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)
        ]
        for i, j in skeleton:
            if i < len(person) and j < len(person):
                pt1 = tuple(map(int, person[i]))
                pt2 = tuple(map(int, person[j]))
                cv2.line(pose_img, pt1, pt2, (255, 0, 0), 2)
    return pose_img


class PoseStreamer:
    def __init__(self, model, cap, process, fps=1, show_original=False, ffmpeg_threads=None):
        self.model = model
        self.cap = cap
        self.process = process
        self.fps = fps
        self.show_original = show_original
        self.shutdown = False
        self.ffmpeg_threads = ffmpeg_threads or []

    def handle_sigint(self, signum, frame):
        print('Received SIGINT, shutting down...')
        self.shutdown = True

    def stream(self):
        last_output_time = time.time()
        interval = 1.0 / self.fps
        try:
            while not self.shutdown:
                ret, frame = self.cap.read()
                if not ret:
                    print('Failed to read frame from stream')
                    break

                now = time.time()
                if now - last_output_time < interval:
                    continue
                last_output_time = now

                pose_img = process_frame(frame, self.model, self.show_original)
                self.process.stdin.write(pose_img.astype(np.uint8).tobytes())
        finally:
            self.cap.release()
            self.process.stdin.close()
            self.process.wait()
            # Wait for ffmpeg output threads to finish
            for t in self.ffmpeg_threads:
                t.join(timeout=1)
            print('Shutdown complete.')


def ffmpeg_output_reader(stream, prefix):
    import sys
    for line in iter(stream.readline, b''):
        try:
            decoded = line.decode(errors='replace').rstrip('\n')
        except Exception:
            decoded = str(line).rstrip('\n')
        print(f"{prefix}{decoded}", file=sys.stderr if prefix.strip() == '[FFMPEG][stderr]' else sys.stdout)
    stream.close()


def main():
    load_dotenv()
    RTSPS_URL = os.getenv('UNIFI_RTSPS_URL')
    if not RTSPS_URL:
        raise RuntimeError('UNIFI_RTSPS_URL not set in .env file')
    OUTPUT_STREAM = "outdata/output.mp4"
    FPS = int(os.getenv('FPS', 1))
    SHOW_ORIGINAL = os.getenv('SHOW_ORIGINAL', 'False').lower() in ('1', 'true', 'yes')

    model = YOLO('models/yolov8n-pose.pt')
    cap = cv2.VideoCapture(RTSPS_URL)
    if not cap.isOpened():
        raise RuntimeError(f'Failed to open stream: {RTSPS_URL}')
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    process = (
        ffmpeg
        .input('pipe:', format='rawvideo', pix_fmt='bgr24', s=f'{width}x{height}', framerate=FPS)
        .output(OUTPUT_STREAM, pix_fmt='yuv420p', vcodec='libx264', r=FPS, preset='veryfast', tune='zerolatency')
        .overwrite_output()
        .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
    )

    # Start threads to read ffmpeg stdout and stderr
    threads = []
    t_out = threading.Thread(target=ffmpeg_output_reader, args=(process.stdout, '[FFMPEG][stdout] '), daemon=True)
    t_err = threading.Thread(target=ffmpeg_output_reader, args=(process.stderr, '[FFMPEG][stderr] '), daemon=True)
    t_out.start()
    t_err.start()
    threads.extend([t_out, t_err])

    streamer = PoseStreamer(model, cap, process, fps=FPS, show_original=SHOW_ORIGINAL, ffmpeg_threads=threads)
    signal.signal(signal.SIGINT, streamer.handle_sigint)
    streamer.stream()


if __name__ == '__main__':
    main() 