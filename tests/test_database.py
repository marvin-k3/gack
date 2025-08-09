import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timezone
from gack.database import PoseDatabase
from gack.pose_stream import Detection

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.mark.asyncio
async def test_database_initialization(temp_db):
    """Test database initialization."""
    db = PoseDatabase(temp_db)
    await db.init_db()
    
    # Verify database file was created
    assert os.path.exists(temp_db)
    
    # Clean up
    await db.close()

@pytest.mark.asyncio
async def test_save_and_retrieve_detection(temp_db):
    """Test saving and retrieving a detection."""
    db = PoseDatabase(temp_db)
    await db.init_db()
    
    # Sample detection data
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    frame_number = 1
    video_timestamp = 1.5
    
    # Create Detection objects
    detection1 = Detection(
        pose=[(100.0, 200.0), (150.0, 250.0)],
        confidence=0.95,
        bbox=(50.0, 100.0, 200.0, 300.0),
        keypoint_confidences=[0.9, 0.8]
    )
    detections = [detection1.model_dump()]
    
    # Save detection
    detection_id = await db.save_detection(
        'test_camera',
        timestamp=timestamp,
        frame_number=frame_number,
        video_timestamp=video_timestamp,
        detections=detections
    )
    
    assert detection_id > 0
    
    # Retrieve detection
    detection = await db.get_detection_by_id(detection_id)
    assert detection is not None
    assert detection["timestamp"] == timestamp
    assert detection["frame_number"] == frame_number
    assert detection["video_timestamp"] == video_timestamp
    assert len(detection["detection_data"]["detections"]) == 1
    saved_detection = detection["detection_data"]["detections"][0]
    # Note: Pydantic serializes tuples as lists, so we compare with lists
    assert saved_detection["pose"] == [[100.0, 200.0], [150.0, 250.0]]
    assert saved_detection["confidence"] == 0.95
    assert saved_detection["bbox"] == [50.0, 100.0, 200.0, 300.0]
    assert saved_detection["keypoint_confidences"] == [0.9, 0.8]
    
    # Clean up
    await db.close()

@pytest.mark.asyncio
async def test_get_latest_detections(temp_db):
    """Test retrieving latest detections."""
    db = PoseDatabase(temp_db)
    await db.init_db()
    
    # Save multiple detections
    for i in range(5):
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
    
    # Get latest 3 detections
    detections = await db.get_latest_detections('test_camera', limit=3)
    assert len(detections) == 3
    
    # Verify they're ordered by timestamp descending
    timestamps = [d["timestamp"] for d in detections]
    assert timestamps == sorted(timestamps, reverse=True)
    
    # Clean up
    await db.close()

@pytest.mark.asyncio
async def test_get_detection_stats(temp_db):
    """Test getting database statistics."""
    db = PoseDatabase(temp_db)
    await db.init_db()
    
    # Save some detections
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
    
    stats = await db.get_detection_stats()
    assert stats["total_detections"] == 3
    assert stats["average_detections_per_frame"] == 1.0
    assert stats["date_range"]["start"] is not None
    assert stats["date_range"]["end"] is not None
    
    # Clean up
    await db.close()

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"]) 