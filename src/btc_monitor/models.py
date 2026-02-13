"""SQLAlchemy database models for BTC Monitor."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""


class PriceData(Base):
    """Model for storing BTC/USD price data (OHLCV format)."""
    
    __tablename__ = "price_data"
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    open_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Relationship to technical indicators
    technical_indicators: Mapped["TechnicalIndicators"] = relationship(
        "TechnicalIndicators", back_populates="price_data", uselist=False
    )
    
    # Index on timestamp for faster queries
    __table_args__ = (
        Index("ix_price_data_timestamp", "timestamp"),
    )


class TechnicalIndicators(Base):
    """Model for storing technical analysis indicators."""
    
    __tablename__ = "technical_indicators"
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_hist: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma_200: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Foreign key to price_data
    price_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        ForeignKey("price_data.timestamp"),
        nullable=False,
    )
    
    # Relationship back to price data
    price_data: Mapped["PriceData"] = relationship(
        "PriceData", back_populates="technical_indicators"
    )
    
    # Indexes on timestamp for faster queries
    __table_args__ = (
        Index("ix_technical_indicators_timestamp", "timestamp"),
        Index("ix_technical_indicators_price_timestamp", "price_timestamp"),
    )


class SentimentData(Base):
    """Model for storing sentiment analysis data from various sources."""
    
    __tablename__ = "sentiment_data"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Index on timestamp for faster queries
    __table_args__ = (
        Index("ix_sentiment_data_timestamp", "timestamp"),
        Index("ix_sentiment_data_source", "source"),
    )


class TrendAnalysis(Base):
    """Model for storing overall trend analysis with confidence scores."""
    
    __tablename__ = "trend_analysis"
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    trend: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "bullish", "bearish", "neutral"
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 1.0
    indicators_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Index on timestamp for faster queries
    __table_args__ = (
        Index("ix_trend_analysis_timestamp", "timestamp"),
    )
