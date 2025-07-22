from gack.pose_stream import main
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Privacy preserving home monitoring")
    parser.add_argument("--stream", action="store_true", help="Stream the video to the web")
    args = parser.parse_args()
    main(args) 