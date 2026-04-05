"""Type stub file for btc_monitor.database."""

from pathlib import Path
from typing import Union

from sqlalchemy import Engine
from sqlalchemy.orm import Session

__all__ = ["DEFAULT_DB_PATH", "get_engine", "init_db", "get_session", "Session"]

DEFAULT_DB_PATH: Path

def get_engine(db_path: Union[Path, str] = ...) -> Engine: ...
def init_db(db_path: Union[Path, str] = ...) -> None: ...
def get_session(db_path: Union[Path, str] = ...) -> Session: ...
