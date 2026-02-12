"""Type stubs for btc_monitor.indicators module."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session


class RSI:
    """Relative Strength Index (RSI) indicator calculator."""
    
    def __init__(self, period: int = 14) -> None: ...
    
    def calculate(self, prices: List[float]) -> Optional[float]: ...
    
    def calculate_and_save(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[float]: ...
    
    def _fetch_prices(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[List[float]]: ...
    
    def _save_indicator(
        self,
        session: Session,
        timestamp: datetime,
        rsi: float
    ) -> None: ...


class MACD:
    """Moving Average Convergence Divergence (MACD) indicator calculator."""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None: ...
    
    def calculate(self, prices: List[float]) -> Optional[tuple]: ...
    
    def calculate_and_save(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[tuple]: ...
    
    def _fetch_prices(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[List[float]]: ...
    
    def _save_indicator(
        self,
        session: Session,
        timestamp: datetime,
        macd_line: float,
        signal_line: float,
        histogram: float
    ) -> None: ...


class MovingAverages:
    """Moving Averages (SMA and EMA) indicator calculator."""
    
    def __init__(self, sma_50_period: int = 50, sma_200_period: int = 200) -> None: ...
    
    def calculate_sma(self, prices: List[float], period: int) -> Optional[float]: ...
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]: ...
    
    def calculate_and_save(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[tuple]: ...
    
    def _fetch_prices(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[List[float]]: ...
    
    def _save_indicator(
        self,
        session: Session,
        timestamp: datetime,
        sma_50: Optional[float],
        sma_200: Optional[float]
    ) -> None: ...
