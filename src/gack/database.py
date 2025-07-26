import aiosqlite
import json
import logging
from datetime import datetime, timedelta
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
                           detections: List[Dict[str, Any]]) -> int:
        """Save pose detections to the database."""
        detection_data = {
            "detections": detections
        }
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO detections (timestamp, frame_number, video_timestamp, detection_data, camera_name)
                VALUES (?, ?, ?, ?, ?)
            """, (timestamp, frame_number, video_timestamp, json.dumps(detection_data), camera_name))
            
            await db.commit()
            detection_id = cursor.lastrowid
            logger.debug(f"Saved detection {detection_id} with {len(detections)} detections for camera {camera_name}")
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
        """Get the latest detections for a specific camera."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, camera_name, timestamp, frame_number, video_timestamp, detection_data, created_at
                FROM detections 
                WHERE camera_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (camera_name, limit)) as cursor:
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
            
            # Average detections per frame
            async with db.execute("""
                SELECT AVG(json_array_length(detection_data, '$.detections')) as avg_detections
                FROM detections
            """) as cursor:
                avg_detections = (await cursor.fetchone())[0]
            
            return {
                "total_detections": total_detections,
                "date_range": {
                    "start": time_range[0] if time_range[0] else None,
                    "end": time_range[1] if time_range[1] else None
                },
                "average_detections_per_frame": avg_detections or 0
            }
    
    async def get_cameras(self) -> List[Dict[str, Any]]:
        """Get list of available cameras with their status."""
        async with aiosqlite.connect(self.db_path) as db:
            # Get unique cameras and their latest activity
            async with db.execute("""
                SELECT DISTINCT camera_name, 
                       MAX(timestamp) as last_seen,
                       COUNT(*) as detection_count
                FROM detections 
                GROUP BY camera_name
                ORDER BY last_seen DESC
            """) as cursor:
                rows = await cursor.fetchall()
                
                cameras = []
                for row in rows:
                    camera_name = row[0]
                    last_seen = row[1]
                    detection_count = row[2]
                    
                    # Determine status based on last activity (within last hour = live)
                    status = "live" if last_seen else "offline"
                    if last_seen:
                        try:
                            last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                            if (datetime.now().replace(tzinfo=last_seen_dt.tzinfo) - last_seen_dt).total_seconds() > 3600:
                                status = "offline"
                        except:
                            status = "offline"
                    
                    cameras.append({
                        "name": camera_name,
                        "status": status,
                        "last_seen": last_seen,
                        "detection_count": detection_count
                    })
                
                return cameras
    
    async def get_timeline_data(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get timeline data for the timeline view - recent detections across all cameras."""
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
                
                # Return in chronological order (oldest first) for timeline
                return list(reversed(detections))
    
    async def get_nearest_detection(self, camera_name: str, timestamp: str) -> Optional[Dict[str, Any]]:
        """Get the detection nearest to a specific timestamp for a camera."""
        try:
            target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return None
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Get the detection closest to the target timestamp
            async with db.execute("""
                SELECT id, camera_name, timestamp, frame_number, video_timestamp, detection_data, created_at
                FROM detections 
                WHERE camera_name = ?
                ORDER BY ABS(CAST((julianday(?) - julianday(timestamp)) * 24 * 60 * 60 AS INTEGER))
                LIMIT 1
            """, (camera_name, timestamp)) as cursor:
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

 

    async def get_nearest_detection_with_tolerance(self, camera_name: str, timestamp: str, tolerance_seconds: float) -> Optional[Dict[str, Any]]:
        """Get the detection nearest to a specific timestamp for a camera, but only if within tolerance."""
        try:
            target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return None
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Get the detection closest to the target timestamp
            async with db.execute("""
                SELECT id, camera_name, timestamp, frame_number, video_timestamp, detection_data, created_at
                FROM detections 
                WHERE camera_name = ?
                ORDER BY ABS(CAST((julianday(?) - julianday(timestamp)) * 24 * 60 * 60 AS INTEGER))
                LIMIT 1
            """, (camera_name, timestamp)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    # Check if the detection is within tolerance
                    # Handle timezone consistently - make both naive or both aware
                    detection_timestamp = row["timestamp"]
                    if detection_timestamp.endswith('Z'):
                        detection_timestamp = detection_timestamp.replace('Z', '+00:00')
                    
                    detection_time = datetime.fromisoformat(detection_timestamp)
                    
                    # Ensure both times have timezone info
                    if target_time.tzinfo is None:
                        target_time = target_time.replace(tzinfo=detection_time.tzinfo)
                    if detection_time.tzinfo is None:
                        detection_time = detection_time.replace(tzinfo=target_time.tzinfo)
                    
                    time_diff = abs((target_time - detection_time).total_seconds())
                    
                    if time_diff <= tolerance_seconds:
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