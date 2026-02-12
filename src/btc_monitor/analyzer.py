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
    
    def __init__(self, sentiment_window_hours: int = 24, max_data_age_hours: int = 1):
        """
        Initialize trend analyzer.
        
        Args:
            sentiment_window_hours: How many hours of sentiment data to average.
            max_data_age_hours: Maximum age of data before confidence penalty applies.
        """
        self.sentiment_window_hours = sentiment_window_hours
        self.max_data_age_hours = max_data_age_hours
    
    def calculate_confidence(
        self,
        session: Session,
        timestamp: datetime,
        rsi_signal: Optional[str],
        macd_signal: Optional[str],
        ma_signal: Optional[str],
        sentiment_signal: Optional[str],
        tech_indicators: TechnicalIndicators,
        sentiment_data: Optional[Dict[str, float]]
    ) -> float:
        """
        Calculate confidence score for trend analysis.
        
        Confidence is based on:
        - Agreement between indicators (higher when all agree)
        - Data recency (higher when data is fresh)
        - Volatility context (lower during extreme volatility)
        - Sentiment volume (higher when more sentiment data available)
        
        Args:
            session: SQLAlchemy database session.
            timestamp: Current timestamp for analysis.
            rsi_signal: RSI-based signal.
            macd_signal: MACD-based signal.
            ma_signal: Moving average-based signal.
            sentiment_signal: Sentiment-based signal.
            tech_indicators: TechnicalIndicators object.
            sentiment_data: Dictionary with sentiment scores by source.
        
        Returns:
            Confidence score as percentage (0-100).
        """
        # Base confidence from signal agreement (0-100)
        agreement_confidence = self._calculate_agreement_confidence(
            rsi_signal,
            macd_signal,
            ma_signal,
            sentiment_signal
        )
        
        # Data recency factor (0.0-1.0)
        recency_factor = self._calculate_recency_factor(session, timestamp, tech_indicators)
        
        # Volatility penalty factor (0.0-1.0)
        volatility_factor = self._calculate_volatility_factor(session, timestamp)
        
        # Sentiment volume factor (0.0-1.0)
        sentiment_volume_factor = self._calculate_sentiment_volume_factor(
            session,
            timestamp,
            sentiment_data
        )
        
        # Combine all factors
        # Start with agreement confidence, then apply other factors as multipliers
        confidence = agreement_confidence
        
        # Apply recency factor (fresh data = no penalty)
        confidence *= recency_factor
        
        # Apply volatility factor (high volatility = lower confidence)
        confidence *= volatility_factor
        
        # Apply sentiment volume factor (more data = higher confidence)
        # Only apply if we have sentiment data, otherwise this factor is neutral
        if sentiment_signal is not None:
            confidence *= sentiment_volume_factor
        
        # Ensure confidence is in valid range
        confidence = max(0.0, min(100.0, confidence))
        
        return confidence
    
    def _calculate_agreement_confidence(
        self,
        rsi_signal: Optional[str],
        macd_signal: Optional[str],
        ma_signal: Optional[str],
        sentiment_signal: Optional[str]
    ) -> float:
        """
        Calculate confidence based on indicator agreement.
        
        Args:
            rsi_signal: RSI-based signal.
            macd_signal: MACD-based signal.
            ma_signal: Moving average-based signal.
            sentiment_signal: Sentiment-based signal.
        
        Returns:
            Agreement confidence as percentage (0-100).
        """
        # Count available signals
        signals = [
            s for s in [rsi_signal, macd_signal, ma_signal, sentiment_signal]
            if s is not None
        ]
        
        if not signals:
            return 0.0
        
        # Count bullish, bearish, neutral signals
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        neutral_count = signals.count("neutral")
        
        total = len(signals)
        
        # Determine dominant trend
        if bullish_count > bearish_count:
            dominant = "bullish"
            agreement = bullish_count
        elif bearish_count > bullish_count:
            dominant = "bearish"
            agreement = bearish_count
        else:
            # Equal bullish and bearish, check if mostly neutral
            if neutral_count > total / 2:
                dominant = "neutral"
                agreement = neutral_count
            else:
                # Mixed signals with no clear direction
                agreement = max(bullish_count, bearish_count)
        
        # Calculate agreement percentage
        agreement_percentage = (agreement / total) * 100.0
        
        return agreement_percentage
    
    def _calculate_recency_factor(
        self,
        session: Session,
        timestamp: datetime,
        tech_indicators: TechnicalIndicators
    ) -> float:
        """
        Calculate recency factor based on data freshness.
        
        Confidence decreases when data is stale (>1 hour old).
        
        Args:
            session: SQLAlchemy database session.
            timestamp: Current timestamp for analysis.
            tech_indicators: TechnicalIndicators object.
        
        Returns:
            Recency factor (0.0-1.0).
        """
        # Calculate age of technical indicators
        # Handle timezone-aware vs timezone-naive datetimes
        from datetime import timezone as dt_timezone
        tech_timestamp = tech_indicators.timestamp
        if timestamp.tzinfo is not None and tech_timestamp.tzinfo is None:
            # timestamp is aware, tech_timestamp is naive - assume tech_timestamp is UTC
            tech_timestamp = tech_timestamp.replace(tzinfo=dt_timezone.utc)
        elif timestamp.tzinfo is None and tech_timestamp.tzinfo is not None:
            # timestamp is naive, tech_timestamp is aware - convert both to naive
            timestamp = timestamp.replace(tzinfo=dt_timezone.utc)
            tech_timestamp = tech_timestamp.replace(tzinfo=None)
        
        data_age = timestamp - tech_timestamp
        age_hours = data_age.total_seconds() / 3600.0
        
        if age_hours <= self.max_data_age_hours:
            # Data is fresh, no penalty
            return 1.0
        else:
            # Data is stale, apply penalty
            # Penalty increases linearly up to 24 hours
            penalty_hours = age_hours - self.max_data_age_hours
            max_penalty_hours = 24.0 - self.max_data_age_hours
            
            # Calculate penalty factor (1.0 = fresh, 0.5 = very stale)
            penalty = min(penalty_hours / max_penalty_hours, 1.0)
            recency_factor = 1.0 - (penalty * 0.5)  # Max penalty is 50%
            
            return max(0.5, recency_factor)
    
    def _calculate_volatility_factor(
        self,
        session: Session,
        timestamp: datetime
    ) -> float:
        """
        Calculate volatility factor based on price volatility.
        
        Confidence decreases during high volatility.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: Current timestamp for analysis.
        
        Returns:
            Volatility factor (0.0-1.0).
        """
        # Fetch recent price data for volatility calculation
        # Need at least 24 hours of data (assuming hourly data)
        cutoff_time = timestamp - timedelta(hours=24)
        
        prices = session.query(PriceData.price).filter(
            PriceData.timestamp >= cutoff_time,
            PriceData.timestamp <= timestamp
        ).order_by(PriceData.timestamp).all()
        
        if len(prices) < 10:
            # Not enough data for volatility calculation
            return 1.0
        
        # Extract prices
        price_list = [p[0] for p in prices]
        
        # Calculate daily volatility (standard deviation of returns)
        if len(price_list) < 2:
            return 1.0
        
        # Calculate percentage changes
        returns = []
        for i in range(1, len(price_list)):
            if price_list[i-1] > 0:
                ret = (price_list[i] - price_list[i-1]) / price_list[i-1]
                returns.append(ret)
        
        if not returns:
            return 1.0
        
        # Calculate standard deviation of returns
        import statistics
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        # Convert to daily volatility (assuming hourly data)
        daily_volatility = std_dev * (24 ** 0.5)  # sqrt of hours per day
        
        # Define thresholds
        # Normal volatility for BTC: <5% daily is low, 5-10% is normal, >10% is high
        low_volatility_threshold = 0.05
        high_volatility_threshold = 0.10
        
        # Calculate volatility factor
        if daily_volatility <= low_volatility_threshold:
            # Low volatility, no penalty
            return 1.0
        elif daily_volatility <= high_volatility_threshold:
            # Normal volatility, small penalty
            volatility_range = high_volatility_threshold - low_volatility_threshold
            excess = daily_volatility - low_volatility_threshold
            penalty = (excess / volatility_range) * 0.2  # Max 20% penalty
            return 1.0 - penalty
        else:
            # High volatility, significant penalty
            # Cap penalty at 50%
            return 0.5
    
    def _calculate_sentiment_volume_factor(
        self,
        session: Session,
        timestamp: datetime,
        sentiment_data: Optional[Dict[str, float]]
    ) -> float:
        """
        Calculate sentiment volume factor based on amount of sentiment data.
        
        Confidence increases with more sentiment data points.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: Current timestamp for analysis.
            sentiment_data: Dictionary with sentiment scores by source.
        
        Returns:
            Sentiment volume factor (0.0-1.0).
        """
        if not sentiment_data:
            return 1.0
        
        # Count total sentiment data points in the window
        cutoff_time = timestamp - timedelta(hours=self.sentiment_window_hours)
        
        sentiment_count = session.query(SentimentData).filter(
            SentimentData.timestamp >= cutoff_time,
            SentimentData.timestamp <= timestamp
        ).count()
        
        if sentiment_count == 0:
            return 1.0
        
        # Define thresholds
        # <10 data points: low confidence
        # 10-50 data points: medium confidence
        # >50 data points: high confidence
        low_threshold = 10
        high_threshold = 50
        
        # Calculate volume factor
        if sentiment_count <= low_threshold:
            # Low volume, factor scales linearly from 0.5 to 0.8
            factor = 0.5 + (sentiment_count / low_threshold) * 0.3
        elif sentiment_count <= high_threshold:
            # Medium volume, factor scales from 0.8 to 1.0
            volume_range = high_threshold - low_threshold
            excess = sentiment_count - low_threshold
            factor = 0.8 + (excess / volume_range) * 0.2
        else:
            # High volume, maximum factor
            factor = 1.0
        
        # Also factor in number of sources (more sources = better)
        source_count = len(sentiment_data)
        # Up to 4 sources available (twitter, reddit, news, research)
        source_factor = min(source_count / 4.0, 1.0)
        
        # Combine volume and source factors (70% volume, 30% sources)
        combined_factor = factor * 0.7 + source_factor * 0.3
        
        return combined_factor
    
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
        trend, agreement_confidence = self._combine_signals(
            rsi_signal,
            macd_signal,
            ma_signal,
            sentiment_signal
        )
        
        # Calculate confidence score (0-100)
        confidence = self.calculate_confidence(
            session,
            timestamp,
            rsi_signal,
            macd_signal,
            ma_signal,
            sentiment_signal,
            tech_indicators,
            sentiment_data
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
        
        # Save to database (convert confidence from 0-100 to 0-1.0)
        self._save_analysis(
            session,
            timestamp,
            trend,
            confidence / 100.0,
            indicators_summary
        )
        
        return {
            "trend": trend,
            "confidence": confidence / 100.0,  # Convert back to 0-1.0 for backward compatibility
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
