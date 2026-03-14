#!/usr/bin/env python3
"""Run the multi-agent dashboard server.

This script starts the FastAPI dashboard server for monitoring Design and Docs agents.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import uvicorn
from dashboard.backend import app


def main():
    """Run the dashboard server."""
    print("=" * 70)
    print("Multi-Agent Dashboard")
    print("=" * 70)
    print()
    print("Starting dashboard server...")
    print("Dashboard UI: http://localhost:8080")
    print("API Docs: http://localhost:8080/docs")
    print("Health Check: http://localhost:8080/api/health")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )


if __name__ == "__main__":
    main()
