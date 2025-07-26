from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import Optional, List
from datetime import datetime, timedelta
import json
from contextlib import asynccontextmanager
from gack.database import PoseDatabase

# Initialize database
db = PoseDatabase()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    await db.init_db()
    yield
    # Shutdown (if needed)

app = FastAPI(title="Gack Pose Detection Replay", version="1.0.0", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML interface."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gack Pose Detection Replay</title>
        <!-- Bootstrap CSS -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-ENjdO4Dr2bkBIFxQpeoA6DQD5Bv0O6p3p9ctb1z9+7oWl1p4ylwF0R8F5r5p6M7g" crossorigin="anonymous">
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                background-color: #1a1a1a; 
                color: #ffffff; 
                margin: 0; 
                padding: 0; 
            }
            
            .nvr-header {
                background: linear-gradient(135deg, #2c3e50, #34495e);
                padding: 15px 0;
                border-bottom: 2px solid #3498db;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }
            
            .nvr-title {
                color: #ecf0f1;
                margin: 0;
                font-weight: 300;
                text-transform: uppercase;
                letter-spacing: 2px;
            }
            
            .camera-grid {
                padding: 20px 0;
                min-height: 60vh;
            }
            
            .camera-cell {
                background: #2c2c2c;
                border: 2px solid #34495e;
                border-radius: 8px;
                margin-bottom: 20px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                transition: all 0.3s ease;
            }
            
            .camera-cell:hover {
                border-color: #3498db;
                box-shadow: 0 6px 20px rgba(52, 152, 219, 0.3);
            }
            
            .camera-header {
                background: linear-gradient(90deg, #34495e, #2c3e50);
                padding: 10px 15px;
                border-bottom: 1px solid #34495e;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .camera-name {
                color: #ecf0f1;
                font-weight: 600;
                margin: 0;
                font-size: 14px;
            }
            
            .camera-status {
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
            }
            
            .status-live {
                background: #27ae60;
                color: white;
            }
            
            .status-offline {
                background: #e74c3c;
                color: white;
            }
            
            .camera-canvas-container {
                position: relative;
                background: #000;
                text-align: center;
                padding: 10px;
            }
            
            .timestamp-overlay {
                position: absolute;
                top: 15px;
                left: 15px;
                background: rgba(0, 0, 0, 0.8);
                color: #ffffff;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                z-index: 10;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            
            .camera-canvas {
                max-width: 100%;
                height: auto;
                border: 1px solid #34495e;
                border-radius: 4px;
            }
            
            .timeline-container {
                background: #2c2c2c;
                border-top: 2px solid #34495e;
                padding: 20px 0;
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                z-index: 1000;
            }
            
            .timeline-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding: 0 20px;
            }
            
            .timeline-controls {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            
            .timeline-scroll {
                overflow-x: auto;
                padding: 10px 20px;
                background: #1a1a1a;
                border-radius: 8px;
                margin: 0 20px;
                position: relative;
            }
            
            .timeline-track {
                height: 60px;
                background: #34495e;
                border-radius: 4px;
                position: relative;
                min-width: 2000px;
            }
            
            .timeline-marker {
                position: absolute;
                top: 0;
                width: 2px;
                height: 100%;
                background: #e74c3c;
                z-index: 10;
                transition: left 0.3s ease;
            }
            
            .detection-segment {
                position: absolute;
                height: 100%;
                background: linear-gradient(90deg, #3498db, #2980b9);
                border-radius: 4px;
                opacity: 0.9;
                cursor: pointer;
                transition: all 0.3s ease;
                border: 1px solid rgba(255, 255, 255, 0.3);
                min-width: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            }
            
            .detection-segment:hover {
                opacity: 1;
                background: linear-gradient(90deg, #5dade2, #3498db);
                transform: scaleY(1.1);
                box-shadow: 0 4px 8px rgba(52, 152, 219, 0.4);
            }
            
            .loading-spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #3498db;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .stats-panel {
                background: #2c2c2c;
                border: 1px solid #34495e;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
            }
            
            .btn-nvr {
                background: linear-gradient(135deg, #3498db, #2980b9);
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            
            .btn-nvr:hover {
                background: linear-gradient(135deg, #2980b9, #1f5f8b);
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(52, 152, 219, 0.4);
            }
            
            .form-control-nvr {
                background: #34495e;
                border: 1px solid #2c3e50;
                color: #ecf0f1;
                border-radius: 6px;
                padding: 8px 12px;
            }
            
            .form-control-nvr:focus {
                background: #2c3e50;
                border-color: #3498db;
                color: #ecf0f1;
                box-shadow: 0 0 0 0.2rem rgba(52, 152, 219, 0.25);
            }
            
            /* Responsive adjustments */
            @media (max-width: 768px) {
                .camera-grid {
                    padding: 10px 0;
                }
                
                .timeline-container {
                    padding: 15px 0;
                }
                
                .timeline-scroll {
                    margin: 0 10px;
                }
            }
        </style>
    </head>
    <body>
        <!-- Header -->
        <div class="nvr-header">
            <div class="container">
                <h1 class="nvr-title">Gack Pose Detection Console</h1>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="container">
            <!-- Stats Panel -->
            <div class="stats-panel" id="stats">
                <h5 class="text-light mb-3">System Statistics</h5>
                <div id="stats-content" class="row">
                    <div class="col-md-3">
                        <div class="text-center">
                            <div class="loading-spinner"></div>
                            <small class="text-muted">Loading...</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Camera Grid -->
            <div class="camera-grid">
                <div class="row" id="cameraGrid">
                    <!-- Dynamic camera cells will be inserted here -->
                </div>
            </div>
        </div>
        
        <!-- Timeline -->
        <div class="timeline-container">
            <div class="timeline-header">
                <h6 class="text-light mb-0">Timeline Navigation</h6>
                <div class="timeline-controls">
                    <button class="btn btn-nvr btn-sm" onclick="loadTimelineData()">
                        <i class="bi bi-arrow-clockwise"></i> Refresh
                    </button>
                    <input type="datetime-local" class="form-control form-control-nvr form-control-sm" id="startTime" style="width: 200px;">
                    <input type="datetime-local" class="form-control form-control-nvr form-control-sm" id="endTime" style="width: 200px;">
                    <button class="btn btn-nvr btn-sm" onclick="loadByTimeRange()">Load Range</button>
                </div>
            </div>
            <div class="timeline-scroll">
                <div class="timeline-track" id="timelineTrack">
                    <div class="timeline-marker" id="timelineMarker" style="left: 50%;"></div>
                    <!-- Detection segments will be added here -->
                </div>
            </div>
        </div>
        
        <!-- Bootstrap JS -->
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-C6RzsynM9kWDrMNeT87bh95OGNyZPhcTNXj1NW7RuBCsyN/o0jlpcV8Qyq46cDfL" crossorigin="anonymous"></script>
        
        <script>
            let cameras = [];
            let timelineData = [];
            let currentTime = null;
            let timelineStart = null;
            let timelineEnd = null;
            
            // Initialize the application
            async function initApp() {
                await loadStats();
                await loadCameras();
                await loadTimelineData();
                setupTimelineInteraction();
            }
            
            // Load system statistics
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const stats = await response.json();
                    
                    document.getElementById('stats-content').innerHTML = `
                        <div class="col-md-3">
                            <div class="text-center">
                                <h4 class="text-primary">${stats.total_detections}</h4>
                                <small class="text-muted">Total Detections</small>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="text-center">
                                <h4 class="text-success">${stats.average_detections_per_frame.toFixed(2)}</h4>
                                <small class="text-muted">Avg per Frame</small>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="text-center">
                                <h4 class="text-info">${stats.date_range.start ? new Date(stats.date_range.start).toLocaleDateString() : 'N/A'}</h4>
                                <small class="text-muted">Start Date</small>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="text-center">
                                <h4 class="text-warning">${stats.date_range.end ? new Date(stats.date_range.end).toLocaleDateString() : 'N/A'}</h4>
                                <small class="text-muted">End Date</small>
                            </div>
                        </div>
                    `;
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            // Load available cameras
            async function loadCameras() {
                try {
                    const response = await fetch('/api/cameras');
                    cameras = await response.json();
                    renderCameraGrid();
                } catch (error) {
                    console.error('Error loading cameras:', error);
                    // Fallback to test camera if API fails
                    cameras = [{ name: 'test_camera', status: 'live' }];
                    renderCameraGrid();
                }
            }
            
            // Render camera grid based on screen size
            function renderCameraGrid() {
                const grid = document.getElementById('cameraGrid');
                grid.innerHTML = '';
                
                cameras.forEach((camera, index) => {
                    const colClass = getResponsiveColClass();
                    const cell = document.createElement('div');
                    cell.className = colClass;
                    cell.innerHTML = `
                        <div class="camera-cell">
                            <div class="camera-header">
                                <h6 class="camera-name">${camera.name}</h6>
                                <span class="camera-status status-${camera.status}">${camera.status}</span>
                            </div>
                            <div class="camera-canvas-container">
                                <div class="timestamp-overlay" id="timestamp_${camera.name}">No data</div>
                                <canvas id="canvas_${camera.name}" class="camera-canvas" width="320" height="240"></canvas>
                            </div>
                        </div>
                    `;
                    grid.appendChild(cell);
                });
            }
            
            // Get responsive column class based on screen size
            function getResponsiveColClass() {
                const width = window.innerWidth;
                if (width < 768) return 'col-12'; // Mobile: 1 per row
                if (width < 1200) return 'col-md-6'; // Tablet: 2 per row
                return 'col-lg-4 col-xl-3'; // Desktop: 3-4 per row
            }
            
            // Load timeline data
            async function loadTimelineData() {
                try {
                    const response = await fetch('/api/timeline');
                    timelineData = await response.json();
                    renderTimeline();
                } catch (error) {
                    console.error('Error loading timeline data:', error);
                }
            }
            
            // Render timeline with detection segments
            function renderTimeline() {
                const track = document.getElementById('timelineTrack');
                const existingSegments = track.querySelectorAll('.detection-segment');
                existingSegments.forEach(seg => seg.remove());
                
                if (timelineData.length === 0) return;
                
                timelineStart = new Date(timelineData[0].timestamp);
                timelineEnd = new Date(timelineData[timelineData.length - 1].timestamp);
                const totalDuration = timelineEnd - timelineStart;
                
                // Group detections that are close together
                const groupedDetections = [];
                const timeThreshold = 5 * 60 * 1000; // 5 minutes in milliseconds
                
                timelineData.forEach(detection => {
                    const time = new Date(detection.timestamp);
                    
                    // Check if this detection is close to an existing group
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
                
                // Create segments for grouped detections
                groupedDetections.forEach(group => {
                    const position = ((group.time - timelineStart) / totalDuration) * 100;
                    
                    // Calculate width based on detection count and time span
                    const timeSpan = group.latest - group.time;
                    const baseWidth = Math.max(2, Math.min(8, group.count * 0.5)); // 2-8% width
                    const timeWidth = (timeSpan / totalDuration) * 100;
                    const width = Math.max(baseWidth, timeWidth);
                    
                    const segment = document.createElement('div');
                    segment.className = 'detection-segment';
                    segment.style.left = position + '%';
                    segment.style.width = width + '%';
                    segment.title = `${group.count} detection(s) starting at ${group.time.toLocaleTimeString()}`;
                    segment.onclick = () => jumpToTime(group.time); // This already jumps to the first detection
                    
                    track.appendChild(segment);
                });
            }
            
            // Setup timeline interaction
            function setupTimelineInteraction() {
                const track = document.getElementById('timelineTrack');
                const marker = document.getElementById('timelineMarker');
                
                track.addEventListener('click', (e) => {
                    const rect = track.getBoundingClientRect();
                    const clickX = e.clientX - rect.left;
                    const percentage = (clickX / rect.width) * 100;
                    
                    if (timelineStart && timelineEnd) {
                        const time = new Date(timelineStart.getTime() + (percentage / 100) * (timelineEnd - timelineStart));
                        jumpToTime(time);
                    }
                });
            }
            
            // Jump to specific time
            async function jumpToTime(time) {
                currentTime = time;
                const marker = document.getElementById('timelineMarker');
                
                if (timelineStart && timelineEnd) {
                    const position = ((time - timelineStart) / (timelineEnd - timelineStart)) * 100;
                    marker.style.left = position + '%';
                }
                
                // Update all camera views
                for (const camera of cameras) {
                    await updateCameraView(camera.name, time);
                }
            }
            
            // Update camera view for specific time
            async function updateCameraView(cameraName, time) {
                try {
                    // Update timestamp overlay
                    updateTimestampOverlay(cameraName, time);
                    
                    // Use a very small tolerance (0.1 seconds) to only show detections very close to the exact time
                    const response = await fetch(`/api/detections/nearest?camera_name=${encodeURIComponent(cameraName)}&timestamp=${time.toISOString()}&tolerance=0.1`);
                    const detection = await response.json();
                    
                    if (detection) {
                        renderDetectionOnCanvas(cameraName, detection);
                    } else {
                        clearCanvas(cameraName);
                    }
                } catch (error) {
                    console.error(`Error updating camera ${cameraName}:`, error);
                    clearCanvas(cameraName);
                }
            }
            
            // Render detection on canvas
            function renderDetectionOnCanvas(cameraName, detection) {
                const canvas = document.getElementById(`canvas_${cameraName}`);
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                const detections = detection.detection_data.detections || [];
                if (detections.length === 0) return;
                
                // Scale factor to fit poses on canvas
                const scale = Math.min(canvas.width / 640, canvas.height / 480);
                const offsetX = (canvas.width - 640 * scale) / 2;
                const offsetY = (canvas.height - 480 * scale) / 2;
                
                detections.forEach((personDetection) => {
                    const conf = personDetection.confidence;
                    const box = personDetection.bbox;
                    const kp_conf = personDetection.keypoint_confidences;
                    const pose = personDetection.pose;
                    
                    // Draw bounding box
                    const x1 = (box[0] * scale) + offsetX;
                    const y1 = (box[1] * scale) + offsetY;
                    const x2 = (box[2] * scale) + offsetX;
                    const y2 = (box[3] * scale) + offsetY;
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${conf})`;
                    ctx.lineWidth = 2;
                    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                    
                    // Draw keypoints
                    pose.forEach((point, kpIndex) => {
                        if (kp_conf[kpIndex] > 0.5) {
                            const x = (point[0] * scale) + offsetX;
                            const y = (point[1] * scale) + offsetY;
                            
                            ctx.fillStyle = `rgba(0, 255, 0, ${kp_conf[kpIndex]})`;
                            ctx.beginPath();
                            ctx.arc(x, y, 2, 0, 2 * Math.PI);
                            ctx.fill();
                        }
                    });
                    
                    // Draw skeleton
                    const skeleton = [
                        [5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12],
                        [11, 12], [11, 13], [13, 15], [12, 14], [14, 16]
                    ];
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${conf})`;
                    ctx.lineWidth = 1;
                    
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
            
            // Update timestamp overlay
            function updateTimestampOverlay(cameraName, time) {
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
                    overlay.textContent = formattedTime;
                }
            }
            
            // Clear canvas
            function clearCanvas(cameraName) {
                const canvas = document.getElementById(`canvas_${cameraName}`);
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
                
                // Update timestamp overlay to show "No data"
                const overlay = document.getElementById(`timestamp_${cameraName}`);
                if (overlay) {
                    overlay.textContent = 'No data';
                }
            }
            
            // Load by time range
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
                } catch (error) {
                    console.error('Error loading time range:', error);
                }
            }
            
            // Handle window resize
            window.addEventListener('resize', () => {
                renderCameraGrid();
            });
            
            // Initialize app when page loads
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
        # Validate datetime format
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