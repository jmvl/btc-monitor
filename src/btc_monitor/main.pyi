"""
Type stubs for main BTC Monitor script.
"""

from typing import Optional
from btc_monitor.config import Config
from btc_monitor.database import Session
from btc_monitor.fetchers import PriceFetcher
from btc_monitor.analyzer import TrendAnalyzer


def signal_handler(signum: int, frame: Optional[object]) -> None: ...


def setup_logging(config_file: str, log_level: str, log_file: str) -> None: ...


def run_monitoring_cycle(
    config: Config, session: Session, price_fetcher: PriceFetcher, trend_analyzer: TrendAnalyzer
) -> bool: ...


def main(
    config_file: Optional[str] = None,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    once: bool = False,
) -> int: ...
