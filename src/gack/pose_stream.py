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
from datetime import datetime, timezone
from gack.database import PoseDatabase
from pydantic import BaseModel
from typing import List, Tuple, Optional
logger = logging.getLogger(__name__)


class Detection(BaseModel):
    """Represents a single person detection with pose estimation data."""
    pose: List[Tuple[float, float]]  # List of (x, y) keypoint coordinates
    confidence: float  # Detection confidence score
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) bounding box
    keypoint_confidences: List[float]  # Confidence scores for each keypoint
    source_frame_width: Optional[int] = None  # Width of the source video frame
    source_frame_height: Optional[int] = None  # Height of the source video frame
    
    @property
    def bbox_width(self) -> float:
        """Calculate bounding box width."""
        return self.bbox[2] - self.bbox[0]
    
    @property
    def bbox_height(self) -> float:
        """Calculate bounding box height."""
        return self.bbox[3] - self.bbox[1]
    
    @property
    def bbox_area(self) -> float:
        """Calculate bounding box area."""
        return self.bbox_width * self.bbox_height
    
    @property
    def avg_keypoint_confidence(self) -> float:
        """Calculate average keypoint confidence."""
        return np.mean(self.keypoint_confidences) if self.keypoint_confidences else 0.0
    
    @property
    def visible_keypoints(self) -> int:
        """Count visible keypoints (confidence > 0.5)."""
        return sum(1 for conf in self.keypoint_confidences if conf > 0.5)


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

    # Get frame dimensions
    frame_height, frame_width = frame.shape[:2]

    # Create Detection objects for each person detected
    detections = []
    for i, (person, conf, box, kp_conf) in enumerate(zip(poses, confidences, boxes, keypoint_confidences)):
        # Convert numpy arrays to lists/tuples for Pydantic
        pose_list = [(float(x), float(y)) for x, y in person]
        bbox_tuple = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        kp_conf_list = [float(conf) for conf in kp_conf]
        
        detection = Detection(
            pose=pose_list,
            confidence=float(conf),
            bbox=bbox_tuple,
            keypoint_confidences=kp_conf_list,
            source_frame_width=frame_width,
            source_frame_height=frame_height
        )
        detections.append(detection)
        
        # Log comprehensive data for each person detected
        logger.info(f"Person {i+1}: detection_confidence={detection.confidence:.3f}, "
                   f"bbox=({detection.bbox[0]:.1f},{detection.bbox[1]:.1f},{detection.bbox[2]:.1f},{detection.bbox[3]:.1f}), "
                   f"size={detection.bbox_width:.1f}x{detection.bbox_height:.1f}, area={detection.bbox_area:.0f}, "
                   f"avg_kp_conf={detection.avg_keypoint_confidence:.3f}, visible_kps={detection.visible_keypoints}/17")
        
        # Draw keypoints and skeleton
        for j, (x, y) in enumerate(detection.pose):
            if detection.keypoint_confidences[j] > 0.5:  # Only draw confident keypoints
                cv2.circle(pose_img, (int(x), int(y)), 3, (0, 255, 0), -1)
        
        skeleton = [
            (5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12),
            (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)
        ]
        for start_idx, end_idx in skeleton:
            if (start_idx < len(detection.pose) and end_idx < len(detection.pose) and 
                detection.keypoint_confidences[start_idx] > 0.5 and detection.keypoint_confidences[end_idx] > 0.5):
                pt1 = tuple(map(int, detection.pose[start_idx]))
                pt2 = tuple(map(int, detection.pose[end_idx]))
                cv2.line(pose_img, pt1, pt2, (255, 0, 0), 2)
    
    return pose_img, detections


class PoseStreamer:
    def __init__(
        self,
        model,
        cap,
        process,
        camera_name,
        fps=1,
        show_original=False,
        ffmpeg_threads=None,
        db=None,
        shutdown_event=None,
        rtsp_url: str | None = None,
        max_reconnect_backoff: float = 5.0,
    ):
        """Stream poses from a video source.

        Parameters
        ----------
        model : YOLO
            The pose model to use.
        cap : cv2.VideoCapture
            OpenCV capture object.
        process : subprocess.Popen
            ffmpeg process used for writing frames.
        camera_name : str
            Name of the camera, used for logging and database storage.
        fps : int, optional
            Output frames per second, by default 1.
        show_original : bool, optional
            Whether to overlay pose on original frame, by default False.
        ffmpeg_threads : list[threading.Thread], optional
            Threads reading ffmpeg output.
        db : PoseDatabase, optional
            Database instance for saving detections.
        shutdown_event : threading.Event, optional
            Shared event to signal shutdown.
        rtsp_url : str, optional
            Original RTSP URL. If provided, the streamer will attempt to
            reconnect using this URL when frame reads fail.
        max_reconnect_backoff : float, optional
            Maximum number of seconds to wait between reconnection attempts
            when using exponential backoff.
        """

        self.model = model
        self.cap = cap
        self.process = process
        self.camera_name = camera_name
        self.fps = fps
        self.show_original = show_original
        self.shutdown = False
        self.ffmpeg_threads = ffmpeg_threads or []
        self.db = db
        self.frame_number = 0
        self.shutdown_event = shutdown_event
        self.rtsp_url = rtsp_url
        self.max_reconnect_backoff = max_reconnect_backoff

    def handle_sigint(self, signum, frame):
        logger.info('Received SIGINT, shutting down...')
        self.shutdown = True

    def stream(self):
        last_output_time = time.time()
        interval = 1.0 / self.fps
        try:
            while not self.shutdown and not (self.shutdown_event and self.shutdown_event.is_set()):
                ret, frame = self.cap.read()
                if not ret:
                    logger.error('Failed to read frame from stream')
                    if not self._attempt_reconnect():
                        break
                    else:
                        continue

                now = time.time()
                if now - last_output_time < interval:
                    continue
                last_output_time = now

                self.frame_number += 1
                video_timestamp = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                
                pose_img, detections = process_frame(frame, self.model, self.show_original)
                self.process.stdin.write(pose_img.astype(np.uint8).tobytes())
                
                # Save to database if poses were detected
                if len(detections) > 0 and self.db:
                    asyncio.run(self._save_detection(video_timestamp, detections))
        finally:
            self.cap.release()
            self.process.stdin.close()
            self.process.wait()
            # Wait for ffmpeg output threads to finish
            for t in self.ffmpeg_threads:
                t.join(timeout=1)
            logger.info('Shutdown complete.')

    def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to the video stream using exponential backoff.

        Returns
        -------
        bool
            True if reconnection succeeded and streaming should continue,
            False if reconnection failed and streaming should stop.
        """
        if not self.rtsp_url:
            # Without a URL we cannot reopen the capture; bail out.
            logger.error("No RTSP URL specified for reconnection")
            return False

        attempts = 0
        wait_time = 1.0
        while not self.shutdown and not (self.shutdown_event and self.shutdown_event.is_set()):
            attempts += 1
            logger.info(
                "Attempting to reconnect to %s (attempt %d)",
                self.camera_name,
                attempts,
            )

            self.cap.release()
            time.sleep(wait_time)
            self.cap = cv2.VideoCapture(self.rtsp_url)
            if self.cap.isOpened():
                logger.info("Reconnected to stream")
                return True

            logger.warning(
                "Reconnection attempt %d failed; retrying in %.1fs",
                attempts,
                wait_time,
            )
            wait_time = min(wait_time * 2, self.max_reconnect_backoff)

        return False
    
    async def _save_detection(self, video_timestamp, detections):
        """Save detection data to database."""
        try:
            # Use UTC timestamps to ensure timezone-aware storage
            timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            # Convert Pydantic Detection objects to dictionaries for JSON serialization
            detections_list = [detection.model_dump() for detection in detections]
            
            await self.db.save_detection(
                self.camera_name,
                timestamp,
                self.frame_number,
                video_timestamp,
                detections_list
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
    
    CAMERAS = os.getenv('CAMERAS')
    if not CAMERAS:
        raise RuntimeError('CAMERAS not set in .env file')
    
    # Parse cameras: list of (camera_name, rtsp_url)
    camera_configs = []
    for entry in CAMERAS.split(','):
        if '|' not in entry:
            logger.warning(f"Invalid camera entry: {entry}")
            continue
        name, url = entry.split('|', 1)
        camera_configs.append((name.strip(), url.strip()))
    if not camera_configs:
        raise RuntimeError('No valid cameras found in CAMERAS')
    
    FPS = int(os.getenv('FPS', 1))
    SHOW_ORIGINAL = os.getenv('SHOW_ORIGINAL', 'False').lower() in ('1', 'true', 'yes')
    SAVE_TO_DB = os.getenv('SAVE_TO_DB', 'True').lower() in ('1', 'true', 'yes')
    RECONNECT_BACKOFF_MAX = float(os.getenv('RECONNECT_BACKOFF_MAX', '5'))

    # Initialize database if enabled
    db = None
    if SAVE_TO_DB:
        db = PoseDatabase()
        asyncio.run(db.init_db())
        logger.info("Database initialized for pose detection storage")

    shutdown_event = threading.Event()

    def handle_sigint(signum, frame):
        logger.info("Received SIGINT, shutting down all streams...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_sigint)

    def run_stream(camera_name, rtsp_url):
        logger.info(f"Starting stream for {camera_name}: {rtsp_url}")
        model = YOLO('models/yolov8n-pose.pt')
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            logger.error(f'Failed to open stream: {rtsp_url}')
            return
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        output_stream = f"outdata/{camera_name}_output.mp4"
        process = (
            ffmpeg
            .input('pipe:', format='rawvideo', pix_fmt='bgr24', s=f'{width}x{height}', framerate=FPS)
            .output(output_stream, pix_fmt='yuv420p', vcodec='libx264', r=FPS, preset='veryfast', tune='zerolatency')
            .overwrite_output()
            .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True)
        )
        # Start threads to read ffmpeg stdout and stderr
        threads = []
        t_out = threading.Thread(target=ffmpeg_output_reader, args=(process.stdout, f'[FFMPEG][stdout][{camera_name}] '), daemon=True)
        t_err = threading.Thread(target=ffmpeg_output_reader, args=(process.stderr, f'[FFMPEG][stderr][{camera_name}] '), daemon=True)
        t_out.start()
        t_err.start()
        threads.extend([t_out, t_err])
        streamer = PoseStreamer(
            model,
            cap,
            process,
            camera_name=camera_name,
            fps=FPS,
            show_original=SHOW_ORIGINAL,
            ffmpeg_threads=threads,
            db=db,
            shutdown_event=shutdown_event,
            rtsp_url=rtsp_url,
            max_reconnect_backoff=RECONNECT_BACKOFF_MAX,
        )
        streamer.stream()

    # Start a thread for each camera
    threads = []
    for camera_name, rtsp_url in camera_configs:
        t = threading.Thread(target=run_stream, args=(camera_name, rtsp_url), daemon=True)
        t.start()
        threads.append(t)
    # Wait for all threads to finish
    for t in threads:
        t.join()
    
    # Clean up database connection pool
    if db:
        asyncio.run(db.close())
        logger.info("Database connection pool closed")


if __name__ == '__main__':
    main()
