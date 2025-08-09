import aiosqlite
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import os
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseConnectionPool:
    """Connection pool for SQLite database with WAL mode enabled."""
    
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection with WAL mode enabled."""
        conn = await aiosqlite.connect(self.db_path)
        # Enable WAL mode for better concurrency
        await conn.execute("PRAGMA journal_mode=WAL")
        # Set other performance optimizations
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA cache_size=10000")
        await conn.execute("PRAGMA temp_store=MEMORY")
        return conn
    
    async def initialize(self):
        """Initialize the connection pool."""
        async with self._lock:
            if self._initialized:
                return
            
            # Create initial connections
            for _ in range(self.max_connections):
                conn = await self._create_connection()
                await self._pool.put(conn)
            
            self._initialized = True
            logger.info(f"Database connection pool initialized with {self.max_connections} connections")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if not self._initialized:
            await self.initialize()
        
        conn = await self._pool.get()
        try:
            yield conn
        finally:
            # Return connection to pool
            await self._pool.put(conn)
    
    async def close(self):
        """Close all connections in the pool."""
        async with self._lock:
            if not self._initialized:
                return
            
            while not self._pool.empty():
                conn = await self._pool.get()
                await conn.close()
            
            self._initialized = False
            logger.info("Database connection pool closed")

class PoseDatabase:
    def __init__(self, db_path: str = "outdata/pose_detections.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._pool = DatabaseConnectionPool(db_path)
    
    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    async def init_db(self):
        """Initialize the database with required tables."""
        async with self._pool.get_connection() as db:
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
        
        async with self._pool.get_connection() as db:
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
        
        async with self._pool.get_connection() as db:
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
        async with self._pool.get_connection() as db:
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
        async with self._pool.get_connection() as db:
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
        async with self._pool.get_connection() as db:
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
        async with self._pool.get_connection() as db:
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
                            if last_seen_dt.tzinfo is None:
                                last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                            # Consider the camera offline if no detections in the last hour
                            if (datetime.now(timezone.utc) - last_seen_dt).total_seconds() > 3600:
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
        async with self._pool.get_connection() as db:
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
            if target_time.tzinfo is None:
                target_time = target_time.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        
        async with self._pool.get_connection() as db:
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
            if target_time.tzinfo is None:
                target_time = target_time.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        
        async with self._pool.get_connection() as db:
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
                    detection_timestamp = row["timestamp"].replace('Z', '+00:00')
                    detection_time = datetime.fromisoformat(detection_timestamp)
                    if detection_time.tzinfo is None:
                        detection_time = detection_time.replace(tzinfo=timezone.utc)

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
    
    async def close(self):
        """Close the database connection pool."""
        await self._pool.close() 