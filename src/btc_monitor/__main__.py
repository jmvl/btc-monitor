"""
Entry point for running BTC Monitor as a module.

Usage:
    python -m btc_monitor [OPTIONS] COMMAND [ARGS]

This allows the package to be run as:
    python -m btc_monitor monitor
    python -m btc_monitor analyze --json
    python -m btc_monitor status
    python -m btc_monitor history --count 20
"""

from btc_monitor.cli import main

if __name__ == "__main__":
    main()
