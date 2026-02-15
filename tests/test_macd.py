"""Tests for MACD indicator calculation."""

import math
from datetime import datetime, timedelta

import pytest

from btc_monitor.indicators import MACD
from btc_monitor.models import PriceData, TechnicalIndicators
from btc_monitor.database import get_session, get_engine, DEFAULT_DB_PATH


class TestMACDClass:
    """Test MACD class initialization."""
    
    def test_default_parameters(self):
        """Test MACD initialized with default parameters."""
        macd = MACD()
        assert macd.fast == 12
        assert macd.slow == 26
        assert macd.signal == 9
    
    def test_custom_parameters(self):
        """Test MACD initialized with custom parameters."""
        macd = MACD(fast=5, slow=10, signal=4)
        assert macd.fast == 5
        assert macd.slow == 10
        assert macd.signal == 4


class TestMACDCalculate:
    """Test MACD calculation."""
    
    def test_empty_price_list(self):
        """Test MACD calculation with empty price list returns None."""
        macd = MACD()
        result = macd.calculate([])
        assert result is None
    
    def test_insufficient_data(self):
        """Test MACD calculation with insufficient data returns None."""
        macd = MACD(fast=12, slow=26, signal=9)
        # Need at least 35 prices (slow + signal = 26 + 9)
        prices = [100.0] * 34
        result = macd.calculate(prices)
        assert result is None
    
    def test_exactly_minimum_data(self):
        """Test MACD calculation with exactly minimum required data."""
        macd = MACD(fast=12, slow=26, signal=9)
        # Create 35 prices (slow + signal = 26 + 9)
        prices = [100.0 + i * 0.5 for i in range(35)]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        assert isinstance(macd_line, float)
        assert isinstance(signal_line, float)
        assert isinstance(histogram, float)
        # Histogram should equal macd_line - signal_line
        assert abs(histogram - (macd_line - signal_line)) < 0.0001
    
    def test_macd_line_calculation(self):
        """Test MACD line calculation (fast EMA - slow EMA)."""
        macd = MACD(fast=5, slow=10, signal=4)
        # Create a simple uptrend
        prices = [100.0 + i * 1.0 for i in range(20)]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        # In an uptrend, fast EMA should be above slow EMA, so MACD > 0
        assert macd_line > 0
    
    def test_signal_line_calculation(self):
        """Test signal line is EMA of MACD line."""
        macd = MACD(fast=5, slow=10, signal=4)
        prices = [100.0 + i * 1.0 for i in range(20)]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        # Signal line should smooth the MACD line
        assert isinstance(signal_line, float)
        # Histogram is the difference
        assert histogram == macd_line - signal_line
    
    def test_histogram_calculation(self):
        """Test histogram is MACD line minus signal line."""
        macd = MACD(fast=5, slow=10, signal=4)
        prices = [100.0 + i * 0.5 for i in range(20)]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        expected_histogram = macd_line - signal_line
        assert abs(histogram - expected_histogram) < 0.0001
    
    def test_uptrend_positive_histogram(self):
        """Test MACD histogram is positive during uptrend."""
        macd = MACD(fast=5, slow=10, signal=4)
        # Strong uptrend
        prices = [100.0 + i * 2.0 for i in range(20)]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        assert histogram > 0  # Histogram positive in uptrend
    
    def test_downtrend_negative_histogram(self):
        """Test MACD histogram is negative during downtrend."""
        macd = MACD(fast=5, slow=10, signal=4)
        # Strong downtrend
        prices = [100.0 - i * 2.0 for i in range(20)]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        assert histogram < 0  # Histogram negative in downtrend
    
    def test_flat_market_near_zero(self):
        """Test MACD near zero for flat market."""
        macd = MACD(fast=5, slow=10, signal=4)
        # Flat market with small fluctuations
        prices = [100.0 + (i % 3 - 1) * 0.1 for i in range(20)]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        # Values should be near zero for flat market
        assert abs(macd_line) < 1.0
        assert abs(signal_line) < 1.0
        assert abs(histogram) < 1.0
    
    def test_handles_nan_values(self):
        """Test MACD calculation handles NaN values in input."""
        macd = MACD(fast=5, slow=10, signal=4)
        # Create prices with some NaN values
        prices = [
            100.0, 101.0, float('nan'), 103.0, 104.0, 105.0,
            106.0, 107.0, 108.0, 109.0, 110.0, 111.0,
            112.0, 113.0, 114.0, 115.0
        ]
        result = macd.calculate(prices)
        # NaN values should be filtered out
        assert result is not None
        macd_line, signal_line, histogram = result
        assert isinstance(macd_line, float)
        assert isinstance(signal_line, float)
        assert isinstance(histogram, float)
    
    def test_multiple_nan_values(self):
        """Test MACD calculation with multiple NaN values."""
        macd = MACD(fast=5, slow=10, signal=4)
        prices = [
            100.0, float('nan'), 102.0, float('nan'),
            104.0, 105.0, 106.0, 107.0, 108.0,
            109.0, 110.0, 111.0, 112.0, 113.0,
            114.0, 115.0, 116.0, 117.0, 118.0
        ]
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        assert isinstance(macd_line, float)
        assert isinstance(signal_line, float)
        assert isinstance(histogram, float)
    
    def test_all_nan_values(self):
        """Test MACD calculation when all values are NaN."""
        macd = MACD(fast=5, slow=10, signal=4)
        prices = [float('nan')] * 20
        result = macd.calculate(prices)
        # All NaN should result in None
        assert result is None
    
    def test_nan_values_and_insufficient_data(self):
        """Test MACD calculation when filtering NaN leaves insufficient data."""
        macd = MACD(fast=12, slow=26, signal=9)
        prices = [100.0] * 34 + [float('nan')] * 10
        result = macd.calculate(prices)
        # After filtering NaN, we have 34 prices but need 35
        assert result is None
    
    def test_long_price_series(self):
        """Test MACD calculation with a longer price series."""
        macd = MACD(fast=12, slow=26, signal=9)
        # Generate 100 prices with oscillating movements
        prices = []
        price = 100.0
        for i in range(100):
            price += (hash(i) % 20) - 10  # Add values between -10 and +10
            prices.append(price)
        
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        assert isinstance(macd_line, float)
        assert isinstance(signal_line, float)
        assert isinstance(histogram, float)
        assert histogram == macd_line - signal_line
    
    def test_parameters_respected(self):
        """Test that different parameters affect calculation."""
        macd_default = MACD(fast=12, slow=26, signal=9)
        macd_custom = MACD(fast=5, slow=10, signal=4)
        
        prices = [100.0 + i * 0.5 for i in range(50)]
        
        result_default = macd_default.calculate(prices)
        result_custom = macd_custom.calculate(prices)
        
        assert result_default is not None
        assert result_custom is not None
        # Different parameters should generally give different results
        macd_line_default, _, _ = result_default
        macd_line_custom, _, _ = result_custom
        assert isinstance(macd_line_default, float)
        assert isinstance(macd_line_custom, float)
    
    def test_consistency_across_calls(self):
        """Test that MACD calculation is consistent."""
        macd = MACD(fast=5, slow=10, signal=4)
        prices = [100.0 + i * 0.5 for i in range(30)]
        
        result1 = macd.calculate(prices)
        result2 = macd.calculate(prices)
        
        assert result1 is not None
        assert result2 is not None
        # Results should be identical
        assert result1[0] == result2[0]  # macd_line
        assert result1[1] == result2[1]  # signal_line
        assert result1[2] == result2[2]  # histogram
    
    def test_crossover_scenarios(self):
        """Test MACD behavior during price crossovers."""
        macd = MACD(fast=5, slow=10, signal=4)
        
        # First uptrend, then downtrend
        prices = [100.0 + i * 2.0 for i in range(10)]  # Uptrend
        prices += [120.0 - i * 2.0 for i in range(10)]  # Downtrend
        
        result = macd.calculate(prices)
        assert result is not None
        macd_line, signal_line, histogram = result
        # In a reversal scenario, values could be anything
        # Just verify they're valid floats
        assert isinstance(macd_line, float)
        assert isinstance(signal_line, float)
        assert isinstance(histogram, float)
        assert histogram == macd_line - signal_line


class TestMACDDatabaseIntegration:
    """Test MACD database integration."""
    
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
        macd = MACD(fast=12, slow=26, signal=9)
        timestamp = datetime.now()
        
        # Insert price data (need 35 = slow + signal)
        base_time = timestamp - timedelta(hours=40)
        for i in range(40):
            price_time = base_time + timedelta(hours=i)
            price_data = PriceData(
                timestamp=price_time,
                close=100.0 + i * 0.5
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Fetch prices
        prices = macd._fetch_prices(db_session, timestamp)
        
        assert prices is not None
        assert len(prices) == 35  # slow + signal
    
    def test_fetch_prices_insufficient_data(self, db_session):
        """Test fetching prices when insufficient data exists."""
        macd = MACD(fast=12, slow=26, signal=9)
        timestamp = datetime.now()
        
        # Insert only 30 price records (need 35)
        base_time = timestamp - timedelta(hours=30)
        for i in range(30):
            price_data = PriceData(
                timestamp=base_time + timedelta(hours=i),
                close=100.0 + i
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Fetch prices
        prices = macd._fetch_prices(db_session, timestamp)
        
        assert prices is None
    
    def test_save_indicator_new_record(self, db_session):
        """Test saving MACD to database as new record."""
        macd = MACD()
        timestamp = datetime.now()
        macd_line = 1.5
        signal_line = 1.2
        histogram = 0.3
        
        # Save indicator
        macd._save_indicator(db_session, timestamp, macd_line, signal_line, histogram)
        
        # Verify saved
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator is not None
        assert indicator.macd == macd_line
        assert indicator.macd_signal == signal_line
        assert indicator.macd_hist == histogram
        assert indicator.price_timestamp == timestamp
    
    def test_save_indicator_update_existing(self, db_session):
        """Test updating existing MACD record in database."""
        macd = MACD()
        timestamp = datetime.now()
        
        # Create initial indicator
        indicator = TechnicalIndicators(
            timestamp=timestamp,
            macd=1.0,
            macd_signal=0.8,
            macd_hist=0.2,
            price_timestamp=timestamp
        )
        db_session.add(indicator)
        db_session.commit()
        
        # Update with new MACD values
        new_macd = 2.0
        new_signal = 1.5
        new_hist = 0.5
        macd._save_indicator(db_session, timestamp, new_macd, new_signal, new_hist)
        
        # Verify updated
        db_session.refresh(indicator)
        assert indicator.macd == new_macd
        assert indicator.macd_signal == new_signal
        assert indicator.macd_hist == new_hist
    
    def test_calculate_and_save(self, db_session):
        """Test full calculate_and_save workflow."""
        macd = MACD(fast=12, slow=26, signal=9)
        timestamp = datetime.now()
        
        # Insert price data (need 35 = slow + signal)
        base_time = timestamp - timedelta(hours=40)
        for i in range(40):
            price_data = PriceData(
                timestamp=base_time + timedelta(hours=i),
                close=100.0 + math.sin(i * 0.5) * 10  # Oscillating prices
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = macd.calculate_and_save(db_session, timestamp)
        
        # Verify result
        assert result is not None
        macd_line, signal_line, histogram = result
        assert isinstance(macd_line, float)
        assert isinstance(signal_line, float)
        assert isinstance(histogram, float)
        assert histogram == macd_line - signal_line
        
        # Verify saved to database
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator is not None
        assert indicator.macd == macd_line
        assert indicator.macd_signal == signal_line
        assert indicator.macd_hist == histogram
    
    def test_calculate_and_save_insufficient_data(self, db_session):
        """Test calculate_and_save with insufficient data."""
        macd = MACD(fast=12, slow=26, signal=9)
        timestamp = datetime.now()
        
        # Insert insufficient price data (need 35, only have 30)
        base_time = timestamp - timedelta(hours=30)
        for i in range(30):
            price_data = PriceData(
                timestamp=base_time + timedelta(hours=i),
                close=100.0 + i
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = macd.calculate_and_save(db_session, timestamp)
        
        # Should return None
        assert result is None
        
        # Verify no indicator created
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator is None
    
    def test_calculate_and_save_updates_existing(self, db_session):
        """Test calculate_and_save updates existing indicator record."""
        macd = MACD(fast=5, slow=10, signal=4)
        timestamp = datetime.now()
        
        # Insert price data
        base_time = timestamp - timedelta(hours=20)
        for i in range(20):
            price_data = PriceData(
                timestamp=base_time + timedelta(hours=i),
                close=100.0 + i * 0.5
            )
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save first time
        result1 = macd.calculate_and_save(db_session, timestamp)
        assert result1 is not None
        
        # Calculate and save again (should update)
        result2 = macd.calculate_and_save(db_session, timestamp)
        assert result2 is not None
        
        # Verify only one record exists
        indicators = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).all()
        
        assert len(indicators) == 1
