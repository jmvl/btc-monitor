#!/usr/bin/env python3
"""
BTC Monitor CLI wrapper script.

This script provides a convenient entry point for running BTC Monitor
from the project root directory.

Usage:
    ./cli.py [OPTIONS] COMMAND [ARGS]

Examples:
    ./cli.py monitor                    # Run continuous monitoring
    ./cli.py monitor --once             # Run single analysis
    ./cli.py analyze                    # Perform single analysis
    ./cli.py status                     # Show current trend
    ./cli.py history                    # Show past 10 analyses
    ./cli.py analyze --json             # Output as JSON
    ./cli.py monitor --verbose          # Enable debug logging
"""

import sys
from pathlib import Path

# Add src directory to path to allow imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from btc_monitor.cli import main

if __name__ == "__main__":
    main()
