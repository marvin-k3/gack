import pytest
import asyncio
from datetime import datetime, timezone
from gack.web_interface import app, db
from gack.pose_stream import Detection
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.mark.asyncio
async def test_web_interface_stats():
    """Test that the web interface stats endpoint works with new Detection structure."""
    # Initialize the database
    await db.init_db()
    
    # Add some test detections
    for i in range(3):
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        detection = Detection(
            pose=[(100.0, 200.0), (150.0, 250.0)],
            confidence=0.9,
            bbox=(50.0, 100.0, 150.0, 200.0),
            keypoint_confidences=[0.8, 0.7]
        )
        await db.save_detection(
            'test_camera',
            timestamp=timestamp,
            frame_number=i,
            video_timestamp=float(i),
            detections=[detection.model_dump()]
        )
    
    # Test the stats endpoint
    with TestClient(app) as client:
        response = client.get("/api/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "total_detections" in stats
        assert "average_detections_per_frame" in stats
        assert "date_range" in stats

@pytest.mark.asyncio
async def test_web_interface_latest_detections():
    """Test that the web interface latest detections endpoint works with new Detection structure."""
    # Initialize the database
    await db.init_db()
    
    # Add some test detections
    for i in range(3):
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        detection = Detection(
            pose=[(100.0, 200.0)],
            confidence=0.9,
            bbox=(50.0, 100.0, 150.0, 200.0),
            keypoint_confidences=[0.8]
        )
        await db.save_detection(
            'test_camera',
            timestamp=timestamp,
            frame_number=i,
            video_timestamp=float(i),
            detections=[detection.model_dump()]
        )
    
    # Test the latest detections endpoint
    with TestClient(app) as client:
        response = client.get("/api/detections/latest?camera_name=test_camera&limit=10")
        assert response.status_code == 200
        detections = response.json()
        assert len(detections) > 0
        
        # Check that the detection data has the new structure
        for detection in detections:
            assert "detection_data" in detection
            assert "detections" in detection["detection_data"]
            assert isinstance(detection["detection_data"]["detections"], list)

def test_web_interface_root_endpoint(client):
    """Test that the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Gack" in response.text 