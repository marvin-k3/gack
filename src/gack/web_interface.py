from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import uvicorn
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager
import subprocess
import os
from gack.database import PoseDatabase

db = PoseDatabase()

def get_version_info():
    """Get version information including git branch and commit."""
    version_info = {
        "version": "0.1.0",  # From pyproject.toml
        "branch": "unknown",
        "commit": "unknown",
        "commit_short": "unknown"
    }
    
    try:
        # Get git branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        if result.returncode == 0:
            version_info["branch"] = result.stdout.strip()
        
        # Get full commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        if result.returncode == 0:
            version_info["commit"] = result.stdout.strip()
            version_info["commit_short"] = version_info["commit"][:8]
        
    except (subprocess.SubprocessError, FileNotFoundError):
        # Git not available or not a git repository
        pass
    
    return version_info

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html lang="en" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gack</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
        <style>
            .camera-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 0;
                margin-bottom: 1rem;
            }
            
            .camera-cell {
                background: #000;
                border: 1px solid var(--bs-border-color);
                border-radius: 0;
                overflow: hidden;
                position: relative;
            }
            
            .camera-canvas-container {
                position: relative;
                background: #000;
                text-align: center;
                width: 100%;
                height: 100%;
            }
            
            .timestamp-overlay {
                position: absolute;
                top: 0.5rem;
                left: 0.5rem;
                background: rgba(0, 0, 0, 0.8);
                color: #ffffff;
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
                font-size: 0.75rem;
                z-index: 10;
            }
            
            .camera-name-overlay {
                position: absolute;
                bottom: 0.5rem;
                left: 0.5rem;
                background: rgba(0, 0, 0, 0.8);
                color: #ffffff;
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
                font-size: 0.875rem;
                font-weight: bold;
                z-index: 10;
            }
            
            .camera-canvas {
                width: 100%;
                height: 100%;
                display: block;
            }
            
            .timeline {
                background: var(--bs-secondary-bg);
                border-top: 2px solid var(--bs-border-color);
                padding: 1rem;
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                z-index: 1000;
            }
            
            .timeline-controls {
                display: flex;
                gap: 0.5rem;
                align-items: center;
                margin-bottom: 0.5rem;
                flex-wrap: wrap;
            }
            
            .timeline-track {
                height: 40px;
                background: var(--bs-tertiary-bg);
                border-radius: 0.25rem;
                position: relative;
                cursor: pointer;
                border: 1px solid var(--bs-border-color);
            }
            
            .timeline-marker {
                position: absolute;
                top: 0;
                width: 2px;
                height: 100%;
                background: var(--bs-danger);
                z-index: 10;
            }
            
            .detection-segment {
                position: absolute;
                height: 100%;
                background: var(--bs-primary);
                border-radius: 0.25rem;
                opacity: 0.8;
                cursor: pointer;
            }
            
            .detection-segment:hover {
                opacity: 1;
            }
            
            .filter-bar {
                background-color: var(--bs-secondary-bg);
                padding: 1rem;
                margin-bottom: 1rem;
                border-radius: 0.375rem;
                border: 1px solid var(--bs-border-color);
            }
            
            .time-range-inputs {
                display: flex;
                gap: 0.5rem;
                align-items: center;
            }
            
            .time-range-inputs input {
                width: 120px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
            }
            
            .stat-card {
                background: var(--bs-body-bg);
                border: 1px solid var(--bs-border-color);
                border-radius: 0.375rem;
                padding: 1rem;
                text-align: center;
            }
            
            .stat-value {
                font-size: 2rem;
                font-weight: bold;
                color: var(--bs-primary);
            }
            
            .stat-label {
                color: var(--bs-secondary-color);
                font-size: 0.875rem;
            }
            
            .footer {
                background-color: var(--bs-secondary-bg);
                border-top: 1px solid var(--bs-border-color);
            }
            
            .footer code {
                background-color: var(--bs-tertiary-bg);
                padding: 0.125rem 0.25rem;
                border-radius: 0.25rem;
                font-size: 0.75rem;
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg border-bottom mb-4">
            <div class="container">
                <a class="navbar-brand" href="/">Gack</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav">
                        <li class="nav-item">
                            <a class="nav-link active" href="/">Cameras</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="#" onclick="switchTab('stats')">System Stats</a>
                        </li>
                    </ul>
                    <ul class="navbar-nav ms-auto">
                        <li class="nav-item">
                            <button class="btn btn-link nav-link" id="theme-toggle">
                                <i class="bi bi-moon-fill" id="theme-icon"></i>
                            </button>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>

        <div class="container mt-4">
            <div class="row mb-4">
                <div class="col">
                    <div class="filter-bar">
                        <form id="filter-form" class="row g-3">
                            <div class="col-md-3">
                                <label for="camera-filter" class="form-label">Camera</label>
                                <select class="form-select" id="camera-filter">
                                    <option value="">All Cameras</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label for="start-time" class="form-label">Start Time</label>
                                <input type="datetime-local" class="form-control" id="start-time">
                            </div>
                            <div class="col-md-3">
                                <label for="end-time" class="form-label">End Time</label>
                                <input type="datetime-local" class="form-control" id="end-time">
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">&nbsp;</label>
                                <div class="d-flex gap-2">
                                    <button type="button" class="btn btn-primary" onclick="loadByTimeRange()">Load Range</button>
                                    <button type="button" class="btn btn-secondary" onclick="resetFilters()">Reset</button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            </div>

            <div class="tab-content">
                <div id="cameras-tab" class="tab-pane active">
                    <div class="camera-grid" id="cameraGrid">
                        <div class="text-center">
                            <div class="spinner-border" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div id="stats-tab" class="tab-pane" style="display: none;">
                    <div class="stats-grid" id="stats">
                        <div class="text-center">
                            <div class="spinner-border" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="timeline">
            <div class="timeline-controls">
                <button class="btn btn-success" id="liveButton" onclick="toggleLiveMode()">
                    <i class="bi bi-broadcast"></i>
                    <span id="liveButtonText">Live</span>
                </button>
                <button class="btn btn-outline-secondary" onclick="loadTimelineData()">
                    <i class="bi bi-arrow-clockwise"></i>
                    Refresh
                </button>
                <span class="text-muted">|</span>
                <span class="text-muted">Timeline Controls</span>
            </div>
            <div class="timeline-track" id="timelineTrack">
                <div class="timeline-marker" id="timelineMarker" style="left: 50%;"></div>
            </div>
        </div>
        
        <footer class="footer mt-4 py-3 border-top">
            <div class="container text-center">
                <span class="text-muted">Gack Pose Detection System - Real-time pose detection and analysis</span>
                <br>
                <small class="text-muted" id="version-info">Loading version info...</small>
            </div>
        </footer>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            let cameras = [];
            let timelineData = [];
            let currentTime = null;
            let timelineStart = null;
            let timelineEnd = null;
            let liveStreamInterval = null;
            let isLiveMode = true;
            
            function switchTab(tabName) {
                // Hide all tab panes
                document.querySelectorAll('.tab-pane').forEach(pane => {
                    pane.style.display = 'none';
                });
                
                // Show selected tab pane
                document.getElementById(tabName + '-tab').style.display = 'block';
                
                // Update navigation
                document.querySelectorAll('.nav-link').forEach(link => {
                    link.classList.remove('active');
                });
                event.target.classList.add('active');
                
                // Load data for the tab
                if (tabName === 'stats') {
                    loadStats();
                }
            }
            
            async function initApp() {
                await loadStats();
                await loadCameras();
                await loadTimelineData();
                await loadVersionInfo();
                setupTimelineInteraction();
                startLiveStream();
            }
            
            async function loadVersionInfo() {
                try {
                    const versionInfo = await fetch('/api/version').then(r => r.json());
                    const versionElement = document.getElementById('version-info');
                    versionElement.innerHTML = `
                        v${versionInfo.version} | 
                        <span class="badge bg-secondary">${versionInfo.branch}</span> | 
                        <code class="text-muted">${versionInfo.commit_short}</code>
                    `;
                } catch (error) {
                    console.error('Error loading version info:', error);
                    document.getElementById('version-info').textContent = 'Version info unavailable';
                }
            }
            
            async function loadStats() {
                try {
                    const stats = await fetch('/api/stats').then(r => r.json());
                    document.getElementById('stats').innerHTML = `
                        <div class="stat-card">
                            <div class="stat-value">${stats.total_detections}</div>
                            <div class="stat-label">Total Detections</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.average_detections_per_frame.toFixed(2)}</div>
                            <div class="stat-label">Avg per Frame</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.date_range.start ? new Date(stats.date_range.start).toLocaleDateString() : 'N/A'}</div>
                            <div class="stat-label">Start Date</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${stats.date_range.end ? new Date(stats.date_range.end).toLocaleDateString() : 'N/A'}</div>
                            <div class="stat-label">End Date</div>
                        </div>
                    `;
                } catch (error) {
                    console.error('Error loading stats:', error);
                    document.getElementById('stats').innerHTML = `
                        <div class="alert alert-danger" role="alert">
                            Error loading statistics. Please try refreshing the page.
                        </div>
                    `;
                }
            }
            
            async function loadCameras() {
                try {
                    cameras = await fetch('/api/cameras').then(r => r.json());
                    renderCameraGrid();
                    updateCameraFilter();
                } catch (error) {
                    console.error('Error loading cameras:', error);
                    cameras = [];
                    renderCameraGrid();
                }
            }
            
            function updateCameraFilter() {
                const select = document.getElementById('camera-filter');
                const currentValue = select.value;
                
                // Clear existing options except "All Cameras"
                while (select.options.length > 1) {
                    select.remove(1);
                }

                // Add new options
                cameras.forEach(camera => {
                    const option = new Option(camera.name, camera.name);
                    select.add(option);
                });

                // Restore previous selection if it still exists
                if (currentValue) {
                    const cameraExists = cameras.some(camera => camera.name === currentValue);
                    if (cameraExists) {
                        select.value = currentValue;
                    }
                }
            }
            
            function renderCameraGrid() {
                const grid = document.getElementById('cameraGrid');
                if (cameras.length === 0) {
                    grid.innerHTML = `
                        <div class="col-12">
                            <div class="alert alert-info" role="alert">
                                No cameras available. Please check your configuration.
                            </div>
                        </div>
                    `;
                    return;
                }
                
                grid.innerHTML = cameras.map(camera => `
                    <div class="camera-cell">
                        <div class="camera-canvas-container">
                            <div class="timestamp-overlay" id="timestamp_${camera.name}">No data</div>
                            <div class="camera-name-overlay">${camera.name}</div>
                            <canvas id="canvas_${camera.name}" class="camera-canvas" width="640" height="360"></canvas>
                        </div>
                    </div>
                `).join('');
            }
            
            function startLiveStream() {
                if (liveStreamInterval) clearInterval(liveStreamInterval);
                liveStreamInterval = setInterval(async () => {
                    if (isLiveMode) {
                        for (const camera of cameras) {
                            await updateCamera(camera.name, 'live');
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
            
            async function updateCamera(cameraName, mode = 'live') {
                try {
                    let response;
                    if (mode === 'live') {
                        response = await fetch(`/api/detections/latest?camera_name=${encodeURIComponent(cameraName)}&limit=1`);
                    } else {
                        response = await fetch(`/api/detections/nearest?camera_name=${encodeURIComponent(cameraName)}&timestamp=${currentTime.toISOString()}&tolerance=0.1`);
                    }
                    
                    const data = await response.json();
                    const detection = Array.isArray(data) ? data[0] : data;
                    
                    if (detection) {
                        const time = new Date(detection.timestamp);
                        const detectionCount = detection.detection_data.detections?.length || 0;
                        updateTimestampOverlay(cameraName, time, detectionCount);
                        renderDetectionOnCanvas(cameraName, detection);
                    } else {
                        const time = mode === 'live' ? new Date() : currentTime;
                        updateTimestampOverlay(cameraName, time, 0);
                        clearCanvas(cameraName);
                    }
                } catch (error) {
                    console.error(`Error updating camera ${cameraName}:`, error);
                    const time = mode === 'live' ? new Date() : currentTime;
                    updateTimestampOverlay(cameraName, time, 0);
                    clearCanvas(cameraName);
                }
            }
            
            async function loadTimelineData() {
                try {
                    timelineData = await fetch('/api/timeline').then(r => r.json());
                    renderTimeline();
                } catch (error) {
                    console.error('Error loading timeline data:', error);
                }
            }
            
            function renderTimeline() {
                const track = document.getElementById('timelineTrack');
                track.querySelectorAll('.detection-segment').forEach(seg => seg.remove());
                
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
                document.getElementById('timelineTrack').addEventListener('click', (e) => {
                    const rect = e.target.getBoundingClientRect();
                    const percentage = ((e.clientX - rect.left) / rect.width) * 100;
                    
                    if (timelineStart && timelineEnd) {
                        const time = new Date(timelineStart.getTime() + (percentage / 100) * (timelineEnd - timelineStart));
                        jumpToTime(time);
                        if (isLiveMode) toggleLiveMode();
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
                    await updateCamera(camera.name, 'timeline');
                }
            }
            
            function renderDetectionOnCanvas(cameraName, detection) {
                const canvas = document.getElementById(`canvas_${cameraName}`);
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                const detections = detection.detection_data.detections || [];
                if (detections.length === 0) return;
                
                // Dark background and frame boundary
                ctx.fillStyle = 'rgba(20, 20, 20, 1)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
                ctx.lineWidth = 2;
                ctx.strokeRect(0, 0, canvas.width, canvas.height);
                
                const firstDetection = detections[0];
                const sourceWidth = firstDetection.source_frame_width || 1920;
                const sourceHeight = firstDetection.source_frame_height || 1080;
                
                const scale = Math.min(canvas.width / sourceWidth, canvas.height / sourceHeight);
                const scaledWidth = sourceWidth * scale;
                const scaledHeight = sourceHeight * scale;
                const offsetX = (canvas.width - scaledWidth) / 2;
                const offsetY = (canvas.height - scaledHeight) / 2;
                
                detections.forEach((personDetection) => {
                    const { confidence, bbox, keypoint_confidences, pose } = personDetection;
                    
                    // Bounding box
                    const [x1, y1, x2, y2] = bbox.map((coord, i) => 
                        (coord * scale) + (i % 2 === 0 ? offsetX : offsetY)
                    );
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${confidence})`;
                    ctx.lineWidth = Math.max(1, 2 * scale);
                    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                    
                    // Keypoints
                    pose.forEach((point, kpIndex) => {
                        if (keypoint_confidences[kpIndex] > 0.5) {
                            const x = (point[0] * scale) + offsetX;
                            const y = (point[1] * scale) + offsetY;
                            
                            ctx.fillStyle = `rgba(0, 255, 0, ${keypoint_confidences[kpIndex]})`;
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
                    
                    ctx.strokeStyle = `rgba(255, 0, 0, ${confidence})`;
                    ctx.lineWidth = Math.max(1, 1.5 * scale);
                    
                    skeleton.forEach(([start, end]) => {
                        if (start < pose.length && end < pose.length && 
                            keypoint_confidences[start] > 0.5 && keypoint_confidences[end] > 0.5) {
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
                    
                    overlay.textContent = detectionCount > 0 
                        ? `${formattedTime} (${detectionCount} detection${detectionCount > 1 ? 's' : ''})`
                        : formattedTime;
                }
            }
            
            function clearCanvas(cameraName) {
                const canvas = document.getElementById(`canvas_${cameraName}`);
                if (canvas) {
                    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
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
                    liveButton.className = 'btn btn-outline-secondary';
                    liveButtonText.textContent = 'Timeline';
                    stopLiveStream();
                }
            }
            
            async function loadByTimeRange() {
                const startTime = document.getElementById('startTime').value;
                const endTime = document.getElementById('endTime').value;
                const cameraFilter = document.getElementById('camera-filter').value;
                
                if (!startTime || !endTime) {
                    alert('Please select both start and end times');
                    return;
                }
                
                try {
                    const params = new URLSearchParams({
                        start_time: startTime,
                        end_time: endTime,
                        limit: '1000'
                    });
                    
                    if (cameraFilter) {
                        params.append('camera_name', cameraFilter);
                    }
                    
                    timelineData = await fetch(`/api/detections/timerange?${params.toString()}`).then(r => r.json());
                    renderTimeline();
                    isLiveMode = false;
                    toggleLiveMode();
                } catch (error) {
                    console.error('Error loading time range:', error);
                }
            }
            
            function resetFilters() {
                document.getElementById('camera-filter').value = '';
                document.getElementById('start-time').value = '';
                document.getElementById('end-time').value = '';
                loadTimelineData();
            }
            
            // Theme toggle functionality
            document.addEventListener('DOMContentLoaded', function() {
                const themeToggle = document.getElementById('theme-toggle');
                const themeIcon = document.getElementById('theme-icon');
                const htmlElement = document.documentElement;
                
                // Check if system prefers dark mode
                const prefersDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
                
                // Check if theme preference is stored in localStorage
                const savedTheme = localStorage.getItem('theme');
                
                if (savedTheme) {
                    // Use saved preference if available
                    htmlElement.setAttribute('data-bs-theme', savedTheme);
                    updateThemeIcon(savedTheme);
                } else {
                    // Use system preference if no saved preference
                    const systemTheme = prefersDarkMode ? 'dark' : 'light';
                    htmlElement.setAttribute('data-bs-theme', systemTheme);
                    updateThemeIcon(systemTheme);
                }
                
                // Watch for system theme changes
                if (window.matchMedia) {
                    const colorSchemeQuery = window.matchMedia('(prefers-color-scheme: dark)');
                    
                    colorSchemeQuery.addEventListener('change', (e) => {
                        // Only update if user hasn't set a preference
                        if (!localStorage.getItem('theme')) {
                            const newTheme = e.matches ? 'dark' : 'light';
                            htmlElement.setAttribute('data-bs-theme', newTheme);
                            updateThemeIcon(newTheme);
                        }
                    });
                }
                
                // Toggle theme when button is clicked
                themeToggle.addEventListener('click', function() {
                    const currentTheme = htmlElement.getAttribute('data-bs-theme');
                    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                    
                    htmlElement.setAttribute('data-bs-theme', newTheme);
                    localStorage.setItem('theme', newTheme);
                    
                    updateThemeIcon(newTheme);
                });
                
                // Update the icon based on current theme
                function updateThemeIcon(theme) {
                    if (theme === 'dark') {
                        themeIcon.classList.remove('bi-sun-fill');
                        themeIcon.classList.add('bi-moon-fill');
                    } else {
                        themeIcon.classList.remove('bi-moon-fill');
                        themeIcon.classList.add('bi-sun-fill');
                    }
                }
                
                // Initialize the application
                initApp();
            });
        </script>
    </body>
    </html>
    """

@app.get("/api/stats")
async def get_stats():
    return await db.get_detection_stats()

@app.get("/api/cameras")
async def get_cameras():
    return await db.get_cameras()

@app.get("/api/timeline")
async def get_timeline(camera_name: Optional[str] = Query(None)):
    return await db.get_timeline_data()

@app.get("/api/detections/latest")
async def get_latest_detections(camera_name: str = Query(...), limit: int = Query(50, ge=1, le=1000)):
    return await db.get_latest_detections(camera_name, limit)

@app.get("/api/detections/timerange")
async def get_detections_by_timerange(
    camera_name: Optional[str] = Query(None),
    start_time: str = Query(...),
    end_time: str = Query(...),
    limit: Optional[int] = Query(50, ge=1, le=1000)
):
    try:
        datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    return await db.get_detections_by_timerange(camera_name, start_time, end_time, limit)

@app.get("/api/detections/nearest")
async def get_nearest_detection(
    camera_name: str = Query(...),
    timestamp: str = Query(...),
    tolerance: Optional[float] = Query(None)
):
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
    detection = await db.get_detection_by_id(detection_id)
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    return detection

@app.get("/api/version")
async def get_version():
    return get_version_info()

def run_web_interface(host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_web_interface() 