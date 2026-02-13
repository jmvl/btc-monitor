"""Database initialization and utilities for BTC Monitor."""

from pathlib import Path
from typing import Union

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from btc_monitor.models import Base


# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "btc_monitor.db"


def get_engine(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> Engine:
    """
    Create a SQLAlchemy engine for the database.
    
    Args:
        db_path: Path to the SQLite database file. Defaults to btc_monitor.db in project root.
    
    Returns:
        SQLAlchemy engine instance.
    """
    if isinstance(db_path, str):
        db_path = Path(db_path)
    
    # Create directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use SQLite for simplicity
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,  # Set to True for SQL query logging
    )
    
    return engine


def init_db(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> None:
    """
    Initialize the database by creating all tables.
    
    Args:
        db_path: Path to the SQLite database file. Defaults to btc_monitor.db in project root.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    print(f"Database initialized at: {db_path}")


def get_session(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> Session:
    """
    Create a database session.
    
    Args:
        db_path: Path to the SQLite database file. Defaults to btc_monitor.db in project root.
    
    Returns:
        SQLAlchemy session instance.
    """
    engine = get_engine(db_path)
    Session = sessionmaker(bind=engine)
    return Session()


def main() -> None:
    """Main entry point for database initialization."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize BTC Monitor database")
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"Path to database file (default: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args()
    
    init_db(args.db_path)


if __name__ == "__main__":
    main()
