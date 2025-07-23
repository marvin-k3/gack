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
import logging
import asyncio
from datetime import datetime
from gack.database import PoseDatabase


def process_frame(frame, model, show_original=False):
    """Run pose estimation and draw skeletons on the frame."""
    results = model(frame)
    poses = results[0].keypoints.xy.cpu().numpy() if results[0].keypoints is not None else []
    confidences = results[0].boxes.conf.cpu().numpy() if results[0].boxes is not None else []
    boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
    keypoint_confidences = results[0].keypoints.conf.cpu().numpy() if results[0].keypoints is not None else []

    if show_original:
        pose_img = frame.copy()
    else:
        pose_img = np.zeros_like(frame)

    # Log comprehensive data for each person detected
    for i, (person, conf, box, kp_conf) in enumerate(zip(poses, confidences, boxes, keypoint_confidences)):
        # Calculate bounding box dimensions
        x1, y1, x2, y2 = box
        width = x2 - x1
        height = y2 - y1
        area = width * height
        
        # Calculate average keypoint confidence
        avg_kp_conf = np.mean(kp_conf) if len(kp_conf) > 0 else 0
        
        # Count visible keypoints (confidence > 0.5)
        visible_keypoints = np.sum(kp_conf > 0.5) if len(kp_conf) > 0 else 0
        
        logger.info(f"Person {i+1}: detection_confidence={conf:.3f}, "
                   f"bbox=({x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}), "
                   f"size={width:.1f}x{height:.1f}, area={area:.0f}, "
                   f"avg_kp_conf={avg_kp_conf:.3f}, visible_kps={visible_keypoints}/17")
        
        # Draw keypoints and skeleton
        for j, (x, y) in enumerate(person):
            if kp_conf[j] > 0.5:  # Only draw confident keypoints
                cv2.circle(pose_img, (int(x), int(y)), 3, (0, 255, 0), -1)
        
        skeleton = [
            (5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12),
            (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)
        ]
        for start_idx, end_idx in skeleton:
            if (start_idx < len(person) and end_idx < len(person) and 
                kp_conf[start_idx] > 0.5 and kp_conf[end_idx] > 0.5):
                pt1 = tuple(map(int, person[start_idx]))
                pt2 = tuple(map(int, person[end_idx]))
                cv2.line(pose_img, pt1, pt2, (255, 0, 0), 2)
    
    return pose_img, poses, confidences, boxes, keypoint_confidences


class PoseStreamer:
    def __init__(self, model, cap, process, fps=1, show_original=False, ffmpeg_threads=None, db=None):
        self.model = model
        self.cap = cap
        self.process = process
        self.fps = fps
        self.show_original = show_original
        self.shutdown = False
        self.ffmpeg_threads = ffmpeg_threads or []
        self.db = db
        self.frame_number = 0

    def handle_sigint(self, signum, frame):
        logger.info('Received SIGINT, shutting down...')
        self.shutdown = True

    def stream(self):
        last_output_time = time.time()
        interval = 1.0 / self.fps
        try:
            while not self.shutdown:
                ret, frame = self.cap.read()
                if not ret:
                    logger.error('Failed to read frame from stream')
                    break

                now = time.time()
                if now - last_output_time < interval:
                    continue
                last_output_time = now

                self.frame_number += 1
                video_timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                
                pose_img, poses, confidences, boxes, keypoint_confidences = process_frame(frame, self.model, self.show_original)
                self.process.stdin.write(pose_img.astype(np.uint8).tobytes())
                
                # Save to database if poses were detected
                if len(poses) > 0 and self.db:
                    asyncio.run(self._save_detection(video_timestamp, poses, confidences, boxes, keypoint_confidences))
        finally:
            self.cap.release()
            self.process.stdin.close()
            self.process.wait()
            # Wait for ffmpeg output threads to finish
            for t in self.ffmpeg_threads:
                t.join(timeout=1)
            logger.info('Shutdown complete.')
    
    async def _save_detection(self, video_timestamp, poses, confidences, boxes, keypoint_confidences):
        """Save detection data to database."""
        try:
            timestamp = datetime.now().isoformat()
            # Convert numpy arrays to lists for JSON serialization
            poses_list = [pose.tolist() for pose in poses]
            confidences_list = confidences.tolist()
            boxes_list = boxes.tolist()
            keypoint_confidences_list = [kp_conf.tolist() for kp_conf in keypoint_confidences]
            
            await self.db.save_detection(
                timestamp=timestamp,
                frame_number=self.frame_number,
                video_timestamp=video_timestamp,
                poses=poses_list,
                confidences=confidences_list,
                boxes=boxes_list,
                keypoint_confidences=keypoint_confidences_list
            )
        except Exception as e:
            logger.error(f"Failed to save detection to database: {e}")


def ffmpeg_output_reader(stream, prefix):
    for line in iter(stream.readline, b''):
        try:
            decoded = line.decode(errors='replace').rstrip('\n')
        except Exception:
            decoded = str(line).rstrip('\n')
        if prefix.strip() == '[FFMPEG][stderr]':
            logger.debug(f"FFMPEG stderr: {decoded}")
        else:
            logger.debug(f"FFMPEG stdout: {decoded}")
    stream.close()


def main():
    load_dotenv()
    
    # Setup logging
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('outdata/gack.log')
        ]
    )
    global logger
    logger = logging.getLogger(__name__)
    
    RTSPS_URL = os.getenv('UNIFI_RTSPS_URL')
    if not RTSPS_URL:
        raise RuntimeError('UNIFI_RTSPS_URL not set in .env file')
    OUTPUT_STREAM = "outdata/output.mp4"
    FPS = int(os.getenv('FPS', 1))
    SHOW_ORIGINAL = os.getenv('SHOW_ORIGINAL', 'False').lower() in ('1', 'true', 'yes')
    SAVE_TO_DB = os.getenv('SAVE_TO_DB', 'True').lower() in ('1', 'true', 'yes')

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

    # Initialize database if enabled
    db = None
    if SAVE_TO_DB:
        db = PoseDatabase()
        asyncio.run(db.init_db())
        logger.info("Database initialized for pose detection storage")

    streamer = PoseStreamer(model, cap, process, fps=FPS, show_original=SHOW_ORIGINAL, ffmpeg_threads=threads, db=db)
    signal.signal(signal.SIGINT, streamer.handle_sigint)
    streamer.stream()


if __name__ == '__main__':
    main() 