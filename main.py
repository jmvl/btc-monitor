#!/usr/bin/env python3
"""
BTC Monitor - Main entry point script.

Usage:
    python main.py [options]
    ./main.py [options] (after chmod +x)

This script provides a convenient entry point to run BTC Monitor
from the project root directory.
"""

import sys
from pathlib import Path

# Add src to path so we can import btc_monitor
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from btc_monitor.main import main

if __name__ == "__main__":
    sys.exit(main())
