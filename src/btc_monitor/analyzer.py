"""Trend analysis engine for BTC Monitor."""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from btc_monitor.models import (
    PriceData,
    SentimentData,
    TechnicalIndicators,
    TrendAnalysis,
)


class TrendAnalyzer:
    """Analyzes technical and sentiment data to determine market trend."""
    
    def __init__(self, sentiment_window_hours: int = 24):
        """
        Initialize trend analyzer.
        
        Args:
            sentiment_window_hours: How many hours of sentiment data to average.
        """
        self.sentiment_window_hours = sentiment_window_hours
    
    def analyze(self, session: Session, timestamp: datetime) -> Optional[Dict[str, any]]:
        """
        Analyze trend at a given timestamp.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp to analyze.
        
        Returns:
            Dictionary with trend, confidence, and signals, or None if insufficient data.
        """
        # Fetch latest technical indicators
        tech_indicators = self._fetch_latest_technical_indicators(session, timestamp)
        if tech_indicators is None:
            return None
        
        # Fetch latest price data
        price_data = self._fetch_latest_price_data(session, timestamp)
        if price_data is None:
            return None
        
        # Fetch recent sentiment data
        sentiment_data = self._fetch_recent_sentiment(session, timestamp)
        
        # Calculate individual signals
        rsi_signal = self._calculate_rsi_signal(tech_indicators.rsi)
        macd_signal = self._calculate_macd_signal(tech_indicators.macd, tech_indicators.macd_signal)
        ma_signal = self._calculate_ma_signal(price_data.price, tech_indicators.sma_200)
        sentiment_signal = self._calculate_sentiment_signal(sentiment_data)
        
        # Combine signals into overall trend
        trend, confidence = self._combine_signals(
            rsi_signal,
            macd_signal,
            ma_signal,
            sentiment_signal
        )
        
        # Create indicators summary
        indicators_summary = self._create_indicators_summary(
            tech_indicators,
            sentiment_data,
            rsi_signal,
            macd_signal,
            ma_signal,
            sentiment_signal
        )
        
        # Save to database
        self._save_analysis(
            session,
            timestamp,
            trend,
            confidence,
            indicators_summary
        )
        
        return {
            "trend": trend,
            "confidence": confidence,
            "rsi_signal": rsi_signal,
            "macd_signal": macd_signal,
            "ma_signal": ma_signal,
            "sentiment_signal": sentiment_signal,
            "indicators_summary": indicators_summary
        }
    
    def _fetch_latest_technical_indicators(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[TechnicalIndicators]:
        """
        Fetch latest technical indicators before or at timestamp.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp to fetch data for.
        
        Returns:
            TechnicalIndicators object or None if not found.
        """
        indicator = session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp <= timestamp
        ).order_by(desc(TechnicalIndicators.timestamp)).first()
        
        return indicator
    
    def _fetch_latest_price_data(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[PriceData]:
        """
        Fetch latest price data before or at timestamp.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp to fetch data for.
        
        Returns:
            PriceData object or None if not found.
        """
        price = session.query(PriceData).filter(
            PriceData.timestamp <= timestamp
        ).order_by(desc(PriceData.timestamp)).first()
        
        return price
    
    def _fetch_recent_sentiment(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[Dict[str, float]]:
        """
        Fetch recent sentiment data.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp to fetch data for.
        
        Returns:
            Dictionary with average sentiment score by source, or None if no data.
        """
        cutoff_time = timestamp - timedelta(hours=self.sentiment_window_hours)
        
        # Query sentiment data within window
        sentiments = session.query(
            SentimentData.source,
            func.avg(SentimentData.score).label("avg_score")
        ).filter(
            SentimentData.timestamp >= cutoff_time,
            SentimentData.timestamp <= timestamp
        ).group_by(SentimentData.source).all()
        
        if not sentiments:
            return None
        
        # Create dictionary of average scores by source
        sentiment_dict = {}
        for source, avg_score in sentiments:
            sentiment_dict[source] = float(avg_score)
        
        return sentiment_dict
    
    def _calculate_rsi_signal(self, rsi: Optional[float]) -> Optional[str]:
        """
        Calculate RSI-based signal.
        
        Args:
            rsi: RSI value.
        
        Returns:
            'bullish', 'bearish', or 'neutral', or None if RSI is missing.
        """
        if rsi is None:
            return None
        
        if rsi < 30:
            return "bullish"
        elif rsi > 70:
            return "bearish"
        else:
            return "neutral"
    
    def _calculate_macd_signal(
        self,
        macd: Optional[float],
        macd_signal: Optional[float]
    ) -> Optional[str]:
        """
        Calculate MACD-based signal.
        
        Args:
            macd: MACD line value.
            macd_signal: MACD signal line value.
        
        Returns:
            'bullish', 'bearish', or 'neutral', or None if data is missing.
        """
        if macd is None or macd_signal is None:
            return None
        
        if macd > macd_signal:
            return "bullish"
        elif macd < macd_signal:
            return "bearish"
        else:
            return "neutral"
    
    def _calculate_ma_signal(
        self,
        price: Optional[float],
        sma_200: Optional[float]
    ) -> Optional[str]:
        """
        Calculate moving average-based signal.
        
        Args:
            price: Current price.
            sma_200: 200-day SMA value.
        
        Returns:
            'bullish', 'bearish', or 'neutral', or None if data is missing.
        """
        if price is None or sma_200 is None:
            return None
        
        if price > sma_200:
            return "bullish"
        elif price < sma_200:
            return "bearish"
        else:
            return "neutral"
    
    def _calculate_sentiment_signal(
        self,
        sentiment_data: Optional[Dict[str, float]]
    ) -> Optional[str]:
        """
        Calculate sentiment-based signal.
        
        Args:
            sentiment_data: Dictionary with average sentiment scores by source.
        
        Returns:
            'bullish', 'bearish', or 'neutral', or None if no sentiment data.
        """
        if not sentiment_data:
            return None
        
        # Calculate weighted average sentiment
        scores = list(sentiment_data.values())
        avg_sentiment = sum(scores) / len(scores)
        
        if avg_sentiment > 0.2:
            return "bullish"
        elif avg_sentiment < -0.2:
            return "bearish"
        else:
            return "neutral"
    
    def _combine_signals(
        self,
        rsi_signal: Optional[str],
        macd_signal: Optional[str],
        ma_signal: Optional[str],
        sentiment_signal: Optional[str]
    ) -> Tuple[str, float]:
        """
        Combine individual signals into overall trend.
        
        Args:
            rsi_signal: RSI-based signal.
            macd_signal: MACD-based signal.
            ma_signal: Moving average-based signal.
            sentiment_signal: Sentiment-based signal.
        
        Returns:
            Tuple of (trend, confidence) where trend is 'bullish', 'bearish', or 'neutral'.
        """
        # Count available signals
        signals = [
            s for s in [rsi_signal, macd_signal, ma_signal, sentiment_signal]
            if s is not None
        ]
        
        if not signals:
            # No signals available
            return "neutral", 0.0
        
        # Count bullish, bearish, neutral signals
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        neutral_count = signals.count("neutral")
        
        total = len(signals)
        
        # Determine trend
        if bullish_count > bearish_count:
            trend = "bullish"
        elif bearish_count > bullish_count:
            trend = "bearish"
        else:
            # Equal bullish and bearish, or all neutral
            trend = "neutral"
        
        # Calculate confidence based on agreement
        if trend == "neutral":
            # Confidence based on how many agree it's neutral
            confidence = neutral_count / total
        else:
            # Confidence based on how many agree with the trend
            if trend == "bullish":
                agreement = bullish_count
            else:  # bearish
                agreement = bearish_count
            confidence = agreement / total
        
        return trend, confidence
    
    def _create_indicators_summary(
        self,
        tech_indicators: TechnicalIndicators,
        sentiment_data: Optional[Dict[str, float]],
        rsi_signal: Optional[str],
        macd_signal: Optional[str],
        ma_signal: Optional[str],
        sentiment_signal: Optional[str]
    ) -> str:
        """
        Create a human-readable summary of indicators.
        
        Args:
            tech_indicators: TechnicalIndicators object.
            sentiment_data: Dictionary with sentiment scores by source.
            rsi_signal: RSI-based signal.
            macd_signal: MACD-based signal.
            ma_signal: Moving average-based signal.
            sentiment_signal: Sentiment-based signal.
        
        Returns:
            String summary of indicators.
        """
        parts = []
        
        # RSI
        if tech_indicators.rsi is not None:
            parts.append(f"RSI: {tech_indicators.rsi:.2f} ({rsi_signal})")
        
        # MACD
        if tech_indicators.macd is not None and tech_indicators.macd_signal is not None:
            parts.append(f"MACD: {tech_indicators.macd:.2f}, Signal: {tech_indicators.macd_signal:.2f} ({macd_signal})")
        
        # Moving averages
        if tech_indicators.sma_50 is not None:
            parts.append(f"SMA(50): {tech_indicators.sma_50:.2f}")
        if tech_indicators.sma_200 is not None:
            parts.append(f"SMA(200): {tech_indicators.sma_200:.2f}")
        
        # Sentiment
        if sentiment_data:
            sentiment_parts = []
            for source, score in sentiment_data.items():
                sentiment_parts.append(f"{source}: {score:.2f}")
            parts.append(f"Sentiment: {', '.join(sentiment_parts)} ({sentiment_signal})")
        
        return "; ".join(parts) if parts else "No indicator data"
    
    def _save_analysis(
        self,
        session: Session,
        timestamp: datetime,
        trend: str,
        confidence: float,
        indicators_summary: str
    ) -> None:
        """
        Save trend analysis to database.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp of the analysis.
            trend: Overall trend ('bullish', 'bearish', or 'neutral').
            confidence: Confidence score (0.0 to 1.0).
            indicators_summary: Human-readable summary of indicators.
        """
        # Check if analysis already exists
        existing = session.query(TrendAnalysis).filter(
            TrendAnalysis.timestamp == timestamp
        ).first()
        
        if existing:
            # Update existing record
            existing.trend = trend
            existing.confidence = confidence
            existing.indicators_summary = indicators_summary
        else:
            # Create new record
            analysis = TrendAnalysis(
                timestamp=timestamp,
                trend=trend,
                confidence=confidence,
                indicators_summary=indicators_summary
            )
            session.add(analysis)
        
        session.commit()
