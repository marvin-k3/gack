from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import Optional, List
from datetime import datetime, timedelta
import json
from gack.database import PoseDatabase

app = FastAPI(title="Gack Pose Detection Replay", version="1.0.0")

# Initialize database
db = PoseDatabase()

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await db.init_db()

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML interface."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gack Pose Detection Replay</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .stats { background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .detection { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
            .detection:hover { background: #f9f9f9; }
            .person { margin: 10px 0; padding: 10px; background: #e8f4f8; border-radius: 3px; }
            .controls { margin: 20px 0; }
            button { padding: 10px 15px; margin: 5px; cursor: pointer; }
            input, select { padding: 8px; margin: 5px; }
            .canvas-container { text-align: center; margin: 20px 0; }
            canvas { border: 1px solid #ccc; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Gack Pose Detection Replay</h1>
            
            <div class="stats" id="stats">
                <h3>Database Statistics</h3>
                <div id="stats-content">Loading...</div>
            </div>
            
            <div class="controls">
                <h3>Controls</h3>
                <button onclick="loadLatest()">Load Latest Detections</button>
                <button onclick="loadByTimeRange()">Load by Time Range</button>
                <br>
                <input type="datetime-local" id="startTime" placeholder="Start Time">
                <input type="datetime-local" id="endTime" placeholder="End Time">
                <input type="number" id="limit" placeholder="Limit" value="50">
            </div>
            
            <div class="canvas-container">
                <canvas id="poseCanvas" width="800" height="600"></canvas>
            </div>
            
            <div id="detections"></div>
        </div>
        
        <script>
            let currentDetections = [];
            let currentIndex = 0;
            const canvas = document.getElementById('poseCanvas');
            const ctx = canvas.getContext('2d');
            
            async function loadStats() {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                document.getElementById('stats-content').innerHTML = `
                    <p><strong>Total Detections:</strong> ${stats.total_detections}</p>
                    <p><strong>Date Range:</strong> ${stats.date_range.start || 'N/A'} to ${stats.date_range.end || 'N/A'}</p>
                    <p><strong>Average Poses per Detection:</strong> ${stats.average_poses_per_detection.toFixed(2)}</p>
                `;
            }
            
            async function loadLatest() {
                const limit = document.getElementById('limit').value || 50;
                const camera_name = document.querySelector('.controls input[type="datetime-local"]').value; // Assuming camera_name is the datetime-local input
                const response = await fetch(`/api/detections/latest?camera_name=${camera_name}&limit=${limit}`);
                const detections = await response.json();
                displayDetections(detections);
            }
            
            async function loadByTimeRange() {
                const startTime = document.getElementById('startTime').value;
                const endTime = document.getElementById('endTime').value;
                const limit = document.getElementById('limit').value || 50;
                const camera_name = document.querySelector('.controls input[type="datetime-local"]').value; // Assuming camera_name is the datetime-local input
                
                if (!startTime || !endTime) {
                    alert('Please select both start and end times');
                    return;
                }
                
                const response = await fetch(`/api/detections/timerange?camera_name=${camera_name}&start_time=${startTime}&end_time=${endTime}&limit=${limit}`);
                const detections = await response.json();
                displayDetections(detections);
            }
            
            function displayDetections(detections) {
                currentDetections = detections;
                currentIndex = 0;
                
                const container = document.getElementById('detections');
                container.innerHTML = `<h3>Detections (${detections.length})</h3>`;
                
                detections.forEach((detection, index) => {
                    const div = document.createElement('div');
                    div.className = 'detection';
                    div.innerHTML = `
                        <h4>Detection ${detection.id} - ${detection.timestamp}</h4>
                        <p><strong>Camera:</strong> ${detection.camera_name || 'N/A'}</p>
                        <p>Frame: ${detection.frame_number}, Video Time: ${detection.video_timestamp.toFixed(2)}s</p>
                        <p>People detected: ${detection.detection_data.poses.length}</p>
                        <button onclick="showDetection(${index})">Show Detection</button>
                    `;
                    container.appendChild(div);
                });
                
                if (detections.length > 0) {
                    showDetection(0);
                }
            }
            
            function showDetection(index) {
                if (index < 0 || index >= currentDetections.length) return;
                
                currentIndex = index;
                const detection = currentDetections[index];
                
                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                // Draw poses
                const poses = detection.detection_data.poses;
                const confidences = detection.detection_data.confidences;
                const boxes = detection.detection_data.boxes;
                const keypoint_confidences = detection.detection_data.keypoint_confidences;
                
                // Scale factor to fit poses on canvas
                const scale = Math.min(canvas.width / 640, canvas.height / 480);
                const offsetX = (canvas.width - 640 * scale) / 2;
                const offsetY = (canvas.height - 480 * scale) / 2;
                
                poses.forEach((person, personIndex) => {
                    const conf = confidences[personIndex];
                    const box = boxes[personIndex];
                    const kp_conf = keypoint_confidences[personIndex];
                    
                    // Draw bounding box
                    const x1 = (box[0] * scale) + offsetX;
                    const y1 = (box[1] * scale) + offsetY;
                    const x2 = (box[2] * scale) + offsetX;
                    const y2 = (box[3] * scale) + offsetY;
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${conf})`;
                    ctx.lineWidth = 2;
                    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                    
                    // Draw keypoints
                    person.forEach((point, kpIndex) => {
                        if (kp_conf[kpIndex] > 0.5) {
                            const x = (point[0] * scale) + offsetX;
                            const y = (point[1] * scale) + offsetY;
                            
                            ctx.fillStyle = `rgba(0, 255, 0, ${kp_conf[kpIndex]})`;
                            ctx.beginPath();
                            ctx.arc(x, y, 3, 0, 2 * Math.PI);
                            ctx.fill();
                        }
                    });
                    
                    // Draw skeleton
                    const skeleton = [
                        [5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12],
                        [11, 12], [11, 13], [13, 15], [12, 14], [14, 16]
                    ];
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${conf})`;
                    ctx.lineWidth = 2;
                    
                    skeleton.forEach(([start, end]) => {
                        if (start < person.length && end < person.length && 
                            kp_conf[start] > 0.5 && kp_conf[end] > 0.5) {
                            const x1 = (person[start][0] * scale) + offsetX;
                            const y1 = (person[start][1] * scale) + offsetY;
                            const x2 = (person[end][0] * scale) + offsetX;
                            const y2 = (person[end][1] * scale) + offsetY;
                            
                            ctx.beginPath();
                            ctx.moveTo(x1, y1);
                            ctx.lineTo(x2, y2);
                            ctx.stroke();
                        }
                    });
                });
                
                // Update detection info
                const infoDiv = document.createElement('div');
                infoDiv.innerHTML = `
                    <h4>Currently Showing: Detection ${detection.id}</h4>
                    <p><strong>Camera:</strong> ${detection.camera_name || 'N/A'}</p>
                    <p>Timestamp: ${detection.timestamp}</p>
                    <p>People: ${poses.length}</p>
                    <button onclick="showDetection(${index - 1})" ${index === 0 ? 'disabled' : ''}>Previous</button>
                    <button onclick="showDetection(${index + 1})" ${index === currentDetections.length - 1 ? 'disabled' : ''}>Next</button>
                `;
                
                const existingInfo = document.querySelector('.current-detection-info');
                if (existingInfo) {
                    existingInfo.remove();
                }
                infoDiv.className = 'current-detection-info';
                document.querySelector('.canvas-container').appendChild(infoDiv);
            }
            
            // Load stats on page load
            loadStats();
        </script>
    </body>
    </html>
    """

@app.get("/api/stats")
async def get_stats():
    """Get database statistics."""
    return await db.get_detection_stats()

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