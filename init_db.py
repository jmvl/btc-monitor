#!/usr/bin/env python3
"""Standalone script to initialize the BTC Monitor database."""

import sys
from pathlib import Path

# Add src to path so we can import btc_monitor
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from btc_monitor.database import init_db

if __name__ == "__main__":
    # Initialize database with default path
    db_path = Path(__file__).parent / "btc_monitor.db"
    print(f"Initializing database at: {db_path}")
    init_db(db_path)
    print("Database initialization complete!")
