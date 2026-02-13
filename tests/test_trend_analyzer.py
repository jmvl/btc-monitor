"""Tests for trend analyzer."""

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


def test_trend_analyzer_init_default():
    """Test TrendAnalyzer initialization with default parameters."""
    analyzer = TrendAnalyzer()
    assert analyzer.sentiment_window_hours == 24


def test_trend_analyzer_init_custom():
    """Test TrendAnalyzer initialization with custom parameters."""
    analyzer = TrendAnalyzer(sentiment_window_hours=48)
    assert analyzer.sentiment_window_hours == 48


def test_fetch_latest_technical_indicators(temp_db_path, timestamp):
    """Test fetching latest technical indicators."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create test data
    tech1 = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=2),
        rsi=45.0,
        macd=10.0,
        macd_signal=8.0,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=2)
    )
    tech2 = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=1),
        rsi=50.0,
        macd=12.0,
        macd_signal=9.0,
        sma_50=46000.0,
        sma_200=44500.0,
        price_timestamp=timestamp - timedelta(hours=1)
    )
    session.add_all([tech1, tech2])
    session.commit()
    
    # Fetch latest
    result = analyzer._fetch_latest_technical_indicators(session, timestamp)
    
    assert result is not None
    assert result.timestamp == tech2.timestamp
    assert result.rsi == 50.0
    assert result.macd == 12.0


def test_fetch_latest_technical_indicators_none(temp_db_path, timestamp):
    """Test fetching when no technical indicators exist."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    result = analyzer._fetch_latest_technical_indicators(session, timestamp)
    
    assert result is None


def test_fetch_latest_price_data(temp_db_path, timestamp):
    """Test fetching latest price data."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create test data
    price1 = PriceData(
        timestamp=timestamp - timedelta(hours=2),
        price=45000.0,
        volume=1000.0
    )
    price2 = PriceData(
        timestamp=timestamp - timedelta(hours=1),
        price=46000.0,
        volume=1100.0
    )
    session.add_all([price1, price2])
    session.commit()
    
    # Fetch latest
    result = analyzer._fetch_latest_price_data(session, timestamp)
    
    assert result is not None
    assert result.timestamp == price2.timestamp
    assert result.price == 46000.0


def test_fetch_latest_price_data_none(temp_db_path, timestamp):
    """Test fetching when no price data exists."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    result = analyzer._fetch_latest_price_data(session, timestamp)
    
    assert result is None


def test_fetch_recent_sentiment(temp_db_path, timestamp):
    """Test fetching recent sentiment data."""
    analyzer = TrendAnalyzer(sentiment_window_hours=24)
    session = get_session(temp_db_path)
    
    # Create sentiment data within window
    sentiment1 = SentimentData(
        timestamp=timestamp - timedelta(hours=1),
        source="twitter",
        score=0.5,
        content="Bullish sentiment"
    )
    sentiment2 = SentimentData(
        timestamp=timestamp - timedelta(hours=2),
        source="news",
        score=0.3,
        content="Positive news"
    )
    sentiment3 = SentimentData(
        timestamp=timestamp - timedelta(hours=5),
        source="reddit",
        score=-0.2,
        content="Mixed views"
    )
    
    # Create sentiment data outside window
    sentiment4 = SentimentData(
        timestamp=timestamp - timedelta(hours=25),
        source="twitter",
        score=0.8,
        content="Old bullish sentiment"
    )
    
    session.add_all([sentiment1, sentiment2, sentiment3, sentiment4])
    session.commit()
    
    # Fetch recent
    result = analyzer._fetch_recent_sentiment(session, timestamp)
    
    assert result is not None
    assert "twitter" in result
    assert "news" in result
    assert "reddit" in result
    assert abs(result["twitter"] - 0.5) < 0.01
    assert abs(result["news"] - 0.3) < 0.01
    assert abs(result["reddit"] - (-0.2)) < 0.01


def test_fetch_recent_sentiment_none(temp_db_path, timestamp):
    """Test fetching when no sentiment data exists."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    result = analyzer._fetch_recent_sentiment(session, timestamp)
    
    assert result is None


def test_calculate_rsi_signal_bullish():
    """Test RSI signal calculation for oversold condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_rsi_signal(25.0)
    
    assert result == "bullish"


def test_calculate_rsi_signal_bearish():
    """Test RSI signal calculation for overbought condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_rsi_signal(75.0)
    
    assert result == "bearish"


def test_calculate_rsi_signal_neutral():
    """Test RSI signal calculation for neutral condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_rsi_signal(50.0)
    
    assert result == "neutral"


def test_calculate_rsi_signal_boundary():
    """Test RSI signal calculation at boundary values."""
    analyzer = TrendAnalyzer()
    
    assert analyzer._calculate_rsi_signal(30.0) == "neutral"
    assert analyzer._calculate_rsi_signal(29.9) == "bullish"
    assert analyzer._calculate_rsi_signal(70.0) == "neutral"
    assert analyzer._calculate_rsi_signal(70.1) == "bearish"


def test_calculate_rsi_signal_none():
    """Test RSI signal calculation with missing data."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_rsi_signal(None)
    
    assert result is None


def test_calculate_macd_signal_bullish():
    """Test MACD signal calculation for bullish condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_macd_signal(10.0, 8.0)
    
    assert result == "bullish"


def test_calculate_macd_signal_bearish():
    """Test MACD signal calculation for bearish condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_macd_signal(8.0, 10.0)
    
    assert result == "bearish"


def test_calculate_macd_signal_neutral():
    """Test MACD signal calculation for neutral condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_macd_signal(10.0, 10.0)
    
    assert result == "neutral"


def test_calculate_macd_signal_none():
    """Test MACD signal calculation with missing data."""
    analyzer = TrendAnalyzer()
    
    assert analyzer._calculate_macd_signal(None, 10.0) is None
    assert analyzer._calculate_macd_signal(10.0, None) is None
    assert analyzer._calculate_macd_signal(None, None) is None


def test_calculate_ma_signal_bullish():
    """Test MA signal calculation for bullish condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_ma_signal(46000.0, 45000.0)
    
    assert result == "bullish"


def test_calculate_ma_signal_bearish():
    """Test MA signal calculation for bearish condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_ma_signal(44000.0, 45000.0)
    
    assert result == "bearish"


def test_calculate_ma_signal_neutral():
    """Test MA signal calculation for neutral condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_ma_signal(45000.0, 45000.0)
    
    assert result == "neutral"


def test_calculate_ma_signal_none():
    """Test MA signal calculation with missing data."""
    analyzer = TrendAnalyzer()
    
    assert analyzer._calculate_ma_signal(None, 45000.0) is None
    assert analyzer._calculate_ma_signal(46000.0, None) is None
    assert analyzer._calculate_ma_signal(None, None) is None


def test_calculate_sentiment_signal_bullish():
    """Test sentiment signal calculation for bullish condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_sentiment_signal({"twitter": 0.5, "news": 0.3})
    
    assert result == "bullish"


def test_calculate_sentiment_signal_bearish():
    """Test sentiment signal calculation for bearish condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_sentiment_signal({"twitter": -0.5, "news": -0.3})
    
    assert result == "bearish"


def test_calculate_sentiment_signal_neutral():
    """Test sentiment signal calculation for neutral condition."""
    analyzer = TrendAnalyzer()
    
    result = analyzer._calculate_sentiment_signal({"twitter": 0.1, "news": -0.05})
    
    assert result == "neutral"


def test_calculate_sentiment_signal_boundary():
    """Test sentiment signal calculation at boundary values."""
    analyzer = TrendAnalyzer()
    
    assert analyzer._calculate_sentiment_signal({"twitter": 0.2}) == "neutral"
    assert analyzer._calculate_sentiment_signal({"twitter": 0.21}) == "bullish"
    assert analyzer._calculate_sentiment_signal({"twitter": -0.2}) == "neutral"
    assert analyzer._calculate_sentiment_signal({"twitter": -0.21}) == "bearish"


def test_calculate_sentiment_signal_none():
    """Test sentiment signal calculation with no data."""
    analyzer = TrendAnalyzer()
    
    assert analyzer._calculate_sentiment_signal(None) is None
    assert analyzer._calculate_sentiment_signal({}) is None


def test_combine_signals_all_bullish():
    """Test combining all bullish signals."""
    analyzer = TrendAnalyzer()
    
    trend, confidence = analyzer._combine_signals("bullish", "bullish", "bullish", "bullish")
    
    assert trend == "bullish"
    assert confidence == 1.0


def test_combine_signals_all_bearish():
    """Test combining all bearish signals."""
    analyzer = TrendAnalyzer()
    
    trend, confidence = analyzer._combine_signals("bearish", "bearish", "bearish", "bearish")
    
    assert trend == "bearish"
    assert confidence == 1.0


def test_combine_signals_mixed():
    """Test combining mixed signals."""
    analyzer = TrendAnalyzer()
    
    # 2 bullish, 1 bearish, 1 neutral
    trend, confidence = analyzer._combine_signals("bullish", "bullish", "bearish", "neutral")
    
    assert trend == "bullish"
    assert confidence == 0.5


def test_combine_signals_equal_bullish_bearish():
    """Test combining equal bullish and bearish signals."""
    analyzer = TrendAnalyzer()
    
    trend, confidence = analyzer._combine_signals("bullish", "bullish", "bearish", "bearish")
    
    assert trend == "neutral"
    assert confidence == 0.0


def test_combine_signals_with_none():
    """Test combining signals with some None values."""
    analyzer = TrendAnalyzer()
    
    # 2 bullish, 1 None
    trend, confidence = analyzer._combine_signals("bullish", "bullish", None, None)
    
    assert trend == "bullish"
    assert confidence == 1.0


def test_combine_signals_all_none():
    """Test combining when all signals are None."""
    analyzer = TrendAnalyzer()
    
    trend, confidence = analyzer._combine_signals(None, None, None, None)
    
    assert trend == "neutral"
    assert confidence == 0.0


def test_combine_signals_all_neutral():
    """Test combining all neutral signals."""
    analyzer = TrendAnalyzer()
    
    trend, confidence = analyzer._combine_signals("neutral", "neutral", "neutral", "neutral")
    
    assert trend == "neutral"
    assert confidence == 1.0


def test_create_indicators_summary():
    """Test creating indicators summary."""
    analyzer = TrendAnalyzer()
    session = None
    
    # Create mock technical indicators
    tech_indicators = TechnicalIndicators(
        timestamp=datetime.now(timezone.utc),
        rsi=55.0,
        macd=10.5,
        macd_signal=9.2,
        sma_50=45000.0,
        sma_200=44000.0
    )
    
    sentiment_data = {"twitter": 0.5, "news": 0.3}
    
    summary = analyzer._create_indicators_summary(
        tech_indicators,
        sentiment_data,
        "neutral",
        "bullish",
        "bullish",
        "bullish"
    )
    
    assert "RSI: 55.00" in summary
    assert "MACD: 10.50" in summary
    assert "Signal: 9.20" in summary
    assert "SMA(50): 45000.00" in summary
    assert "SMA(200): 44000.00" in summary
    assert "twitter: 0.50" in summary
    assert "news: 0.30" in summary


def test_create_indicators_summary_no_data():
    """Test creating indicators summary with no data."""
    analyzer = TrendAnalyzer()
    
    tech_indicators = TechnicalIndicators(
        timestamp=datetime.now(timezone.utc),
        rsi=None,
        macd=None,
        macd_signal=None,
        sma_50=None,
        sma_200=None
    )
    
    summary = analyzer._create_indicators_summary(
        tech_indicators,
        None,
        None,
        None,
        None,
        None
    )
    
    assert summary == "No indicator data"


def test_save_analysis_new(temp_db_path, timestamp):
    """Test saving new analysis to database."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    analyzer._save_analysis(
        session,
        timestamp,
        "bullish",
        0.75,
        "RSI: 55.00 (neutral); MACD: 10.50, Signal: 9.20 (bullish)"
    )
    
    # Verify saved
    analysis = session.query(TrendAnalysis).filter(
        TrendAnalysis.timestamp == timestamp
    ).first()
    
    assert analysis is not None
    assert analysis.trend == "bullish"
    assert analysis.confidence == 0.75
    assert "RSI: 55.00" in analysis.indicators_summary


def test_save_analysis_update(temp_db_path, timestamp):
    """Test updating existing analysis in database."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create initial analysis
    analyzer._save_analysis(
        session,
        timestamp,
        "bullish",
        0.75,
        "Initial summary"
    )
    
    # Update analysis
    analyzer._save_analysis(
        session,
        timestamp,
        "bearish",
        0.60,
        "Updated summary"
    )
    
    # Verify updated
    analysis = session.query(TrendAnalysis).filter(
        TrendAnalysis.timestamp == timestamp
    ).first()
    
    assert analysis is not None
    assert analysis.trend == "bearish"
    assert analysis.confidence == 0.60
    assert analysis.indicators_summary == "Updated summary"


def test_analyze_complete(temp_db_path, timestamp):
    """Test complete analysis workflow."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create test data
    price = PriceData(
        timestamp=timestamp - timedelta(hours=1),
        price=46000.0,
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
    assert "rsi_signal" in result
    assert "macd_signal" in result
    assert "ma_signal" in result
    assert "sentiment_signal" in result
    assert result["trend"] in ["bullish", "bearish", "neutral"]
    assert 0.0 <= result["confidence"] <= 1.0


def test_analyze_no_technical_indicators(temp_db_path, timestamp):
    """Test analysis when no technical indicators exist."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Only create price data (no indicators)
    price = PriceData(
        timestamp=timestamp - timedelta(hours=1),
        price=46000.0,
        volume=1000.0
    )
    session.add(price)
    session.commit()
    
    # Run analysis
    result = analyzer.analyze(session, timestamp)
    
    assert result is None


def test_analyze_no_price_data(temp_db_path, timestamp):
    """Test analysis when no price data exists."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Only create technical indicators (no price data)
    tech = TechnicalIndicators(
        timestamp=timestamp - timedelta(hours=1),
        rsi=55.0,
        macd=10.5,
        macd_signal=9.2,
        sma_50=45000.0,
        sma_200=44000.0,
        price_timestamp=timestamp - timedelta(hours=1)
    )
    session.add(tech)
    session.commit()
    
    # Run analysis
    result = analyzer.analyze(session, timestamp)
    
    assert result is None


def test_analyze_no_sentiment_data(temp_db_path, timestamp):
    """Test analysis when no sentiment data exists."""
    analyzer = TrendAnalyzer()
    session = get_session(temp_db_path)
    
    # Create price and technical indicators (no sentiment)
    price = PriceData(
        timestamp=timestamp - timedelta(hours=1),
        price=46000.0,
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
    session.add_all([price, tech])
    session.commit()
    
    # Run analysis
    result = analyzer.analyze(session, timestamp)
    
    assert result is not None
    assert result["sentiment_signal"] is None


def test_analyze_with_old_sentiment_data(temp_db_path, timestamp):
    """Test analysis when sentiment data is outside the window."""
    analyzer = TrendAnalyzer(sentiment_window_hours=24)
    session = get_session(temp_db_path)
    
    # Create price and technical indicators
    price = PriceData(
        timestamp=timestamp - timedelta(hours=1),
        price=46000.0,
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
    # Create old sentiment (outside window)
    sentiment = SentimentData(
        timestamp=timestamp - timedelta(hours=25),
        source="twitter",
        score=0.8,
        content="Old bullish sentiment"
    )
    
    session.add_all([price, tech, sentiment])
    session.commit()
    
    # Run analysis
    result = analyzer.analyze(session, timestamp)
    
    assert result is not None
    assert result["sentiment_signal"] is None
