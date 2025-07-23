import aiosqlite
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

class PoseDatabase:
    def __init__(self, db_path: str = "outdata/pose_detections.db"):
        self.db_path = db_path
        self._ensure_db_dir()
    
    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    async def init_db(self):
        """Initialize the database with required tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    frame_number INTEGER NOT NULL,
                    video_timestamp REAL NOT NULL,
                    detection_data TEXT NOT NULL,
                    camera_name TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_detections_timestamp 
                ON detections(timestamp)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_detections_video_timestamp 
                ON detections(video_timestamp)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_detections_camera_name
                ON detections(camera_name)
            """)
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def save_detection(self, 
                           camera_name: str,
                           timestamp: str, 
                           frame_number: int, 
                           video_timestamp: float,
                           poses: List[Dict[str, Any]], 
                           confidences: List[float], 
                           boxes: List[List[float]], 
                           keypoint_confidences: List[List[float]]) -> int:
        """Save a pose detection to the database."""
        detection_data = {
            "poses": poses,
            "confidences": confidences,
            "boxes": boxes,
            "keypoint_confidences": keypoint_confidences
        }
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO detections (timestamp, frame_number, video_timestamp, detection_data, camera_name)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, frame_number, video_timestamp, json.dumps(detection_data), camera_name))
            
            await db.commit()
            detection_id = cursor.lastrowid
            logger.debug(f"Saved detection {detection_id} with {len(poses)} poses for camera {camera_name}")
            return detection_id
    
    async def get_detections_by_timerange(self, 
                                        camera_name: str,
                                        start_time: str, 
                                        end_time: str, 
                                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get detections within a time range."""
        query = """
            SELECT id, camera_name, timestamp, frame_number, video_timestamp, detection_data, created_at
            FROM detections 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, (start_time, end_time)) as cursor:
                rows = await cursor.fetchall()
                
                detections = []
                for row in rows:
                    detection = {
                        "id": row["id"],
                        "camera_name": row["camera_name"],
                        "timestamp": row["timestamp"],
                        "frame_number": row["frame_number"],
                        "video_timestamp": row["video_timestamp"],
                        "detection_data": json.loads(row["detection_data"]),
                        "created_at": row["created_at"]
                    }
                    detections.append(detection)
                
                return detections
    
    async def get_detection_by_id(self, detection_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific detection by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, camera_name, timestamp, frame_number, video_timestamp, detection_data, created_at
                FROM detections 
                WHERE id = ?
            """, (detection_id,)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    return {
                        "id": row["id"],
                        "camera_name": row["camera_name"],
                        "timestamp": row["timestamp"],
                        "frame_number": row["frame_number"],
                        "video_timestamp": row["video_timestamp"],
                        "detection_data": json.loads(row["detection_data"]),
                        "created_at": row["created_at"]
                    }
                return None
    
    async def get_latest_detections(self, camera_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get the latest detections."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, camera_name, timestamp, frame_number, video_timestamp, detection_data, created_at
                FROM detections 
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                
                detections = []
                for row in rows:
                    detection = {
                        "id": row["id"],
                        "camera_name": row["camera_name"],
                        "timestamp": row["timestamp"],
                        "frame_number": row["frame_number"],
                        "video_timestamp": row["video_timestamp"],
                        "detection_data": json.loads(row["detection_data"]),
                        "created_at": row["created_at"]
                    }
                    detections.append(detection)
                
                return detections
    
    async def get_detection_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        async with aiosqlite.connect(self.db_path) as db:
            # Total detections
            async with db.execute("SELECT COUNT(*) FROM detections") as cursor:
                total_detections = (await cursor.fetchone())[0]
            
            # Date range
            async with db.execute("""
                SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time 
                FROM detections
            """) as cursor:
                time_range = await cursor.fetchone()
            
            # Average poses per detection
            async with db.execute("""
                SELECT AVG(json_array_length(detection_data, '$.poses')) as avg_poses
                FROM detections
            """) as cursor:
                avg_poses = (await cursor.fetchone())[0]
            
            return {
                "total_detections": total_detections,
                "date_range": {
                    "start": time_range[0] if time_range[0] else None,
                    "end": time_range[1] if time_range[1] else None
                },
                "average_poses_per_detection": avg_poses or 0
            } 