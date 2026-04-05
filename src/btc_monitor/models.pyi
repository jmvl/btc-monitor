"""Type stub file for btc_monitor.models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Float, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing_extensions import TypedDict

# Base class
class Base:
    """Base class for all models."""

class PriceData(Base):
    """Model for storing BTC/USD price data (OHLCV format)."""

    __tablename__: str
    __table_args__: tuple

    timestamp: Mapped[datetime]
    open_price: Mapped[Optional[float]]
    high: Mapped[Optional[float]]
    low: Mapped[Optional[float]]
    close: Mapped[float]
    volume: Mapped[Optional[float]]
    technical_indicators: Mapped["TechnicalIndicators"]

class TechnicalIndicators(Base):
    """Model for storing technical analysis indicators."""

    __tablename__: str
    __table_args__: tuple

    timestamp: Mapped[datetime]
    rsi: Mapped[Optional[float]]
    macd: Mapped[Optional[float]]
    macd_signal: Mapped[Optional[float]]
    macd_hist: Mapped[Optional[float]]
    sma_50: Mapped[Optional[float]]
    sma_200: Mapped[Optional[float]]
    price_timestamp: Mapped[datetime]
    price_data: Mapped["PriceData"]

class SentimentData(Base):
    """Model for storing sentiment analysis data from various sources."""

    __tablename__: str
    __table_args__: tuple

    id: Mapped[int]
    timestamp: Mapped[datetime]
    source: Mapped[str]
    score: Mapped[float]
    content: Mapped[Optional[str]]

class TrendAnalysis(Base):
    """Model for storing overall trend analysis with confidence scores."""

    __tablename__: str
    __table_args__: tuple

    timestamp: Mapped[datetime]
    trend: Mapped[str]
    confidence: Mapped[float]
    indicators_summary: Mapped[Optional[str]]
