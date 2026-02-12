"""Tests for database schema and initialization."""

import tempfile
from pathlib import Path
from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from btc_monitor.database import init_db, get_engine, get_session
from btc_monitor.models import (
    PriceData,
    TechnicalIndicators,
    SentimentData,
    TrendAnalysis,
    Base,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database file for testing."""
    db_path = tmp_path / "test_btc_monitor.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def db_session(temp_db_path: Path):
    """Create a database session for testing."""
    session = get_session(temp_db_path)
    yield session
    session.close()


class TestDatabaseInitialization:
    """Tests for database initialization."""
    
    def test_init_db_creates_database_file(self, tmp_path: Path) -> None:
        """Test that init_db creates the database file."""
        db_path = tmp_path / "test_init.db"
        assert not db_path.exists()
        
        init_db(db_path)
        
        assert db_path.exists()
        assert db_path.is_file()
    
    def test_all_tables_exist(self, temp_db_path: Path) -> None:
        """Test that all required tables are created."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        expected_tables = {
            "price_data",
            "technical_indicators",
            "sentiment_data",
            "trend_analysis",
        }
        
        assert set(table_names) == expected_tables


class TestPriceDataModel:
    """Tests for the PriceData model."""
    
    def test_price_data_columns(self, temp_db_path: Path) -> None:
        """Test that PriceData has the correct columns."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("price_data")]
        
        expected_columns = {"timestamp", "price", "volume"}
        assert set(columns) == expected_columns
    
    def test_price_data_timestamp_is_primary_key(self, temp_db_path: Path) -> None:
        """Test that timestamp is the primary key of price_data."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        pk_constraint = inspector.get_pk_constraint("price_data")
        
        assert pk_constraint["constrained_columns"] == ["timestamp"]
    
    def test_price_data_has_timestamp_index(self, temp_db_path: Path) -> None:
        """Test that price_data has an index on timestamp."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        indexes = inspector.get_indexes("price_data")
        
        index_names = {idx["name"] for idx in indexes}
        assert "ix_price_data_timestamp" in index_names
    
    def test_insert_and_retrieve_price_data(self, db_session) -> None:
        """Test that we can insert and retrieve price data."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        price = 45000.50
        volume = 1000000.0
        
        price_entry = PriceData(timestamp=timestamp, price=price, volume=volume)
        db_session.add(price_entry)
        db_session.commit()
        
        retrieved = db_session.query(PriceData).filter_by(timestamp=timestamp).first()
        
        assert retrieved is not None
        assert retrieved.price == price
        assert retrieved.volume == volume
        assert retrieved.timestamp == timestamp
    
    def test_price_data_without_volume(self, db_session) -> None:
        """Test that we can insert price data without volume."""
        timestamp = datetime(2024, 1, 2, 12, 0, 0)
        price = 46000.75
        
        price_entry = PriceData(timestamp=timestamp, price=price)
        db_session.add(price_entry)
        db_session.commit()
        
        retrieved = db_session.query(PriceData).filter_by(timestamp=timestamp).first()
        
        assert retrieved is not None
        assert retrieved.price == price
        assert retrieved.volume is None


class TestTechnicalIndicatorsModel:
    """Tests for the TechnicalIndicators model."""
    
    def test_technical_indicators_columns(self, temp_db_path: Path) -> None:
        """Test that TechnicalIndicators has the correct columns."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("technical_indicators")]
        
        expected_columns = {
            "timestamp",
            "rsi",
            "macd",
            "macd_signal",
            "macd_hist",
            "sma_50",
            "sma_200",
            "price_timestamp",
        }
        assert set(columns) == expected_columns
    
    def test_technical_indicators_has_indexes(self, temp_db_path: Path) -> None:
        """Test that technical_indicators has proper indexes."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        indexes = inspector.get_indexes("technical_indicators")
        
        index_names = {idx["name"] for idx in indexes}
        assert "ix_technical_indicators_timestamp" in index_names
        assert "ix_technical_indicators_price_timestamp" in index_names
    
    def test_technical_indicators_foreign_key(self, temp_db_path: Path) -> None:
        """Test that technical_indicators has a foreign key to price_data."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        fk_constraints = inspector.get_foreign_keys("technical_indicators")
        
        assert len(fk_constraints) == 1
        fk = fk_constraints[0]
        assert fk["constrained_columns"] == ["price_timestamp"]
        assert fk["referred_table"] == "price_data"
        assert fk["referred_columns"] == ["timestamp"]
    
    def test_insert_and_retrieve_technical_indicators(self, db_session) -> None:
        """Test that we can insert and retrieve technical indicators."""
        # First create price data
        price_timestamp = datetime(2024, 1, 1, 12, 0, 0)
        price_entry = PriceData(timestamp=price_timestamp, price=45000.0)
        db_session.add(price_entry)
        
        # Create technical indicators
        indicators = TechnicalIndicators(
            timestamp=price_timestamp,
            rsi=65.5,
            macd=150.25,
            macd_signal=145.75,
            macd_hist=4.5,
            sma_50=44000.0,
            sma_200=42000.0,
            price_timestamp=price_timestamp,
        )
        db_session.add(indicators)
        db_session.commit()
        
        # Retrieve
        retrieved = db_session.query(TechnicalIndicators).filter_by(
            timestamp=price_timestamp
        ).first()
        
        assert retrieved is not None
        assert retrieved.rsi == 65.5
        assert retrieved.macd == 150.25
        assert retrieved.macd_signal == 145.75
        assert retrieved.macd_hist == 4.5
        assert retrieved.sma_50 == 44000.0
        assert retrieved.sma_200 == 42000.0


class TestSentimentDataModel:
    """Tests for the SentimentData model."""
    
    def test_sentiment_data_columns(self, temp_db_path: Path) -> None:
        """Test that SentimentData has the correct columns."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("sentiment_data")]
        
        expected_columns = {"id", "timestamp", "source", "score", "content"}
        assert set(columns) == expected_columns
    
    def test_sentiment_data_id_is_primary_key(self, temp_db_path: Path) -> None:
        """Test that id is the primary key of sentiment_data."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        pk_constraint = inspector.get_pk_constraint("sentiment_data")
        
        assert pk_constraint["constrained_columns"] == ["id"]
    
    def test_sentiment_data_has_indexes(self, temp_db_path: Path) -> None:
        """Test that sentiment_data has proper indexes."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        indexes = inspector.get_indexes("sentiment_data")
        
        index_names = {idx["name"] for idx in indexes}
        assert "ix_sentiment_data_timestamp" in index_names
        assert "ix_sentiment_data_source" in index_names
    
    def test_insert_and_retrieve_sentiment_data(self, db_session) -> None:
        """Test that we can insert and retrieve sentiment data."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        source = "twitter"
        score = 0.75
        content = "Bitcoin looks bullish today! 🚀"
        
        sentiment = SentimentData(
            timestamp=timestamp,
            source=source,
            score=score,
            content=content,
        )
        db_session.add(sentiment)
        db_session.commit()
        
        # Retrieve
        retrieved = db_session.query(SentimentData).filter_by(id=1).first()
        
        assert retrieved is not None
        assert retrieved.timestamp == timestamp
        assert retrieved.source == source
        assert retrieved.score == score
        assert retrieved.content == content
    
    def test_sentiment_data_without_content(self, db_session) -> None:
        """Test that we can insert sentiment data without content."""
        timestamp = datetime(2024, 1, 2, 12, 0, 0)
        source = "news"
        score = -0.5
        
        sentiment = SentimentData(timestamp=timestamp, source=source, score=score)
        db_session.add(sentiment)
        db_session.commit()
        
        retrieved = db_session.query(SentimentData).filter_by(timestamp=timestamp).first()
        
        assert retrieved is not None
        assert retrieved.content is None


class TestTrendAnalysisModel:
    """Tests for the TrendAnalysis model."""
    
    def test_trend_analysis_columns(self, temp_db_path: Path) -> None:
        """Test that TrendAnalysis has the correct columns."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("trend_analysis")]
        
        expected_columns = {"timestamp", "trend", "confidence", "indicators_summary"}
        assert set(columns) == expected_columns
    
    def test_trend_analysis_timestamp_is_primary_key(self, temp_db_path: Path) -> None:
        """Test that timestamp is the primary key of trend_analysis."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        pk_constraint = inspector.get_pk_constraint("trend_analysis")
        
        assert pk_constraint["constrained_columns"] == ["timestamp"]
    
    def test_trend_analysis_has_timestamp_index(self, temp_db_path: Path) -> None:
        """Test that trend_analysis has an index on timestamp."""
        engine = get_engine(temp_db_path)
        inspector = inspect(engine)
        indexes = inspector.get_indexes("trend_analysis")
        
        index_names = {idx["name"] for idx in indexes}
        assert "ix_trend_analysis_timestamp" in index_names
    
    def test_insert_and_retrieve_trend_analysis(self, db_session) -> None:
        """Test that we can insert and retrieve trend analysis."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        trend = "bullish"
        confidence = 0.85
        summary = "RSI above 70, MACD showing positive momentum"
        
        analysis = TrendAnalysis(
            timestamp=timestamp,
            trend=trend,
            confidence=confidence,
            indicators_summary=summary,
        )
        db_session.add(analysis)
        db_session.commit()
        
        retrieved = db_session.query(TrendAnalysis).filter_by(timestamp=timestamp).first()
        
        assert retrieved is not None
        assert retrieved.trend == trend
        assert retrieved.confidence == confidence
        assert retrieved.indicators_summary == summary
    
    def test_trend_analysis_without_summary(self, db_session) -> None:
        """Test that we can insert trend analysis without summary."""
        timestamp = datetime(2024, 1, 2, 12, 0, 0)
        trend = "neutral"
        confidence = 0.5
        
        analysis = TrendAnalysis(
            timestamp=timestamp,
            trend=trend,
            confidence=confidence,
        )
        db_session.add(analysis)
        db_session.commit()
        
        retrieved = db_session.query(TrendAnalysis).filter_by(timestamp=timestamp).first()
        
        assert retrieved is not None
        assert retrieved.indicators_summary is None


class TestRelationships:
    """Tests for relationships between models."""
    
    def test_price_data_to_technical_indicators_relationship(self, db_session) -> None:
        """Test the one-to-one relationship between PriceData and TechnicalIndicators."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        
        # Create price data
        price_entry = PriceData(timestamp=timestamp, price=45000.0)
        db_session.add(price_entry)
        
        # Create technical indicators
        indicators = TechnicalIndicators(
            timestamp=timestamp,
            rsi=65.5,
            price_timestamp=timestamp,
        )
        db_session.add(indicators)
        db_session.commit()
        
        # Test relationship from price to indicators
        retrieved_price = db_session.query(PriceData).filter_by(timestamp=timestamp).first()
        assert retrieved_price.technical_indicators is not None
        assert retrieved_price.technical_indicators.rsi == 65.5
        
        # Test relationship from indicators to price
        retrieved_indicators = db_session.query(TechnicalIndicators).filter_by(
            timestamp=timestamp
        ).first()
        assert retrieved_indicators.price_data is not None
        assert retrieved_indicators.price_data.price == 45000.0
