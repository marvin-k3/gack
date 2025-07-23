import pytest
import asyncio
import tempfile
import os
from datetime import datetime
from gack.database import PoseDatabase

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

@pytest.mark.asyncio
async def test_save_and_retrieve_detection(temp_db):
    """Test saving and retrieving a detection."""
    db = PoseDatabase(temp_db)
    await db.init_db()
    
    # Sample detection data
    timestamp = datetime.now().isoformat()
    frame_number = 1
    video_timestamp = 1.5
    poses = [[[100, 200], [150, 250]]]  # One person with 2 keypoints
    confidences = [0.95]
    boxes = [[50, 100, 200, 300]]
    keypoint_confidences = [[0.9, 0.8]]
    
    # Save detection
    detection_id = await db.save_detection(
        timestamp=timestamp,
        frame_number=frame_number,
        video_timestamp=video_timestamp,
        poses=poses,
        confidences=confidences,
        boxes=boxes,
        keypoint_confidences=keypoint_confidences
    )
    
    assert detection_id > 0
    
    # Retrieve detection
    detection = await db.get_detection_by_id(detection_id)
    assert detection is not None
    assert detection["timestamp"] == timestamp
    assert detection["frame_number"] == frame_number
    assert detection["video_timestamp"] == video_timestamp
    assert detection["detection_data"]["poses"] == poses
    assert detection["detection_data"]["confidences"] == confidences
    assert detection["detection_data"]["boxes"] == boxes
    assert detection["detection_data"]["keypoint_confidences"] == keypoint_confidences

@pytest.mark.asyncio
async def test_get_latest_detections(temp_db):
    """Test retrieving latest detections."""
    db = PoseDatabase(temp_db)
    await db.init_db()
    
    # Save multiple detections
    for i in range(5):
        timestamp = datetime.now().isoformat()
        await db.save_detection(
            timestamp=timestamp,
            frame_number=i,
            video_timestamp=float(i),
            poses=[[[100, 200]]],
            confidences=[0.9],
            boxes=[[50, 100, 150, 200]],
            keypoint_confidences=[[0.8]]
        )
    
    # Get latest 3 detections
    detections = await db.get_latest_detections(limit=3)
    assert len(detections) == 3
    
    # Verify they're ordered by timestamp descending
    timestamps = [d["timestamp"] for d in detections]
    assert timestamps == sorted(timestamps, reverse=True)

@pytest.mark.asyncio
async def test_get_detection_stats(temp_db):
    """Test getting database statistics."""
    db = PoseDatabase(temp_db)
    await db.init_db()
    
    # Save some detections
    for i in range(3):
        timestamp = datetime.now().isoformat()
        await db.save_detection(
            timestamp=timestamp,
            frame_number=i,
            video_timestamp=float(i),
            poses=[[[100, 200]]],
            confidences=[0.9],
            boxes=[[50, 100, 150, 200]],
            keypoint_confidences=[[0.8]]
        )
    
    stats = await db.get_detection_stats()
    assert stats["total_detections"] == 3
    assert stats["average_poses_per_detection"] == 1.0
    assert stats["date_range"]["start"] is not None
    assert stats["date_range"]["end"] is not None

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"]) 