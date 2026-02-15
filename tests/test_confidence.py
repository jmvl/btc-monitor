"""Tests for confidence score calculation."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from btc_monitor.analyzer import TrendAnalyzer
from btc_monitor.database import get_session, init_db
from btc_monitor.models import PriceData, SentimentData, TechnicalIndicators, TrendAnalysis


@pytest.fixture
def temp_db_path():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Initialize the database
    init_db(db_path)
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def timestamp():
    """Create a timestamp for testing."""
    return datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc)


def test_trend_analyzer_init_with_max_age():
    """Test TrendAnalyzer initialization with max_data_age_hours."""
    analyzer = TrendAnalyzer(max_data_age_hours=2)
    assert analyzer.sentiment_window_hours == 24
    assert analyzer.max_data_age_hours == 2


def test_calculate_agreement_confidence_all_bullish():
    """Test agreement confidence with all bullish signals."""
    analyzer = TrendAnalyzer()
    
    confidence = analyzer._calculate_agreement_confidence(
        "bullish", "bullish", "bullish", "bullish"
    )
    
    assert confidence == 100.0


def test_calculate_agreement_confidence_all_bearish():
    """Test agreement confidence with all bearish signals."""
    analyzer = TrendAnalyzer()
    
    confidence = analyzer._calculate_agreement_confidence(
        "bearish", "bearish", "bearish", "bearish"
    )
    
    assert confidence == 100.0


def test_calculate_agreement_confidence_mixed():
    """Test agreement confidence with mixed signals."""
    analyzer = TrendAnalyzer()
    
    # 2 bullish, 1 bearish, 1 neutral
    confidence = analyzer._calculate_agreement_confidence(
        "bullish", "bullish", "bearish", "neutral"
    )
    
    assert confidence == 50.0


def test_calculate_agreement_confidence_equal_bullish_bearish():
    """Test agreement confidence with equal bullish and bearish."""
    analyzer = TrendAnalyzer()
    
    confidence = analyzer._calculate_agreement_confidence(
        "bullish", "bullish", "bearish", "bearish"
    )
    
    assert confidence == 50.0


def test_calculate_agreement_confidence_with_none():
    """Test agreement confidence with some None signals."""
    analyzer = TrendAnalyzer()
    
    # 2 bullish, 2 None
    confidence = analyzer._calculate_agreement_confidence(
        "bullish", "bullish", None, None
    )
    
    assert confidence == 100.0


def test_calculate_agreement_confidence_all_none():
    """Test agreement confidence with all None signals."""
    analyzer = TrendAnalyzer()
    
    confidence = analyzer._calculate_agreement_confidence(
        None, None, None, None
    )
    
    assert confidence == 0.0


def test_calculate_agreement_confidence_all_neutral():
    """Test agreement confidence with all neutral signals."""
    analyzer = TrendAnalyzer()
    
    confidence = analyzer._calculate_agreement_confidence(
        "neutral", "neutral", "neutral", "neutral"
    )
    
    assert confidence == 100.0


def test_calculate_recency_factor_fresh_data(temp_db_path, timestamp):
    """Test recency factor with fresh data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Fresh data (5 minutes old)
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(minutes=5),
        rsi=50.0,
        macd=10.0,
        macd_signal=8.0,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(minutes=5)
    )
    
    factor = analyzer._calculate_recency_factor(session, timestamp, tech_indicators)
    
    assert factor == 1.0


def test_calculate_recency_factor_stale_data(temp_db_path, timestamp):
    """Test recency factor with stale data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Stale data (2 hours old)
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=2),
        rsi=50.0,
        macd=10.0,
        macd_signal=8.0,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=2)
    )
    
    factor = analyzer._calculate_recency_factor(session, timestamp, tech_indicators)
    
    # Factor should be less than 1.0 but at least 0.5
    assert 0.5 <= factor < 1.0


def test_calculate_recency_factor_very_stale_data(temp_db_path, timestamp):
    """Test recency factor with very stale data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Very stale data (24 hours old)
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=24),
        rsi=50.0,
        macd=10.0,
        macd_signal=8.0,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=24)
    )
    
    factor = analyzer._calculate_recency_factor(session, timestamp, tech_indicators)
    
    # Factor should be at minimum (0.5)
    assert factor == 0.5


def test_calculate_volatility_factor_low_volatility(temp_db_path, timestamp):
    """Test volatility factor with low volatility."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create stable price data (low volatility)
    base_price = 45000.0
    for i in range(20):
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=base_price + (i * 10),  # Small gradual increase
            volume=1000.0
        )
        session.add(price)
    session.commit()
    
    factor = analyzer._calculate_volatility_factor(session, timestamp)
    
    # Low volatility = no penalty
    assert factor == 1.0


def test_calculate_volatility_factor_normal_volatility(temp_db_path, timestamp):
    """Test volatility factor with normal volatility."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create price data with moderate volatility
    base_price = 45000.0
    for i in range(20):
        # Add some randomness for moderate volatility
        import random
        random.seed(42)  # For reproducibility
        price_change = random.uniform(-500, 500)
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=base_price + price_change,
            volume=1000.0
        )
        session.add(price)
    session.commit()
    
    factor = analyzer._calculate_volatility_factor(session, timestamp)
    
    # Normal volatility = small penalty (factor between 0.8 and 1.0)
    assert 0.8 <= factor <= 1.0


def test_calculate_volatility_factor_high_volatility(temp_db_path, timestamp):
    """Test volatility factor with high volatility."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create price data with high volatility
    base_price = 45000.0
    for i in range(20):
        # Large price swings for high volatility
        price_change = 2000 if i % 2 == 0 else -2000
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=base_price + price_change,
            volume=1000.0
        )
        session.add(price)
    session.commit()
    
    factor = analyzer._calculate_volatility_factor(session, timestamp)
    
    # High volatility = significant penalty (factor = 0.5)
    assert factor == 0.5


def test_calculate_volatility_factor_insufficient_data(temp_db_path, timestamp):
    """Test volatility factor with insufficient price data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create only 5 price points (less than minimum 10)
    for i in range(5):
        price = PriceData(
            timestamp=timestamp - timedelta(hours=5-i),
            close=45000.0 + i * 100,
            volume=1000.0
        )
        session.add(price)
    session.commit()
    
    factor = analyzer._calculate_volatility_factor(session, timestamp)
    
    # Not enough data = neutral factor
    assert factor == 1.0


def test_calculate_sentiment_volume_factor_no_data(temp_db_path, timestamp):
    """Test sentiment volume factor with no sentiment data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    factor = analyzer._calculate_sentiment_volume_factor(
        session, timestamp, None
    )
    
    # No sentiment data = neutral factor
    assert factor == 1.0


def test_calculate_sentiment_volume_factor_low_volume(temp_db_path, timestamp):
    """Test sentiment volume factor with low sentiment volume."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create 5 sentiment data points (low volume)
    for i in range(5):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(hours=i),
            source="twitter",
            score=0.5,
            content="Test"
        )
        session.add(sentiment)
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    factor = analyzer._calculate_sentiment_volume_factor(
        session, timestamp, sentiment_data
    )
    
    # Low volume = factor between 0.5 and 0.8
    assert 0.5 <= factor < 0.8


def test_calculate_sentiment_volume_factor_medium_volume(temp_db_path, timestamp):
    """Test sentiment volume factor with medium sentiment volume."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create 30 sentiment data points (medium volume)
    for i in range(30):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(hours=i/2),
            source="twitter",
            score=0.5,
            content="Test"
        )
        session.add(sentiment)
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    factor = analyzer._calculate_sentiment_volume_factor(
        session, timestamp, sentiment_data
    )
    
    # Medium volume with 1 source = factor between 0.7 and 1.0
    # (70% from volume ~0.9, 30% from source factor 0.25)
    assert 0.7 <= factor <= 1.0


def test_calculate_sentiment_volume_factor_high_volume(temp_db_path, timestamp):
    """Test sentiment volume factor with high sentiment volume."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create 100 sentiment data points (high volume)
    for i in range(100):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(minutes=i),
            source="twitter",
            score=0.5,
            content="Test"
        )
        session.add(sentiment)
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    factor = analyzer._calculate_sentiment_volume_factor(
        session, timestamp, sentiment_data
    )
    
    # High volume with 1 source = factor ~0.775
    # (70% from volume 1.0, 30% from source factor 0.25)
    assert abs(factor - 0.775) < 0.001


def test_calculate_sentiment_volume_factor_multiple_sources(temp_db_path, timestamp):
    """Test sentiment volume factor with multiple sources."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create sentiment from 4 sources
    for i in range(20):
        for source in ["twitter", "reddit", "news", "research"]:
            sentiment = SentimentData(
                timestamp=timestamp - timedelta(minutes=i),
                source=source,
                score=0.5,
                content="Test"
            )
            session.add(sentiment)
    session.commit()
    
    sentiment_data = {
        "twitter": 0.5,
        "reddit": 0.3,
        "news": 0.4,
        "research": 0.6
    }
    
    factor = analyzer._calculate_sentiment_volume_factor(
        session, timestamp, sentiment_data
    )
    
    # Multiple sources + high volume = maximum factor
    assert factor == 1.0


def test_calculate_confidence_all_bullish_fresh_data_low_volatility(
    temp_db_path, timestamp
):
    """Test confidence calculation with all bullish signals, fresh data, low volatility."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create fresh technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(minutes=5),
        rsi=25.0,  # Oversold = bullish
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(minutes=5)
    )
    
    # Create stable price data
    for i in range(20):
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=45000.0 + i * 10,
            volume=1000.0
        )
        session.add(price)
    
    # Create sentiment data from multiple sources
    for i in range(20):
        for source in ["twitter", "reddit", "news", "research"]:
            sentiment = SentimentData(
                timestamp=timestamp - timedelta(minutes=i),
                source=source,
                score=0.5,
                content="Bullish"
            )
            session.add(sentiment)
    
    session.commit()
    
    sentiment_data = {
        "twitter": 0.5,
        "reddit": 0.5,
        "news": 0.5,
        "research": 0.5
    }
    
    confidence = analyzer.calculate_confidence(
        session,
        timestamp,
        "bullish",
        "bullish",
        "bullish",
        "bullish",
        tech_indicators,
        sentiment_data
    )
    
    # All signals agree + fresh data + low volatility + high volume + 4 sources = high confidence
    assert 90.0 <= confidence <= 100.0


def test_calculate_confidence_mixed_signals(temp_db_path, timestamp):
    """Test confidence calculation with mixed signals."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(minutes=5),
        rsi=50.0,  # Neutral
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(minutes=5)
    )
    
    # Create stable price data
    for i in range(20):
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=45000.0 + i * 10,
            volume=1000.0
        )
        session.add(price)
    
    # Create sentiment data
    for i in range(20):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(minutes=i),
            source="twitter",
            score=0.5,
            content="Bullish"
        )
        session.add(sentiment)
    
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    confidence = analyzer.calculate_confidence(
        session,
        timestamp,
        "neutral",  # Mixed signals
        "bullish",
        "bullish",
        "bullish",
        tech_indicators,
        sentiment_data
    )
    
    # Mixed signals = lower confidence
    assert 40.0 <= confidence < 80.0


def test_calculate_confidence_stale_data(temp_db_path, timestamp):
    """Test confidence calculation with stale data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create stale technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=5),
        rsi=25.0,
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=5)
    )
    
    # Create stable price data
    for i in range(20):
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=45000.0 + i * 10,
            volume=1000.0
        )
        session.add(price)
    
    # Create sentiment data
    for i in range(20):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(minutes=i),
            source="twitter",
            score=0.5,
            content="Bullish"
        )
        session.add(sentiment)
    
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    confidence = analyzer.calculate_confidence(
        session,
        timestamp,
        "bullish",
        "bullish",
        "bullish",
        "bullish",
        tech_indicators,
        sentiment_data
    )
    
    # Stale data = penalty applied
    assert confidence < 100.0


def test_calculate_confidence_high_volatility(temp_db_path, timestamp):
    """Test confidence calculation with high volatility."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(minutes=5),
        rsi=25.0,
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(minutes=5)
    )
    
    # Create high volatility price data
    for i in range(20):
        price_change = 2000 if i % 2 == 0 else -2000
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=45000.0 + price_change,
            volume=1000.0
        )
        session.add(price)
    
    # Create sentiment data
    for i in range(20):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(minutes=i),
            source="twitter",
            score=0.5,
            content="Bullish"
        )
        session.add(sentiment)
    
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    confidence = analyzer.calculate_confidence(
        session,
        timestamp,
        "bullish",
        "bullish",
        "bullish",
        "bullish",
        tech_indicators,
        sentiment_data
    )
    
    # High volatility = significant penalty
    assert confidence <= 50.0


def test_calculate_confidence_low_sentiment_volume(temp_db_path, timestamp):
    """Test confidence calculation with low sentiment volume."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(minutes=5),
        rsi=25.0,
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(minutes=5)
    )
    
    # Create stable price data
    for i in range(20):
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=45000.0 + i * 10,
            volume=1000.0
        )
        session.add(price)
    
    # Create only 5 sentiment data points (low volume)
    for i in range(5):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(minutes=i),
            source="twitter",
            score=0.5,
            content="Bullish"
        )
        session.add(sentiment)
    
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    confidence = analyzer.calculate_confidence(
        session,
        timestamp,
        "bullish",
        "bullish",
        "bullish",
        "bullish",
        tech_indicators,
        sentiment_data
    )
    
    # Low sentiment volume = penalty applied
    assert confidence < 100.0


def test_calculate_confidence_no_sentiment(temp_db_path, timestamp):
    """Test confidence calculation with no sentiment data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(minutes=5),
        rsi=25.0,
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(minutes=5)
    )
    
    # Create stable price data
    for i in range(20):
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=45000.0 + i * 10,
            volume=1000.0
        )
        session.add(price)
    
    session.commit()
    
    confidence = analyzer.calculate_confidence(
        session,
        timestamp,
        "bullish",
        "bullish",
        "bullish",
        None,  # No sentiment signal
        tech_indicators,
        None  # No sentiment data
    )
    
    # No sentiment = sentiment factor is neutral (1.0)
    assert 80.0 <= confidence <= 100.0


def test_calculate_confidence_range(temp_db_path, timestamp):
    """Test that confidence is always in valid range (0-100)."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=timestamp - timedelta(minutes=5),
        rsi=50.0,
        macd=10.0,
        macd_signal=9.0,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(minutes=5)
    )
    
    # Create extreme volatility price data
    for i in range(20):
        price_change = 5000 if i % 2 == 0 else -5000
        price = PriceData(
            timestamp=timestamp - timedelta(hours=20-i),
            close=45000.0 + price_change,
            volume=1000.0
        )
        session.add(price)
    
    # Create very stale data (23 hours old)
    tech_indicators_stale = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=23),
        rsi=50.0,
        macd=10.0,
        macd_signal=9.0,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=23)
    )
    
    # Create very low sentiment volume
    for i in range(2):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(minutes=i),
            source="twitter",
            score=0.5,
            content="Test"
        )
        session.add(sentiment)
    
    session.commit()
    
    sentiment_data = {"twitter": 0.5}
    
    # Worst case scenario
    confidence = analyzer.calculate_confidence(
        session,
        timestamp,
        "neutral",
        "neutral",
        "neutral",
        "neutral",
        tech_indicators_stale,
        sentiment_data
    )
    
    # Even worst case should be >= 0.0
    assert 0.0 <= confidence <= 100.0


def test_analyze_with_confidence(temp_db_path, timestamp):
    """Test complete analysis workflow with confidence calculation."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create test data
    price = PriceData(
        timestamp=timestamp - timedelta(hours=1),
        close=46000.0,
        volume=1000.0
    )
    tech = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=1),
        rsi=55.0,
        macd=10.5,
        macd_signal=9.2,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=1)
    )
    sentiment = SentimentData(
        timestamp=timestamp - timedelta(hours=1),
        source="twitter",
        score=0.5,
        content="Bullish sentiment"
    )
    
    session.add_all([price, tech, sentiment])
    session.commit()
    
    # Run analysis
    result = analyzer.analyze(session, timestamp)
    
    assert result is not None
    assert "trend" in result
    assert "confidence" in result
    assert result["trend"] in ["bullish", "bearish", "neutral"]
    # Confidence in database is stored as 0-1.0
    assert 0.0 <= result["confidence"] <= 1.0


def test_confidence_saved_to_database(temp_db_path, timestamp):
    """Test that confidence is properly saved to database."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create test data
    price = PriceData(
        timestamp=timestamp - timedelta(hours=1),
        close=46000.0,
        volume=1000.0
    )
    tech = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=1),
        rsi=25.0,  # Oversold = bullish
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=1)
    )
    for i in range(20):
        sentiment = SentimentData(
            timestamp=timestamp - timedelta(minutes=i),
            source="twitter",
            score=0.5,
            content="Bullish"
        )
        session.add(sentiment)
    session.add_all([price, tech])
    session.commit()
    
    # Run analysis
    result = analyzer.analyze(session, timestamp)
    
    # Verify saved to database
    analysis = session.query(TrendAnalysis).filter(
        TrendAnalysis.timestamp == timestamp
    ).first()
    
    assert analysis is not None
    assert analysis.confidence is not None
    # Confidence in database is stored as 0-1.0
    assert 0.0 <= analysis.confidence <= 1.0
