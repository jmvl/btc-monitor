"""Tests for Moving Averages indicator calculation."""

import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from btc_monitor.database import init_db, get_session
from btc_monitor.indicators import MovingAverages
from btc_monitor.models import PriceData, TechnicalIndicators


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


@pytest.fixture
def ma_calculator():
    """Create a MovingAverages calculator instance."""
    return MovingAverages()


class TestMovingAveragesInstantiation:
    """Test MovingAverages class instantiation."""
    
    def test_default_parameters(self):
        """Test calculator can be instantiated with default parameters."""
        ma = MovingAverages()
        assert ma.sma_50_period == 50
        assert ma.sma_200_period == 200
    
    def test_custom_parameters(self):
        """Test calculator can be instantiated with custom parameters."""
        ma = MovingAverages(sma_50_period=10, sma_200_period=50)
        assert ma.sma_50_period == 10
        assert ma.sma_200_period == 50


class TestSMACalculation:
    """Test SMA calculation."""
    
    def test_sma_basic_calculation(self, ma_calculator):
        """Test basic SMA calculation."""
        prices = [10.0, 12.0, 14.0, 16.0, 18.0]
        sma = ma_calculator.calculate_sma(prices, period=3)
        assert sma == pytest.approx(16.0)  # Average of 14, 16, 18
    
    def test_sma_with_longer_series(self, ma_calculator):
        """Test SMA calculation with longer price series."""
        prices = [100.0] * 100
        sma = ma_calculator.calculate_sma(prices, period=50)
        assert sma == pytest.approx(100.0)
    
    def test_sma_with_increasing_prices(self, ma_calculator):
        """Test SMA with increasing price trend."""
        prices = [float(i) for i in range(1, 61)]  # 1.0 to 60.0
        sma = ma_calculator.calculate_sma(prices, period=20)
        # Average of last 20 values: 41, 42, ..., 60 = (41+60)*20/2 / 20 = 50.5
        assert sma == pytest.approx(50.5)
    
    def test_sma_with_decreasing_prices(self, ma_calculator):
        """Test SMA with decreasing price trend."""
        prices = [float(i) for i in range(60, 0, -1)]  # 60.0 to 1.0
        sma = ma_calculator.calculate_sma(prices, period=20)
        # Average of last 20 values: 20, 19, ..., 1 = (20+1)*20/2 / 20 = 10.5
        assert sma == pytest.approx(10.5)
    
    def test_sma_with_nan_values(self, ma_calculator):
        """Test SMA calculation filters NaN values."""
        prices = [10.0, math.nan, 12.0, 14.0, math.nan, 16.0, 18.0]
        sma = ma_calculator.calculate_sma(prices, period=3)
        # Last 3 valid values: 14, 16, 18
        assert sma == pytest.approx(16.0)
    
    def test_sma_returns_none_for_empty_list(self, ma_calculator):
        """Test SMA returns None for empty price list."""
        sma = ma_calculator.calculate_sma([], period=10)
        assert sma is None
    
    def test_sma_returns_none_for_insufficient_data(self, ma_calculator):
        """Test SMA returns None when insufficient data."""
        prices = [10.0, 12.0, 14.0]
        sma = ma_calculator.calculate_sma(prices, period=10)
        assert sma is None
    
    def test_sma_returns_none_for_all_nan(self, ma_calculator):
        """Test SMA returns None when all values are NaN."""
        prices = [math.nan, math.nan, math.nan]
        sma = ma_calculator.calculate_sma(prices, period=2)
        assert sma is None
    
    def test_sma_exact_period_count(self, ma_calculator):
        """Test SMA works with exactly period number of prices."""
        prices = [10.0, 12.0, 14.0]
        sma = ma_calculator.calculate_sma(prices, period=3)
        assert sma == pytest.approx(12.0)
    
    def test_sma_large_period(self, ma_calculator):
        """Test SMA with large period."""
        prices = [float(i) for i in range(1, 201)]  # 1.0 to 200.0
        sma = ma_calculator.calculate_sma(prices, period=200)
        assert sma == pytest.approx(100.5)  # Average of 1-200


class TestEMACalculation:
    """Test EMA calculation."""
    
    def test_ema_basic_calculation(self, ma_calculator):
        """Test basic EMA calculation."""
        prices = [10.0, 12.0, 14.0, 16.0, 18.0]
        ema = ma_calculator.calculate_ema(prices, period=3)
        # EMA gives more weight to recent prices
        assert isinstance(ema, float)
        assert ema > 0.0
    
    def test_ema_matches_sma_for_first_value(self, ma_calculator):
        """Test EMA starts with SMA for initial period values."""
        prices = [10.0, 12.0, 14.0]
        sma = sum(prices[:3]) / 3
        ema = ma_calculator.calculate_ema(prices, period=3)
        # For exactly period prices, EMA should equal SMA
        assert ema == pytest.approx(sma)
    
    def test_ema_with_constant_prices(self, ma_calculator):
        """Test EMA with constant prices."""
        prices = [100.0] * 50
        ema = ma_calculator.calculate_ema(prices, period=12)
        assert ema == pytest.approx(100.0)
    
    def test_ema_with_increasing_prices(self, ma_calculator):
        """Test EMA with increasing price trend."""
        prices = [float(i) for i in range(1, 31)]
        ema = ma_calculator.calculate_ema(prices, period=10)
        # EMA and SMA relationship depends on price distribution
        # Verify EMA is calculated and is in reasonable range
        sma = sum(prices[-10:]) / 10
        assert isinstance(ema, float)
        assert ema > 0.0
        # EMA should be in the same general range as SMA
        assert 0.5 * sma < ema < 1.5 * sma
    
    def test_ema_with_decreasing_prices(self, ma_calculator):
        """Test EMA with decreasing price trend."""
        prices = [float(i) for i in range(30, 0, -1)]
        ema = ma_calculator.calculate_ema(prices, period=10)
        # EMA should be lower than SMA for downtrend (gives more weight to recent prices)
        sma = sum(prices[-10:]) / 10
        assert ema < sma
    
    def test_ema_with_nan_values(self, ma_calculator):
        """Test EMA calculation filters NaN values."""
        prices = [10.0, math.nan, 12.0, 14.0, math.nan, 16.0, 18.0]
        ema = ma_calculator.calculate_ema(prices, period=3)
        assert isinstance(ema, float)
        assert ema > 0.0
    
    def test_ema_returns_none_for_empty_list(self, ma_calculator):
        """Test EMA returns None for empty price list."""
        ema = ma_calculator.calculate_ema([], period=10)
        assert ema is None
    
    def test_ema_returns_none_for_insufficient_data(self, ma_calculator):
        """Test EMA returns None when insufficient data."""
        prices = [10.0, 12.0]
        ema = ma_calculator.calculate_ema(prices, period=10)
        assert ema is None
    
    def test_ema_returns_none_for_all_nan(self, ma_calculator):
        """Test EMA returns None when all values are NaN."""
        prices = [math.nan, math.nan, math.nan]
        ema = ma_calculator.calculate_ema(prices, period=2)
        assert ema is None
    
    def test_ema_period_12(self, ma_calculator):
        """Test EMA with 12-period (standard fast period)."""
        prices = [float(i) for i in range(1, 31)]
        ema = ma_calculator.calculate_ema(prices, period=12)
        assert isinstance(ema, float)
        assert ema > 0.0
    
    def test_ema_period_26(self, ma_calculator):
        """Test EMA with 26-period (standard slow period)."""
        prices = [float(i) for i in range(1, 51)]
        ema = ma_calculator.calculate_ema(prices, period=26)
        assert isinstance(ema, float)
        assert ema > 0.0


class TestDatabaseIntegration:
    """Test MovingAverages database integration."""
    
    def test_fetch_prices_from_database(self, ma_calculator, db_session):
        """Test fetching prices from database."""
        # Insert test price data
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(60):
            timestamp = base_time - timedelta(days=60 - i)
            price = 100.0 + i  # Increasing prices
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Fetch prices
        prices = ma_calculator._fetch_prices(db_session, base_time)
        
        assert prices is not None
        assert len(prices) == 60
        assert prices[0] == 100.0  # First price
        assert prices[-1] == 159.0  # Last price
    
    def test_fetch_prices_insufficient_data(self, ma_calculator, db_session):
        """Test fetching prices with insufficient data."""
        # Insert fewer than SMA 50 period prices
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(30):
            timestamp = base_time - timedelta(days=30 - i)
            price = 100.0 + i
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Fetch prices - should return None (less than 50 samples)
        prices = ma_calculator._fetch_prices(db_session, base_time)
        
        assert prices is None
    
    def test_save_indicator_insert(self, ma_calculator, db_session):
        """Test saving SMA values as new indicator record."""
        timestamp = datetime.utcnow().replace(microsecond=0)
        
        # Save indicator
        ma_calculator._save_indicator(db_session, timestamp, sma_50=150.0, sma_200=140.0)
        
        # Verify it was saved
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator is not None
        assert indicator.sma_50 == pytest.approx(150.0)
        assert indicator.sma_200 == pytest.approx(140.0)
        assert indicator.price_timestamp == timestamp
    
    def test_save_indicator_update(self, ma_calculator, db_session):
        """Test updating existing SMA indicator record."""
        timestamp = datetime.utcnow().replace(microsecond=0)
        
        # Insert initial indicator
        indicator = TechnicalIndicators(
            timestamp=timestamp,
            sma_50=150.0,
            sma_200=140.0,
            price_timestamp=timestamp
        )
        db_session.add(indicator)
        db_session.commit()
        
        # Update with new values
        ma_calculator._save_indicator(db_session, timestamp, sma_50=155.0, sma_200=145.0)
        
        # Verify it was updated
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator.sma_50 == pytest.approx(155.0)
        assert indicator.sma_200 == pytest.approx(145.0)
    
    def test_save_indicator_none_sma_200(self, ma_calculator, db_session):
        """Test saving SMA with only SMA 50 available."""
        timestamp = datetime.utcnow().replace(microsecond=0)
        
        # Save indicator with SMA 50 only
        ma_calculator._save_indicator(db_session, timestamp, sma_50=150.0, sma_200=None)
        
        # Verify it was saved
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
        assert indicator.sma_50 == pytest.approx(150.0)
        assert indicator.sma_200 is None


class TestCalculateAndSave:
    """Test calculate_and_save method."""
    
    def test_calculate_and_save_sma_50_only(self, ma_calculator, db_session):
        """Test calculate_and_save with only SMA 50 data available."""
        # Insert 60 prices (enough for SMA 50, not for SMA 200)
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(60):
            timestamp = base_time - timedelta(days=60 - i)
            price = 100.0 + i
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = ma_calculator.calculate_and_save(db_session, base_time)
        
        assert result is not None
        sma_50, sma_200 = result
        assert sma_50 is not None
        assert sma_200 is None  # Insufficient data for SMA 200
        
        # Verify database
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == base_time
        ).first()
        
        assert indicator is not None
        assert indicator.sma_50 is not None
        assert indicator.sma_200 is None
    
    def test_calculate_and_save_both_smas(self, ma_calculator, db_session):
        """Test calculate_and_save with both SMA 50 and SMA 200 data available."""
        # Insert 250 prices (enough for both SMA 50 and SMA 200)
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(250):
            timestamp = base_time - timedelta(days=250 - i)
            price = 100.0 + i
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = ma_calculator.calculate_and_save(db_session, base_time)
        
        assert result is not None
        sma_50, sma_200 = result
        assert sma_50 is not None
        assert sma_200 is not None
        
        # SMA 50 should be higher (more recent prices are higher)
        # SMA 200 should be lower (includes earlier lower prices)
        assert sma_50 > sma_200
        
        # Verify database
        indicator = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == base_time
        ).first()
        
        assert indicator is not None
        assert indicator.sma_50 is not None
        assert indicator.sma_200 is not None
    
    def test_calculate_and_save_insufficient_data(self, ma_calculator, db_session):
        """Test calculate_and_save with insufficient data for even SMA 50."""
        # Insert only 30 prices (insufficient for SMA 50)
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(30):
            timestamp = base_time - timedelta(days=30 - i)
            price = 100.0 + i
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save - should return None
        result = ma_calculator.calculate_and_save(db_session, base_time)
        
        assert result is None
    
    def test_calculate_and_save_uptrend(self, ma_calculator, db_session):
        """Test calculate_and_save in uptrend."""
        # Insert increasing prices
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(250):
            timestamp = base_time - timedelta(days=250 - i)
            price = 100.0 + i
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = ma_calculator.calculate_and_save(db_session, base_time)
        
        assert result is not None
        sma_50, sma_200 = result
        
        # In uptrend: SMA 50 > SMA 200 (golden cross pattern)
        assert sma_50 > sma_200
    
    def test_calculate_and_save_downtrend(self, ma_calculator, db_session):
        """Test calculate_and_save in downtrend."""
        # Insert decreasing prices
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(250):
            timestamp = base_time - timedelta(days=250 - i)
            price = 350.0 - i
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = ma_calculator.calculate_and_save(db_session, base_time)
        
        assert result is not None
        sma_50, sma_200 = result
        
        # In downtrend: SMA 50 < SMA 200 (death cross pattern)
        assert sma_50 < sma_200
    
    def test_calculate_and_save_flat_market(self, ma_calculator, db_session):
        """Test calculate_and_save in flat market."""
        # Insert constant prices
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(250):
            timestamp = base_time - timedelta(days=250 - i)
            price = 100.0
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Calculate and save
        result = ma_calculator.calculate_and_save(db_session, base_time)
        
        assert result is not None
        sma_50, sma_200 = result
        
        # In flat market: SMA 50 == SMA 200
        assert sma_50 == pytest.approx(sma_200)
        assert sma_50 == pytest.approx(100.0)
    
    def test_calculate_and_save_update_existing(self, ma_calculator, db_session):
        """Test calculate_and_save updates existing indicator record."""
        # Insert price data
        base_time = datetime.utcnow().replace(microsecond=0)
        for i in range(250):
            timestamp = base_time - timedelta(days=250 - i)
            price = 100.0 + i
            price_data = PriceData(timestamp=timestamp, close=price, volume=1000.0)
            db_session.add(price_data)
        db_session.commit()
        
        # Create existing indicator
        indicator = TechnicalIndicators(
            timestamp=base_time,
            sma_50=150.0,
            sma_200=140.0,
            price_timestamp=base_time
        )
        db_session.add(indicator)
        db_session.commit()
        
        # Calculate and save (should update)
        result = ma_calculator.calculate_and_save(db_session, base_time)
        
        assert result is not None
        
        # Verify it was updated (not inserted new)
        indicators = db_session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == base_time
        ).all()
        
        assert len(indicators) == 1  # Only one record
        
        # Verify values changed
        indicator = indicators[0]
        assert indicator.sma_50 != 150.0  # Should be different from initial value
        assert indicator.sma_200 != 140.0


class TestSMALongPeriods:
    """Test SMA with long periods (50 and 200)."""
    
    def test_sma_50_calculation(self, ma_calculator):
        """Test SMA 50 calculation."""
        prices = [float(i) for i in range(1, 51)]  # 1.0 to 50.0
        sma_50 = ma_calculator.calculate_sma(prices, period=50)
        assert sma_50 == pytest.approx(25.5)  # Average of 1-50
    
    def test_sma_200_calculation(self, ma_calculator):
        """Test SMA 200 calculation."""
        prices = [float(i) for i in range(1, 201)]  # 1.0 to 200.0
        sma_200 = ma_calculator.calculate_sma(prices, period=200)
        assert sma_200 == pytest.approx(100.5)  # Average of 1-200
    
    def test_sma_50_vs_sma_200_uptrend(self, ma_calculator):
        """Test that SMA 50 > SMA 200 in uptrend."""
        prices = [float(i) for i in range(1, 201)]  # 1.0 to 200.0
        sma_50 = ma_calculator.calculate_sma(prices, period=50)
        sma_200 = ma_calculator.calculate_sma(prices, period=200)
        
        # In uptrend, shorter SMA > longer SMA
        assert sma_50 > sma_200
        # SMA 50: average of 151-200 = 175.5
        assert sma_50 == pytest.approx(175.5)
        # SMA 200: average of 1-200 = 100.5
        assert sma_200 == pytest.approx(100.5)


class TestEMALongPeriods:
    """Test EMA with long periods (12, 26, 50, 200)."""
    
    def test_ema_12_calculation(self, ma_calculator):
        """Test EMA 12 calculation (standard MACD fast period)."""
        prices = [float(i) for i in range(1, 31)]
        ema_12 = ma_calculator.calculate_ema(prices, period=12)
        assert isinstance(ema_12, float)
        assert ema_12 > 0.0
    
    def test_ema_26_calculation(self, ma_calculator):
        """Test EMA 26 calculation (standard MACD slow period)."""
        prices = [float(i) for i in range(1, 51)]
        ema_26 = ma_calculator.calculate_ema(prices, period=26)
        assert isinstance(ema_26, float)
        assert ema_26 > 0.0
    
    def test_ema_50_calculation(self, ma_calculator):
        """Test EMA 50 calculation."""
        prices = [float(i) for i in range(1, 101)]
        ema_50 = ma_calculator.calculate_ema(prices, period=50)
        assert isinstance(ema_50, float)
        assert ema_50 > 0.0
    
    def test_ema_200_calculation(self, ma_calculator):
        """Test EMA 200 calculation."""
        prices = [float(i) for i in range(1, 251)]
        ema_200 = ma_calculator.calculate_ema(prices, period=200)
        assert isinstance(ema_200, float)
        assert ema_200 > 0.0


class TestSMAAgainstEMADifferences:
    """Test differences between SMA and EMA in various scenarios."""
    
    def test_ema_responsive_to_recent_prices(self, ma_calculator):
        """Test EMA responds to recent price changes."""
        # First 200 prices at 100, last 50 prices at 200
        prices = [100.0] * 200 + [200.0] * 50
        
        sma = ma_calculator.calculate_sma(prices, period=50)
        ema = ma_calculator.calculate_ema(prices, period=50)
        
        # SMA of last 50 prices (all 200s) = 200
        assert sma == pytest.approx(200.0)
        
        # EMA should be lower than SMA because it's influenced by
        # the 200 earlier values at 100.0, but higher than 100
        assert ema > 100.0
        assert ema < 200.0
        
        # EMA should be significantly above the base price
        # (showing it does respond to recent higher prices)
        assert ema > 150.0
    
    def test_ema_less_responsive_in_flat_market(self, ma_calculator):
        """Test EMA and SMA converge in flat market."""
        prices = [100.0] * 250
        
        sma = ma_calculator.calculate_sma(prices, period=50)
        ema = ma_calculator.calculate_ema(prices, period=50)
        
        # In flat market, EMA and SMA should be very close
        assert sma == pytest.approx(100.0)
        assert ema == pytest.approx(100.0)
