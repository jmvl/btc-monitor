"""
Entry point for running BTC Monitor as a module.

Usage:
    python -m btc_monitor [options]

This allows the package to be run as:
    python -m btc_monitor --config config.yaml --once
"""

from btc_monitor.main import main
import sys

if __name__ == "__main__":
    sys.exit(main())
