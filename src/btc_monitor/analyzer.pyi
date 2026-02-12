"""Type stubs for analyzer module."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from btc_monitor.models import (
    PriceData,
    SentimentData,
    TechnicalIndicators,
    TrendAnalysis,
)


class TrendAnalyzer:
    """Analyzes technical and sentiment data to determine market trend."""
    
    def __init__(self, sentiment_window_hours: int = 24) -> None: ...
    
    def analyze(self, session: Session, timestamp: datetime) -> Optional[Dict[str, Any]]: ...
    
    def _fetch_latest_technical_indicators(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[TechnicalIndicators]: ...
    
    def _fetch_latest_price_data(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[PriceData]: ...
    
    def _fetch_recent_sentiment(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[Dict[str, float]]: ...
    
    def _calculate_rsi_signal(self, rsi: Optional[float]) -> Optional[str]: ...
    
    def _calculate_macd_signal(
        self,
        macd: Optional[float],
        macd_signal: Optional[float]
    ) -> Optional[str]: ...
    
    def _calculate_ma_signal(
        self,
        price: Optional[float],
        sma_200: Optional[float]
    ) -> Optional[str]: ...
    
    def _calculate_sentiment_signal(
        self,
        sentiment_data: Optional[Dict[str, float]]
    ) -> Optional[str]: ...
    
    def _combine_signals(
        self,
        rsi_signal: Optional[str],
        macd_signal: Optional[str],
        ma_signal: Optional[str],
        sentiment_signal: Optional[str]
    ) -> tuple[str, float]: ...
    
    def _create_indicators_summary(
        self,
        tech_indicators: TechnicalIndicators,
        sentiment_data: Optional[Dict[str, float]],
        rsi_signal: Optional[str],
        macd_signal: Optional[str],
        ma_signal: Optional[str],
        sentiment_signal: Optional[str]
    ) -> str: ...
    
    def _save_analysis(
        self,
        session: Session,
        timestamp: datetime,
        trend: str,
        confidence: float,
        indicators_summary: str
    ) -> None: ...
