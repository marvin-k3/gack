#!/usr/bin/env python3
import argparse
import subprocess
import tempfile
import time
import os
import sys
import requests
import signal

MEDIA_PORT = 8554
API_PORT = 9997
RTSP_PATH = "test"

def wait_for_mediamtx(api_port, timeout=30):
    url = f"http://localhost:{api_port}/v3/paths/list"
    print(f"Checking MediaMTX API at {url}...")
    for i in range(int(timeout * 5)):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                print(f"MediaMTX is ready! (after {i * 0.2:.1f}s)")
                return True
        except requests.exceptions.ConnectionError:
            # Expected while MediaMTX is starting
            pass
        except Exception as e:
            print(f"Unexpected error checking MediaMTX: {e}")
        time.sleep(0.2)
        if i % 25 == 0:  # Print status every 5 seconds
            print(f"Still waiting for MediaMTX... ({i * 0.2:.1f}s elapsed)")
    return False

def main():
    parser = argparse.ArgumentParser(description="Stream a video file to a local RTSP server for testing.")
    parser.add_argument("video", help="Path to the video file to stream")
    parser.add_argument("--mediamtx", default="mediamtx", help="Path to mediamtx binary")
    parser.add_argument("--media-port", type=int, default=MEDIA_PORT, help="RTSP port")
    parser.add_argument("--api-port", type=int, default=API_PORT, help="MediaMTX API port")
    parser.add_argument("--rtsp-path", default=RTSP_PATH, help="RTSP path (default: test)")
    args = parser.parse_args()

    # 1. Start MediaMTX
    config_content = f"""
paths:
  all:
    source: publisher
api: yes
apiAddress: :{args.api_port}
rtspAddress: :{args.media_port}
# Disable other protocols to avoid port conflicts
hlsAddress: ""
webrtcAddress: ""
rtmpAddress: ""
srtAddress: ""
"""
    config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)
    config_file.write(config_content)
    config_file.close()
    mediamtx_proc = subprocess.Popen(
        [args.mediamtx, config_file.name],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    print(f"Started MediaMTX (pid {mediamtx_proc.pid})...")

    try:
        print("Waiting for MediaMTX to be ready...")
        if not wait_for_mediamtx(args.api_port):
            print("MediaMTX did not start in time.", file=sys.stderr)
            
            # Check if the process is still running
            if mediamtx_proc.poll() is not None:
                print("MediaMTX process has exited. Output:", file=sys.stderr)
                stdout, stderr = mediamtx_proc.communicate()
                if stdout:
                    print("STDOUT:", stdout.decode(), file=sys.stderr)
                if stderr:
                    print("STDERR:", stderr.decode(), file=sys.stderr)
            else:
                print("MediaMTX process is still running but API is not responding.", file=sys.stderr)
            
            mediamtx_proc.terminate()
            sys.exit(1)

        # 2. Start FFmpeg to stream the video
        rtsp_url = f"rtsp://localhost:{args.media_port}/{args.rtsp_path}"
        ffmpeg_cmd = [
            "ffmpeg", "-re", "-stream_loop", "-1", "-i", args.video,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-g", "10",
            "-f", "rtsp", rtsp_url
        ]
        print(f"Streaming {args.video} to {rtsp_url} ...")
        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        print("\nReady! You can now point Gack at this RTSP URL:")
        print(f"  {rtsp_url}\n")
        print("Press Ctrl+C to stop streaming.")

        # Wait until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")

        ffmpeg_proc.terminate()
        ffmpeg_proc.wait(timeout=5)
    finally:
        mediamtx_proc.terminate()
        try:
            mediamtx_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mediamtx_proc.kill()
        os.unlink(config_file.name)

if __name__ == "__main__":
    main()