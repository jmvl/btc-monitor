"""Type stubs for fetchers.py."""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional, Union

from btc_monitor.models import PriceData


class PriceFetcher:
    """Fetches BTC/USD price data from yfinance and stores it in the database."""
    
    def __init__(
        self,
        max_retries: int = ...,
        initial_backoff: float = ...,
        max_backoff: float = ...,
        db_path: Optional[Union[str, Path]] = ...,
    ) -> None: ...
    
    def _retry_with_backoff(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Optional[Any]: ...
    
    def get_current_price(self) -> Optional[float]: ...
    
    def get_historical_data(
        self,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
    ) -> List[PriceData]: ...
    
    def save_to_database(self, price_data: PriceData) -> bool: ...
    
    def fetch_and_save_current_price(self) -> Optional[float]: ...
    
    def fetch_and_save_historical_data(
        self,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
    ) -> int: ...
