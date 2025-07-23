#!/usr/bin/env python3
"""
Web server for Gack pose detection replay interface.
"""

import uvicorn
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from gack.web_interface import app

def main():
    load_dotenv()
    
    host = os.getenv('WEB_HOST', '0.0.0.0')
    port = int(os.getenv('WEB_PORT', 8000))
    
    print(f"Starting Gack web interface on http://{host}:{port}")
    print("Press Ctrl+C to stop")
    
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main() 