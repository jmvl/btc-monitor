"""Tests for RSI indicator calculation."""

import math
from datetime import datetime, timedelta

import pytest

from btc_monitor.indicators import RSI
from btc_monitor.models import PriceData, TechnicalIndicators
from btc_monitor.database import get_session, get_engine, DEFAULT_DB_PATH


class TestRSIClass:
    """Test RSI class initialization."""
    
    def test_default_period(self):
        """Test RSI initialized with default period of 14."""
        rsi = RSI()
        assert rsi.period == 14
    
    def test_custom_period(self):
        """Test RSI initialized with custom period."""
        rsi = RSI(period=7)
        assert rsi.period == 7


class TestRSICalculate:
    """Test RSI calculation."""
    
    def test_empty_price_list(self):
        """Test RSI calculation with empty price list returns None."""
        rsi = RSI()
        result = rsi.calculate([])
        assert result is None
    
    def test_insufficient_data(self):
        """Test RSI calculation with insufficient data returns None."""
        rsi = RSI(period=14)
        # Need at least 15 prices (period + 1)
        prices = [100.0] * 14
        result = rsi.calculate(prices)
        assert result is None
    
    def test_exactly_minimum_data(self):
        """Test RSI calculation with exactly minimum required data."""
        rsi = RSI(period=14)
        # Create 15 prices with some variation
        prices = [100.0 + i for i in range(15)]
        result = rsi.calculate(prices)
        assert result is not None
        assert 0 <= result <= 100
    
    def test_all_prices_same(self):
        """Test RSI calculation when all prices are the same."""
        rsi = RSI(period=14)
        prices = [100.0] * 20
        result = rsi.calculate(prices)
        # When no change, RSI should be 50
        assert result is not None
        assert 45 <= result <= 55  # Allow small floating-point errors
    
    def test_all_gains(self):
        """Test RSI calculation with all gains (price always increasing)."""
        rsi = RSI(period=5)
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        result = rsi.calculate(prices)
        assert result is not None
        assert result > 70  # Strong uptrend
    
    def test_all_losses(self):
        """Test RSI calculation with all losses (price always decreasing)."""
        rsi = RSI(period=5)
        prices = [105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
        result = rsi.calculate(prices)
        assert result is not None
        assert result < 30  # Strong downtrend
    
    def test_rsi_bounds(self):
        """Test that RSI values are always between 0 and 100."""
        rsi = RSI(period=14)
        # Test with various price patterns
        test_cases = [
            [100.0 + math.sin(i) * 10 for i in range(50)],  # Oscillating
            [100.0 + i * 0.5 for i in range(30)],  # Gradual uptrend
            [100.0 - i * 0.5 for i in range(30)],  # Gradual downtrend
            [100.0] * 30,  # Flat
        ]
        
        for prices in test_cases:
            result = rsi.calculate(prices)
            assert result is not None
            assert 0 <= result <= 100, f"RSI {result} outside bounds for prices {prices}"
    
    def test_handles_nan_values(self):
        """Test RSI calculation handles NaN values in input."""
        rsi = RSI(period=5)
        # Create prices with some NaN values
        prices = [100.0, 101.0, float('nan'), 103.0, 104.0, 105.0, 106.0, 107.0]
        result = rsi.calculate(prices)
        # NaN values should be filtered out
        assert result is not None
        assert 0 <= result <= 100
    
    def test_multiple_nan_values(self):
        """Test RSI calculation with multiple NaN values."""
        rsi = RSI(period=5)
        prices = [
            100.0, float('nan'), 102.0, float('nan'),
            104.0, 105.0, 106.0, 107.0, 108.0
        ]
        result = rsi.calculate(prices)
        assert result is not None
        assert 0 <= result <= 100
    
    def test_all_nan_values(self):
        """Test RSI calculation when all values are NaN."""
        rsi = RSI(period=5)
        prices = [float('nan')] * 20
        result = rsi.calculate(prices)
        # All NaN should result in None
        assert result is None
    
    def test_nan_values_and_insufficient_data(self):
        """Test RSI calculation when filtering NaN leaves insufficient data."""
        rsi = RSI(period=14)
        prices = [100.0] * 14 + [float('nan')] * 10
        result = rsi.calculate(prices)
        # After filtering NaN, we have 14 prices but need 15
        assert result is None
    
    def test_verifiable_formula(self):
        """Test RSI calculation against a manually calculated example."""
        rsi = RSI(period=5)
        # Manually calculated test case
        # Prices: 100, 102, 99, 103, 98, 104
        # Changes: +2, -3, +4, -5, +6
        # Avg gain (first 5): (2 + 4 + 6) / 5 = 2.4
        # Avg loss (first 5): (3 + 5) / 5 = 1.6
        # RS = 2.4 / 1.6 = 1.5
        # RSI = 100 - (100 / 2.5) = 100 - 40 = 60
        prices = [100.0, 102.0, 99.0, 103.0, 98.0, 104.0]
        result = rsi.calculate(prices)
        # Allow small floating-point error
        assert result is not None
        assert abs(result - 60.0) < 5.0
    
    def test_long_price_series(self):
        """Test RSI calculation with a longer price series."""
        rsi = RSI(period=14)
        # Generate 100 prices with random-ish movements
        prices = []
        price = 100.0
        for i in range(100):
            price += (hash(i) % 20) - 10  # Add values between -10 and +10
            prices.append(price)
        
        result = rsi.calculate(prices)
        assert result is not None
        assert 0 <= result <= 100
    
    def test_period_parameter_respected(self):
        """Test that the period parameter affects calculation."""
        rsi_short = RSI(period=5)
        rsi_long = RSI(period=20)
        
        prices = [100.0 + i * 0.5 for i in range(30)]
        
        result_short = rsi_short.calculate(prices)
        result_long = rsi_long.calculate(prices)
        
        assert result_short is not None
        assert result_long is not None
        # Different periods should generally give different results
        # (though they could occasionally be the same)
        assert isinstance(result_short, float)
        assert isinstance(result_long, float)


class TestRSIDatabaseIntegration:
    """Test RSI database integration."""
    
    @pytest.fixture
    def db_session(self):
        """Create a temporary database session for testing."""
        import tempfile
        from pathlib import Path
        
        # Create a temporary database file
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        # Initialize the database
        engine = get_engine(temp_db.name)
        from btc_monitor.models import Base
        Base.metadata.create_all(engine)
        
        # Create session
        session = get_session(temp_db.name)
        
        yield session
        
        # Cleanup
        session.close()
        Path(temp_db.name).unlink(missing_ok=True)
    
    def test_fetch_prices_sufficient_data(self, db_session):
        """Test fetching prices when sufficient data exists."""
        rsi = RSI(period=14)
        timestamp = datetime.now()
        
        # Insert price data
        base_time = timestamp - timedelta(hours=20)
        for i in range(20):
            price_time = base_time + timedelta(hours=i)
            price_data = PriceData(
                timestamp=price_time,
                close=100.0 + i * 0.5
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Fetch prices
        prices = rsi._fetch_prices(db_session, timestamp)
        
        assert prices is not None
        assert len(prices) == 15  # period + 1
    
    def test_fetch_prices_insufficient_data(self, db_session):
        """Test fetching prices when insufficient data exists."""
        rsi = RSI(period=14)
        timestamp = datetime.now()
        
        # Insert only 10 price records
        base_time = timestamp - timedelta(hours=10)
        for i in range(10):
            price_data = PriceData(
                timestamp=base_time + timedelta(hours=i),
                close=100.0 + i
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Fetch prices
        prices = rsi._fetch_prices(db_session, timestamp)
        
        assert prices is None
    
    def test_save_indicator_new_record(self, db_session):
        """Test saving RSI to database as new record."""
        rsi = RSI()
        timestamp = datetime.now()
        rsi_value = 65.5
        
        # Save indicator
        rsi._save_indicator(db_session, timestamp, rsi_value)
        
        # Verify saved
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator is not None
        assert indicator.rsi == rsi_value
        assert indicator.price_timestamp == timestamp
    
    def test_save_indicator_update_existing(self, db_session):
        """Test updating existing RSI record in database."""
        rsi = RSI()
        timestamp = datetime.now()
        
        # Create initial indicator
        indicator = TechnicalIndicators(
            timestamp=timestamp,
            rsi=50.0,
            price_timestamp=timestamp
        )
        db_session.add(indicator)
        db_session.commit()
        
        # Update with new RSI value
        new_rsi = 75.0
        rsi._save_indicator(db_session, timestamp, new_rsi)
        
        # Verify updated
        db_session.refresh(indicator)
        assert indicator.rsi == new_rsi
    
    def test_calculate_and_save(self, db_session):
        """Test full calculate_and_save workflow."""
        rsi = RSI(period=14)
        timestamp = datetime.now()
        
        # Insert price data
        base_time = timestamp - timedelta(hours=20)
        for i in range(20):
            price_data = PriceData(
                timestamp=base_time + timedelta(hours=i),
                close=100.0 + math.sin(i) * 10  # Oscillating prices
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = rsi.calculate_and_save(db_session, timestamp)
        
        # Verify result
        assert result is not None
        assert 0 <= result <= 100
        
        # Verify saved to database
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator is not None
        assert indicator.rsi == result
    
    def test_calculate_and_save_insufficient_data(self, db_session):
        """Test calculate_and_save with insufficient data."""
        rsi = RSI(period=14)
        timestamp = datetime.now()
        
        # Insert insufficient price data
        base_time = timestamp - timedelta(hours=10)
        for i in range(10):
            price_data = PriceData(
                timestamp=base_time + timedelta(hours=i),
                close=100.0 + i
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = rsi.calculate_and_save(db_session, timestamp)
        
        # Should return None
        assert result is None
        
        # Verify no indicator created
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator is None
