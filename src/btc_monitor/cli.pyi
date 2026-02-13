"""Type stubs for btc_monitor.cli module."""

import argparse
from typing import Any, Dict, Optional

from btc_monitor.config import Config
from btc_monitor.database import Session
from btc_monitor.fetchers import PriceFetcher
from btc_monitor.analyzer import TrendAnalyzer


def setup_logging(verbose: bool, config: Optional[Config] = None) -> None: ...

def format_output(data: Dict[str, Any], as_json: bool = False) -> str: ...

def cmd_monitor(args: argparse.Namespace) -> None: ...

def run_monitoring_cycle(
    config: Config,
    session: Session,
    price_fetcher: PriceFetcher,
    trend_analyzer: TrendAnalyzer,
    output_json: bool = False,
) -> bool: ...

def cmd_analyze(args: argparse.Namespace) -> None: ...

def cmd_status(args: argparse.Namespace) -> None: ...

def cmd_history(args: argparse.Namespace) -> None: ...

def main() -> None: ...
