from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import uvicorn
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager
from gack.database import PoseDatabase

# Initialize database
db = PoseDatabase()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    await db.init_db()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML interface."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gack Pose Detection</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background-color: #1a1a1a; 
                color: #ffffff; 
                margin: 0; 
                padding: 20px;
            }
            
            .header {
                background: #2c3e50;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            
            .stats {
                background: #2c2c2c;
                border: 1px solid #34495e;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
            }
            
            .camera-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 20px;
                margin-bottom: 120px;
            }
            
            .camera-cell {
                background: #2c2c2c;
                border: 1px solid #34495e;
                border-radius: 8px;
                overflow: hidden;
            }
            
            .camera-header {
                background: #34495e;
                padding: 10px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .camera-canvas-container {
                position: relative;
                background: #000;
                padding: 10px;
                text-align: center;
            }
            
            .timestamp-overlay {
                position: absolute;
                top: 10px;
                left: 10px;
                background: rgba(0, 0, 0, 0.8);
                color: #ffffff;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 10;
            }
            
            .camera-canvas {
                width: 100%;
                max-width: 640px;
                height: 480px;
                border: 1px solid #34495e;
                border-radius: 4px;
            }
            
            .timeline {
                background: #2c2c2c;
                border-top: 2px solid #34495e;
                padding: 15px;
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                z-index: 1000;
            }
            
            .timeline-controls {
                display: flex;
                gap: 10px;
                align-items: center;
                margin-bottom: 10px;
            }
            
            .timeline-track {
                height: 40px;
                background: #34495e;
                border-radius: 4px;
                position: relative;
                cursor: pointer;
            }
            
            .timeline-marker {
                position: absolute;
                top: 0;
                width: 2px;
                height: 100%;
                background: #e74c3c;
                z-index: 10;
            }
            
            .detection-segment {
                position: absolute;
                height: 100%;
                background: #3498db;
                border-radius: 4px;
                opacity: 0.8;
                cursor: pointer;
            }
            
            .btn {
                background: #3498db;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
            }
            
            .btn:hover {
                background: #2980b9;
            }
            
            .btn-success {
                background: #27ae60;
            }
            
            .btn-success:hover {
                background: #229954;
            }
            
            input[type="datetime-local"] {
                background: #34495e;
                border: 1px solid #2c3e50;
                color: #ecf0f1;
                border-radius: 4px;
                padding: 8px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Gack Pose Detection Console</h1>
        </div>
        
        <div class="stats" id="stats">
            <h3>System Statistics</h3>
            <div id="stats-content">Loading...</div>
        </div>
        
        <div class="camera-grid" id="cameraGrid">
            <!-- Cameras will be inserted here -->
        </div>
        
        <div class="timeline">
            <div class="timeline-controls">
                <button class="btn" id="liveButton" onclick="toggleLiveMode()">
                    <span id="liveButtonText">Live</span>
                </button>
                <button class="btn" onclick="loadTimelineData()">Refresh</button>
                <input type="datetime-local" id="startTime">
                <input type="datetime-local" id="endTime">
                <button class="btn" onclick="loadByTimeRange()">Load Range</button>
            </div>
            <div class="timeline-track" id="timelineTrack">
                <div class="timeline-marker" id="timelineMarker" style="left: 50%;"></div>
            </div>
        </div>
        
        <script>
            let cameras = [];
            let timelineData = [];
            let currentTime = null;
            let timelineStart = null;
            let timelineEnd = null;
            let liveStreamInterval = null;
            let isLiveMode = true;
            
            async function initApp() {
                await loadStats();
                await loadCameras();
                await loadTimelineData();
                setupTimelineInteraction();
                startLiveStream();
            }
            
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    
                    document.getElementById('stats-content').innerHTML = `
                        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;">
                            <div>
                                <h4>${stats.total_detections}</h4>
                                <small>Total Detections</small>
                            </div>
                            <div>
                                <h4>${stats.average_detections_per_frame.toFixed(2)}</h4>
                                <small>Avg per Frame</small>
                            </div>
                            <div>
                                <h4>${stats.date_range.start ? new Date(stats.date_range.start).toLocaleDateString() : 'N/A'}</h4>
                                <small>Start Date</small>
                            </div>
                            <div>
                                <h4>${stats.date_range.end ? new Date(stats.date_range.end).toLocaleDateString() : 'N/A'}</h4>
                                <small>End Date</small>
                            </div>
                        </div>
                    `;
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            async function loadCameras() {
                try {
                    const response = await fetch('/api/cameras');
                    cameras = await response.json();
                    renderCameraGrid();
                } catch (error) {
                    console.error('Error loading cameras:', error);
                    cameras = [];
                    renderCameraGrid();
                }
            }
            
            function renderCameraGrid() {
                const grid = document.getElementById('cameraGrid');
                grid.innerHTML = '';
                
                cameras.forEach(camera => {
                    const cell = document.createElement('div');
                    cell.className = 'camera-cell';
                    cell.innerHTML = `
                        <div class="camera-header">
                            <h4>${camera.name}</h4>
                            <span>${camera.status}</span>
                        </div>
                        <div class="camera-canvas-container">
                            <div class="timestamp-overlay" id="timestamp_${camera.name}">No data</div>
                            <canvas id="canvas_${camera.name}" class="camera-canvas" width="640" height="480"></canvas>
                        </div>
                    `;
                    grid.appendChild(cell);
                });
            }
            
            function startLiveStream() {
                if (liveStreamInterval) clearInterval(liveStreamInterval);
                
                liveStreamInterval = setInterval(async () => {
                    if (isLiveMode) {
                        for (const camera of cameras) {
                            await updateCameraLive(camera.name);
                        }
                    }
                }, 1000);
            }
            
            function stopLiveStream() {
                if (liveStreamInterval) {
                    clearInterval(liveStreamInterval);
                    liveStreamInterval = null;
                }
            }
            
            async function updateCameraLive(cameraName) {
                try {
                    const response = await fetch(`/api/detections/latest?camera_name=${encodeURIComponent(cameraName)}&limit=1`);
                    const detections = await response.json();
                    
                    if (detections && detections.length > 0) {
                        const latestDetection = detections[0];
                        const detectionTime = new Date(latestDetection.timestamp);
                        const detectionCount = latestDetection.detection_data.detections ? latestDetection.detection_data.detections.length : 0;
                        
                        updateTimestampOverlay(cameraName, detectionTime, detectionCount);
                        renderDetectionOnCanvas(cameraName, latestDetection);
                    } else {
                        const now = new Date();
                        updateTimestampOverlay(cameraName, now, 0);
                        clearCanvas(cameraName);
                    }
                } catch (error) {
                    console.error(`Error updating camera ${cameraName}:`, error);
                    const now = new Date();
                    updateTimestampOverlay(cameraName, now, 0);
                    clearCanvas(cameraName);
                }
            }
            
            async function loadTimelineData() {
                try {
                    const response = await fetch('/api/timeline');
                    timelineData = await response.json();
                    renderTimeline();
                } catch (error) {
                    console.error('Error loading timeline data:', error);
                }
            }
            
            function renderTimeline() {
                const track = document.getElementById('timelineTrack');
                const existingSegments = track.querySelectorAll('.detection-segment');
                existingSegments.forEach(seg => seg.remove());
                
                if (timelineData.length === 0) return;
                
                timelineStart = new Date(timelineData[0].timestamp);
                timelineEnd = new Date(timelineData[timelineData.length - 1].timestamp);
                const totalDuration = timelineEnd - timelineStart;
                
                // Group detections by 5-minute intervals
                const groupedDetections = [];
                const timeThreshold = 5 * 60 * 1000;
                
                timelineData.forEach(detection => {
                    const time = new Date(detection.timestamp);
                    let addedToGroup = false;
                    
                    for (let group of groupedDetections) {
                        const groupTime = new Date(group.timestamp);
                        if (Math.abs(time - groupTime) < timeThreshold) {
                            group.count++;
                            group.latest = Math.max(group.latest, time);
                            addedToGroup = true;
                            break;
                        }
                    }
                    
                    if (!addedToGroup) {
                        groupedDetections.push({
                            timestamp: detection.timestamp,
                            time: time,
                            count: 1,
                            latest: time
                        });
                    }
                });
                
                groupedDetections.forEach(group => {
                    const position = ((group.time - timelineStart) / totalDuration) * 100;
                    const width = Math.max(2, Math.min(8, group.count * 0.5));
                    
                    const segment = document.createElement('div');
                    segment.className = 'detection-segment';
                    segment.style.left = position + '%';
                    segment.style.width = width + '%';
                    segment.title = `${group.count} detection(s) at ${group.time.toLocaleTimeString()}`;
                    segment.onclick = () => jumpToTime(group.time);
                    
                    track.appendChild(segment);
                });
            }
            
            function setupTimelineInteraction() {
                const track = document.getElementById('timelineTrack');
                
                track.addEventListener('click', (e) => {
                    const rect = track.getBoundingClientRect();
                    const clickX = e.clientX - rect.left;
                    const percentage = (clickX / rect.width) * 100;
                    
                    if (timelineStart && timelineEnd) {
                        const time = new Date(timelineStart.getTime() + (percentage / 100) * (timelineEnd - timelineStart));
                        jumpToTime(time);
                        if (isLiveMode) {
                            toggleLiveMode();
                        }
                    }
                });
            }
            
            async function jumpToTime(time) {
                currentTime = time;
                isLiveMode = false;
                const marker = document.getElementById('timelineMarker');
                
                if (timelineStart && timelineEnd) {
                    const position = ((time - timelineStart) / (timelineEnd - timelineStart)) * 100;
                    marker.style.left = position + '%';
                }
                
                for (const camera of cameras) {
                    await updateCameraView(camera.name, time);
                }
            }
            
            async function updateCameraView(cameraName, time) {
                try {
                    const response = await fetch(`/api/detections/nearest?camera_name=${encodeURIComponent(cameraName)}&timestamp=${time.toISOString()}&tolerance=0.1`);
                    const detection = await response.json();
                    
                    if (detection) {
                        const detectionCount = detection.detection_data.detections ? detection.detection_data.detections.length : 0;
                        updateTimestampOverlay(cameraName, time, detectionCount);
                        renderDetectionOnCanvas(cameraName, detection);
                    } else {
                        clearCanvas(cameraName);
                        updateTimestampOverlay(cameraName, time, 0);
                    }
                } catch (error) {
                    console.error(`Error updating camera ${cameraName}:`, error);
                    clearCanvas(cameraName);
                    updateTimestampOverlay(cameraName, time, 0);
                }
            }
            
            function renderDetectionOnCanvas(cameraName, detection) {
                const canvas = document.getElementById(`canvas_${cameraName}`);
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                const detections = detection.detection_data.detections || [];
                if (detections.length === 0) return;
                
                // Dark background
                ctx.fillStyle = 'rgba(20, 20, 20, 1)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                // Frame boundary
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
                ctx.lineWidth = 2;
                ctx.strokeRect(0, 0, canvas.width, canvas.height);
                
                const firstDetection = detections[0];
                const sourceWidth = firstDetection.source_frame_width || 1920;
                const sourceHeight = firstDetection.source_frame_height || 1080;
                
                const scaleX = canvas.width / sourceWidth;
                const scaleY = canvas.height / sourceHeight;
                const scale = Math.min(scaleX, scaleY);
                
                const scaledWidth = sourceWidth * scale;
                const scaledHeight = sourceHeight * scale;
                const offsetX = (canvas.width - scaledWidth) / 2;
                const offsetY = (canvas.height - scaledHeight) / 2;
                
                detections.forEach((personDetection) => {
                    const conf = personDetection.confidence;
                    const box = personDetection.bbox;
                    const kp_conf = personDetection.keypoint_confidences;
                    const pose = personDetection.pose;
                    
                    // Bounding box
                    const x1 = (box[0] * scale) + offsetX;
                    const y1 = (box[1] * scale) + offsetY;
                    const x2 = (box[2] * scale) + offsetX;
                    const y2 = (box[3] * scale) + offsetY;
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${conf})`;
                    ctx.lineWidth = Math.max(1, 2 * scale);
                    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                    
                    // Keypoints
                    pose.forEach((point, kpIndex) => {
                        if (kp_conf[kpIndex] > 0.5) {
                            const x = (point[0] * scale) + offsetX;
                            const y = (point[1] * scale) + offsetY;
                            
                            ctx.fillStyle = `rgba(0, 255, 0, ${kp_conf[kpIndex]})`;
                            ctx.beginPath();
                            ctx.arc(x, y, Math.max(1, 3 * scale), 0, 2 * Math.PI);
                            ctx.fill();
                        }
                    });
                    
                    // Skeleton
                    const skeleton = [
                        [5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12],
                        [11, 12], [11, 13], [13, 15], [12, 14], [14, 16]
                    ];
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${conf})`;
                    ctx.lineWidth = Math.max(1, 1.5 * scale);
                    
                    skeleton.forEach(([start, end]) => {
                        if (start < pose.length && end < pose.length && 
                            kp_conf[start] > 0.5 && kp_conf[end] > 0.5) {
                            const x1 = (pose[start][0] * scale) + offsetX;
                            const y1 = (pose[start][1] * scale) + offsetY;
                            const x2 = (pose[end][0] * scale) + offsetX;
                            const y2 = (pose[end][1] * scale) + offsetY;
                            
                            ctx.beginPath();
                            ctx.moveTo(x1, y1);
                            ctx.lineTo(x2, y2);
                            ctx.stroke();
                        }
                    });
                });
            }
            
            function updateTimestampOverlay(cameraName, time, detectionCount = 0) {
                const overlay = document.getElementById(`timestamp_${cameraName}`);
                if (overlay) {
                    const formattedTime = time.toLocaleString('en-US', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });
                    
                    if (detectionCount > 0) {
                        overlay.textContent = `${formattedTime} (${detectionCount} detection${detectionCount > 1 ? 's' : ''})`;
                    } else {
                        overlay.textContent = formattedTime;
                    }
                }
            }
            
            function clearCanvas(cameraName) {
                const canvas = document.getElementById(`canvas_${cameraName}`);
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
            }
            
            function toggleLiveMode() {
                isLiveMode = !isLiveMode;
                const liveButton = document.getElementById('liveButton');
                const liveButtonText = document.getElementById('liveButtonText');
                
                if (isLiveMode) {
                    liveButton.className = 'btn btn-success';
                    liveButtonText.textContent = 'Live';
                    startLiveStream();
                } else {
                    liveButton.className = 'btn';
                    liveButtonText.textContent = 'Timeline';
                    stopLiveStream();
                }
            }
            
            async function loadByTimeRange() {
                const startTime = document.getElementById('startTime').value;
                const endTime = document.getElementById('endTime').value;
                
                if (!startTime || !endTime) {
                    alert('Please select both start and end times');
                    return;
                }
                
                try {
                    const response = await fetch(`/api/detections/timerange?start_time=${startTime}&end_time=${endTime}&limit=1000`);
                    timelineData = await response.json();
                    renderTimeline();
                    isLiveMode = false;
                    toggleLiveMode();
                } catch (error) {
                    console.error('Error loading time range:', error);
                }
            }
            
            document.addEventListener('DOMContentLoaded', initApp);
        </script>
    </body>
    </html>
    """

@app.get("/api/stats")
async def get_stats():
    """Get database statistics."""
    return await db.get_detection_stats()

@app.get("/api/cameras")
async def get_cameras():
    """Get list of available cameras."""
    return await db.get_cameras()

@app.get("/api/timeline")
async def get_timeline(camera_name: Optional[str] = Query(None, description="Optional camera name to filter by")):
    """Get timeline data for the timeline view."""
    return await db.get_timeline_data()

@app.get("/api/detections/latest")
async def get_latest_detections(camera_name: str = Query(..., description="Camera name to filter by"), limit: int = Query(50, ge=1, le=1000)):
    """Get the latest detections for a specific camera."""
    return await db.get_latest_detections(camera_name, limit)

@app.get("/api/detections/timerange")
async def get_detections_by_timerange(
    camera_name: str = Query(..., description="Camera name to filter by"),
    start_time: str = Query(..., description="Start time in ISO format"),
    end_time: str = Query(..., description="End time in ISO format"),
    limit: Optional[int] = Query(50, ge=1, le=1000)
):
    """Get detections within a time range for a specific camera."""
    try:
        datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    return await db.get_detections_by_timerange(camera_name, start_time, end_time, limit)

@app.get("/api/detections/nearest")
async def get_nearest_detection(
    camera_name: str = Query(..., description="Camera name to filter by"),
    timestamp: str = Query(..., description="Timestamp in ISO format"),
    tolerance: Optional[float] = Query(None, description="Tolerance in seconds - if provided, only return detection within this tolerance")
):
    """Get the detection nearest to a specific timestamp for a camera."""
    try:
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    if tolerance is not None:
        return await db.get_nearest_detection_with_tolerance(camera_name, timestamp, tolerance)
    else:
        return await db.get_nearest_detection(camera_name, timestamp)

@app.get("/api/detections/{detection_id}")
async def get_detection(detection_id: int):
    """Get a specific detection by ID."""
    detection = await db.get_detection_by_id(detection_id)
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    return detection

def run_web_interface(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI web interface."""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_web_interface() 