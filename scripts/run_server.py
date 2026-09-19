"""CLI entrypoint to launch the UMLdoc live defense presentation server.

Usage:
    python scripts/run_server.py
    python scripts/run_server.py --port 8080
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from umldoc.server.app import run_server


def main():
    parser = argparse.ArgumentParser(description="Launch UMLdoc Live Presentation Server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, blocking=True)


if __name__ == "__main__":
    main()
