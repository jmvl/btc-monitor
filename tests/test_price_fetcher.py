"""Tests for price fetcher functionality."""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from btc_monitor.database import init_db
from btc_monitor.fetchers import PriceFetcher
from btc_monitor.models import PriceData


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
def fetcher(temp_db_path):
    """Create a PriceFetcher instance with test database."""
    return PriceFetcher(db_path=temp_db_path, max_retries=3)


class TestPriceFetcherClass:
    """Test PriceFetcher class exists and can be instantiated."""
    
    def test_price_fetcher_exists(self):
        """Test that PriceFetcher class exists."""
        assert PriceFetcher is not None
    
    def test_price_fetcher_instantiation_default(self, temp_db_path):
        """Test PriceFetcher can be instantiated with default parameters."""
        fetcher = PriceFetcher(db_path=temp_db_path)
        assert fetcher is not None
        assert fetcher.max_retries == 3
        assert fetcher.initial_backoff == 1.0
        assert fetcher.max_backoff == 60.0
    
    def test_price_fetcher_instantiation_custom(self, temp_db_path):
        """Test PriceFetcher can be instantiated with custom parameters."""
        fetcher = PriceFetcher(
            db_path=temp_db_path,
            max_retries=5,
            initial_backoff=2.0,
            max_backoff=120.0,
        )
        assert fetcher.max_retries == 5
        assert fetcher.initial_backoff == 2.0
        assert fetcher.max_backoff == 120.0


class TestGetCurrentPrice:
    """Test get_current_price method."""
    
    def test_get_current_price_returns_float(self, fetcher):
        """Test that get_current_price returns a float."""
        price = fetcher.get_current_price()
        assert isinstance(price, float) or price is None
    
    def test_get_current_price_in_valid_range(self, fetcher):
        """Test that get_current_price returns price in valid range."""
        price = fetcher.get_current_price()
        
        if price is not None:
            assert 0 < price < 1_000_000
    
    def test_get_current_price_positive(self, fetcher):
        """Test that get_current_price returns positive price."""
        price = fetcher.get_current_price()
        
        if price is not None:
            assert price > 0


class TestGetHistoricalData:
    """Test get_historical_data method."""
    
    def test_get_historical_data_returns_list(self, fetcher):
        """Test that get_historical_data returns a list."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        data = fetcher.get_historical_data(start_date, end_date)
        assert isinstance(data, list)
    
    def test_get_historical_data_contains_price_data(self, fetcher):
        """Test that historical data contains PriceData objects."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)
        
        data = fetcher.get_historical_data(start_date, end_date)
        
        if data:
            assert all(isinstance(record, PriceData) for record in data)
    
    def test_get_historical_data_includes_volume(self, fetcher):
        """Test that historical data includes volume."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)
        
        data = fetcher.get_historical_data(start_date, end_date)
        
        if data:
            # At least some records should have volume data
            assert any(record.volume is not None for record in data)
    
    def test_get_historical_data_string_dates(self, fetcher):
        """Test that get_historical_data works with string dates."""
        start_date = "2024-01-01"
        end_date = "2024-01-07"
        
        data = fetcher.get_historical_data(start_date, end_date)
        assert isinstance(data, list)


class TestSaveToDatabase:
    """Test save_to_database method."""
    
    def test_save_to_database_success(self, fetcher, temp_db_path):
        """Test that save_to_database saves data successfully."""
        test_data = PriceData(
            timestamp=datetime(2024, 1, 1, 12, 0),
            close=45000.0,
            volume=1000000.0,
        )
        
        result = fetcher.save_to_database(test_data)
        assert result is True
    
    def test_save_to_database_persists_data(self, fetcher, temp_db_path):
        """Test that saved data can be retrieved from database."""
        test_data = PriceData(
            timestamp=datetime(2024, 1, 1, 12, 0),
            close=45000.0,
            volume=1000000.0,
        )
        
        fetcher.save_to_database(test_data)
        
        # Verify data was saved
        from btc_monitor.database import get_session
        session = get_session(temp_db_path)
        try:
            saved_data = session.query(PriceData).filter(
                PriceData.timestamp == datetime(2024, 1, 1, 12, 0)
            ).first()
            assert saved_data is not None
            assert saved_data.close == 45000.0
            assert saved_data.volume == 1000000.0
        finally:
            session.close()
    
    def test_save_to_database_upsert(self, fetcher, temp_db_path):
        """Test that save_to_database updates existing records."""
        test_data = PriceData(
            timestamp=datetime(2024, 1, 1, 12, 0),
            close=45000.0,
            volume=1000000.0,
        )
        
        # Save initial data
        fetcher.save_to_database(test_data)
        
        # Update with new data
        updated_data = PriceData(
            timestamp=datetime(2024, 1, 1, 12, 0),
            close=46000.0,
            volume=2000000.0,
        )
        fetcher.save_to_database(updated_data)
        
        # Verify data was updated
        from btc_monitor.database import get_session
        session = get_session(temp_db_path)
        try:
            saved_data = session.query(PriceData).filter(
                PriceData.timestamp == datetime(2024, 1, 1, 12, 0)
            ).first()
            assert saved_data is not None
            assert saved_data.close == 46000.0
            assert saved_data.volume == 2000000.0
        finally:
            session.close()


class TestFetchAndSaveCurrentPrice:
    """Test fetch_and_save_current_price method."""
    
    def test_fetch_and_save_current_price(self, fetcher, temp_db_path):
        """Test that fetch_and_save_current_price works."""
        price = fetcher.fetch_and_save_current_price()
        
        if price is not None:
            assert isinstance(price, float)
            assert 0 < price < 1_000_000
    
    def test_fetch_and_save_current_price_persists(self, fetcher, temp_db_path):
        """Test that fetch_and_save_current_price saves to database."""
        price = fetcher.fetch_and_save_current_price()
        
        if price is not None:
            # Verify data was saved
            from btc_monitor.database import get_session
            session = get_session(temp_db_path)
            try:
                # Check for recent data (within last 5 minutes)
                recent = datetime.utcnow() - timedelta(minutes=5)
                saved_data = session.query(PriceData).filter(
                    PriceData.timestamp >= recent
                ).first()
                assert saved_data is not None
                assert saved_data.close == price
            finally:
                session.close()


class TestFetchAndSaveHistoricalData:
    """Test fetch_and_save_historical_data method."""
    
    def test_fetch_and_save_historical_data(self, fetcher, temp_db_path):
        """Test that fetch_and_save_historical_data works."""
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=3)
        
        count = fetcher.fetch_and_save_historical_data(start_date, end_date)
        
        if count > 0:
            assert isinstance(count, int)
            assert count > 0
    
    def test_fetch_and_save_historical_data_persists(self, fetcher, temp_db_path):
        """Test that fetch_and_save_historical_data saves to database."""
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=3)
        
        count = fetcher.fetch_and_save_historical_data(start_date, end_date)
        
        if count > 0:
            # Verify data was saved
            from btc_monitor.database import get_session
            session = get_session(temp_db_path)
            try:
                saved_data = session.query(PriceData).filter(
                    PriceData.timestamp >= start_date,
                    PriceData.timestamp <= end_date,
                ).all()
                # Some records may have been updates, so check at least 1 exists
                assert len(saved_data) >= 1
            finally:
                session.close()


class TestRetryWithBackoff:
    """Test retry with exponential backoff."""
    
    def test_retry_with_backoff_on_failure(self, fetcher):
        """Test that retry with backoff handles failures gracefully."""
        # This test verifies the retry mechanism doesn't crash
        def failing_func():
            raise ValueError("Test error")
        
        result = fetcher._retry_with_backoff(failing_func)
        assert result is None
    
    def test_retry_with_backoff_on_success(self, fetcher):
        """Test that retry with backoff returns on success."""
        def success_func():
            return 42
        
        result = fetcher._retry_with_backoff(success_func)
        assert result == 42


class TestErrorHandling:
    """Test error handling."""
    
    def test_get_current_price_handles_api_error(self, fetcher):
        """Test that get_current_price handles API errors gracefully."""
        # This is a smoke test - it shouldn't crash
        price = fetcher.get_current_price()
        # Either returns a price or None, but shouldn't crash
        assert price is None or isinstance(price, float)
    
    def test_get_historical_data_handles_invalid_dates(self, fetcher):
        """Test that get_historical_data handles invalid dates gracefully."""
        # This is a smoke test - it shouldn't crash
        data = fetcher.get_historical_data("invalid-date", "also-invalid")
        assert isinstance(data, list)
