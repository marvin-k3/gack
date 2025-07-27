# Gack

Privacy-preserving home monitoring using pose detection.

## Features

- Real-time pose detection from RTSP streams
- Privacy-preserving (only stores pose data, not video frames)
- SQLite database storage for detection replay
- Web interface for viewing historical detections
- Configurable detection frequency and output options

## Installation

1. Install dependencies:
```bash
pip install -e .
```

2. Create a `.env` file with your configuration:
```env
UNIFI_RTSPS_URL=rtsp://your-camera-url
FPS=1
SHOW_ORIGINAL=False
SAVE_TO_DB=True
LOG_LEVEL=INFO
```

## Usage

### Running Pose Detection

Start the pose detection stream:
```bash
gack
```

This will:
- Connect to your RTSP stream
- Run pose detection at the specified FPS
- Save detection data to SQLite database (if enabled)
- Output processed video to `outdata/output.mp4`

### Web Interface

Start the web interface to view historical detections:
```bash
gack-web
```

Then open http://localhost:8000 in your browser.

The web interface provides:
- Database statistics
- Browse latest detections
- Search detections by time range
- Visual replay of pose detections
- Interactive canvas showing skeletons and keypoints

### Environment Variables

- `UNIFI_RTSPS_URL`: RTSP stream URL for your camera
- `FPS`: Detection frequency (default: 1)
- `SHOW_ORIGINAL`: Show original video background (default: False)
- `SAVE_TO_DB`: Save detections to database (default: True)
- `LOG_LEVEL`: Logging level (default: INFO)
- `KNOWN_FACES_DIR`: Directory of labeled face images for optional face recognition
- `WEB_HOST`: Web interface host (default: 0.0.0.0)
- `WEB_PORT`: Web interface port (default: 8000)

## Database Schema

The SQLite database stores:
- Detection timestamps
- Frame numbers and video timestamps
- Pose keypoints (17 points per person)
- Detection confidences
- Bounding boxes
- Keypoint confidence scores

## API Endpoints

- `GET /api/stats` - Database statistics
- `GET /api/detections/latest?limit=50` - Latest detections
- `GET /api/detections/timerange?start_time=...&end_time=...` - Detections by time range
- `GET /api/detections/{id}` - Specific detection by ID

## Development

Run tests:
```bash
pytest tests/
```

## Privacy

This system is designed for privacy preservation:
- Only pose keypoints are stored, not video frames
- Facial recognition is optional and disabled by default
- Detection data can be easily deleted from the database
- Local storage only (no cloud uploads)
