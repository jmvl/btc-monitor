"""Tests for logging configuration and error handling."""

import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from btc_monitor.logging import (
    setup_logging,
    log_api_call,
    log_indicator_calculation,
    log_database_operation,
    CircuitBreaker,
    CircuitBreakerOpenError,
)
from btc_monitor.config import Config


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self, tmp_path):
        """Test logging setup with default parameters."""
        log_file = tmp_path / "btc_monitor.log"
        error_log_file = tmp_path / "error.log"

        root_logger = setup_logging(
            config=None,
            log_file=str(log_file),
            error_log_file=str(error_log_file),
        )

        # Check that logger was configured
        assert root_logger is not None
        assert root_logger.level >= logging.INFO

        # Check that log files were created
        assert log_file.exists()
        assert error_log_file.exists()

        # Check that handlers were added
        assert len(root_logger.handlers) == 3  # console, file, error file

        # Log a test message
        test_logger = logging.getLogger("test")
        test_logger.info("Test message")

        # Check that log file contains the message
        log_content = log_file.read_text()
        assert "Test message" in log_content

    def test_setup_logging_with_config(self, tmp_path):
        """Test logging setup with config object."""
        config = Config()
        config.logging.level = "DEBUG"
        config.logging.file = str(tmp_path / "btc_monitor.log")
        config.logging.error_file = str(tmp_path / "error.log")

        root_logger = setup_logging(config=config)

        # Check that log level is DEBUG
        assert root_logger.level == logging.DEBUG

        # Check that log files were created
        assert Path(config.logging.file).exists()
        assert Path(config.logging.error_file).exists()

    def test_setup_logging_invalid_level(self, tmp_path):
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            setup_logging(
                config=None,
                log_level="INVALID",
                log_file=str(tmp_path / "test.log"),
                error_log_file=str(tmp_path / "error.log"),
            )

    def test_setup_logging_log_levels(self, tmp_path):
        """Test that different log levels work correctly."""
        log_file = tmp_path / "test.log"
        error_log_file = tmp_path / "error.log"

        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            root_logger = setup_logging(
                config=None,
                log_level=level,
                log_file=str(log_file),
                error_log_file=str(error_log_file),
            )

            expected_level = getattr(logging, level)
            assert root_logger.level == expected_level

    def test_error_log_only_errors(self, tmp_path):
        """Test that error.log only contains ERROR level and above."""
        log_file = tmp_path / "btc_monitor.log"
        error_log_file = tmp_path / "error.log"

        setup_logging(
            config=None,
            log_file=str(log_file),
            error_log_file=str(error_log_file),
        )

        logger = logging.getLogger("test")

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # Check main log file contains messages at INFO level and above (DEBUG is filtered out)
        main_log_content = log_file.read_text()
        assert "Debug message" not in main_log_content  # DEBUG is filtered by log level
        assert "Info message" in main_log_content
        assert "Warning message" in main_log_content
        assert "Error message" in main_log_content
        assert "Critical message" in main_log_content

        # Check error log file only contains ERROR and CRITICAL
        error_log_content = error_log_file.read_text()
        assert "Debug message" not in error_log_content
        assert "Info message" not in error_log_content
        assert "Warning message" not in error_log_content
        assert "Error message" in error_log_content
        assert "Critical message" in error_log_content


class TestLogApiCall:
    """Tests for log_api_call function."""

    def test_log_api_call_success(self, caplog):
        """Test logging successful API call."""
        with caplog.at_level(logging.INFO):
            log_api_call(
                endpoint="BTC-USD",
                method="GET",
                status_code=200,
                response_time_ms=123.45,
            )

        assert "API call: GET BTC-USD" in caplog.text
        assert "HTTP 200" in caplog.text
        assert "123ms" in caplog.text

    def test_log_api_call_failure(self, caplog):
        """Test logging failed API call."""
        error = Exception("Connection timeout")

        with caplog.at_level(logging.ERROR):
            log_api_call(
                endpoint="BTC-USD",
                method="GET",
                response_time_ms=500,
                error=error,
            )

        assert "API call failed: GET BTC-USD" in caplog.text
        assert "Connection timeout" in caplog.text
        assert "Exception" in caplog.text

    def test_log_api_call_without_status(self, caplog):
        """Test logging API call without status code."""
        with caplog.at_level(logging.INFO):
            log_api_call(
                endpoint="search",
                method="POST",
                response_time_ms=50,
            )

        assert "API call: POST search" in caplog.text
        assert "completed" in caplog.text
        assert "50ms" in caplog.text


class TestLogIndicatorCalculation:
    """Tests for log_indicator_calculation function."""

    def test_log_indicator_success(self, caplog):
        """Test logging successful indicator calculation."""
        with caplog.at_level(logging.INFO):
            log_indicator_calculation(
                indicator_name="RSI",
                parameters={"period": 14},
                result=65.5,
            )

        assert "RSI calculated [period=14]" in caplog.text
        assert "Result: 65.5" in caplog.text

    def test_log_indicator_failure(self, caplog):
        """Test logging failed indicator calculation."""
        error = ValueError("Insufficient data")

        with caplog.at_level(logging.ERROR):
            log_indicator_calculation(
                indicator_name="MACD",
                parameters={"fast": 12, "slow": 26},
                result=None,
                error=error,
            )

        assert "MACD calculation failed [fast=12, slow=26]" in caplog.text
        assert "Insufficient data" in caplog.text

    def test_log_indicator_none_result(self, caplog):
        """Test logging indicator calculation with None result."""
        with caplog.at_level(logging.WARNING):
            log_indicator_calculation(
                indicator_name="RSI",
                parameters={"period": 14},
                result=None,
            )

        assert "RSI calculation returned None [period=14]" in caplog.text


class TestLogDatabaseOperation:
    """Tests for log_database_operation function."""

    def test_log_database_success(self, caplog):
        """Test logging successful database operation."""
        with caplog.at_level(logging.DEBUG):
            log_database_operation(
                operation="INSERT",
                table="price_data",
                record_id=123,
            )

        assert "Database INSERT on price_data (id=123)" in caplog.text

    def test_log_database_failure(self, caplog):
        """Test logging failed database operation."""
        error = Exception("Database connection failed")

        with caplog.at_level(logging.ERROR):
            log_database_operation(
                operation="UPDATE",
                table="technical_indicators",
                record_id=456,
                error=error,
            )

        assert "Database UPDATE failed on technical_indicators (id=456)" in caplog.text
        assert "Database connection failed" in caplog.text

    def test_log_database_without_record_id(self, caplog):
        """Test logging database operation without record ID."""
        with caplog.at_level(logging.DEBUG):
            log_database_operation(
                operation="SELECT",
                table="trend_analysis",
            )

        assert "Database SELECT on trend_analysis" in caplog.text


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_circuit_breaker_success(self):
        """Test circuit breaker on successful call."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

        def success_func():
            return "success"

        result = cb.call(success_func)

        assert result == "success"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

        def fail_func():
            raise ValueError("API error")

        # Trigger failures until threshold
        for i in range(3):
            with pytest.raises(ValueError):
                cb.call(fail_func)

        # Circuit should be OPEN
        assert cb.state == "OPEN"
        assert cb.failure_count == 3

    def test_circuit_breaker_blocks_when_open(self):
        """Test circuit breaker blocks calls when OPEN."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

        def fail_func():
            raise ValueError("API error")

        # Trigger failures to open circuit
        for i in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)

        assert cb.state == "OPEN"

        # Next call should be blocked
        with pytest.raises(CircuitBreakerOpenError, match="Circuit breaker is OPEN"):
            cb.call(fail_func)

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker enters HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        def fail_func():
            raise ValueError("API error")

        # Trigger failures to open circuit
        for i in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)

        assert cb.state == "OPEN"

        # Wait for recovery timeout
        import time
        time.sleep(0.15)

        # Next call should put circuit in HALF_OPEN
        def success_func():
            return "success"

        result = cb.call(success_func)

        assert result == "success"
        assert cb.state == "CLOSED"  # Should recover and close
        assert cb.failure_count == 0

    def test_circuit_breaker_reset(self):
        """Test circuit breaker can be manually reset."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

        def fail_func():
            raise ValueError("API error")

        # Trigger failures to open circuit
        for i in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)

        assert cb.state == "OPEN"

        # Reset circuit breaker
        cb.reset()

        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

        # Should allow calls again
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"

    def test_circuit_breaker_get_state(self):
        """Test getting circuit breaker state."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)

        state = cb.get_state()

        assert state["state"] == "CLOSED"
        assert state["failure_count"] == 0
        assert state["failure_threshold"] == 3
        assert state["recovery_timeout"] == 60.0
        assert state["last_failure_time"] is None

    def test_circuit_breaker_custom_exception(self):
        """Test circuit breaker with custom exception type."""
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=60.0,
            expected_exception=ValueError,
        )

        def fail_func():
            raise ValueError("API error")

        def other_fail_func():
            raise RuntimeError("Other error")

        # Trigger failures with expected exception
        for i in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)

        # Circuit should be OPEN
        assert cb.state == "OPEN"

        # Reset for next test
        cb.reset()

        # Other exception should not count as failure
        with pytest.raises(RuntimeError):
            cb.call(other_fail_func)

        # Circuit should still be CLOSED
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""

    def test_circuit_breaker_open_error_message(self):
        """Test CircuitBreakerOpenError error message."""
        error = CircuitBreakerOpenError("Circuit breaker is OPEN")
        assert "Circuit breaker is OPEN" in str(error)


class TestIntegrationLoggingWithFetchers:
    """Integration tests for logging with actual fetcher."""

    def test_price_fetcher_logging(self, tmp_path, caplog):
        """Test that PriceFetcher logs API calls."""
        from btc_monitor.fetchers import PriceFetcher

        log_file = tmp_path / "btc_monitor.log"
        error_log_file = tmp_path / "error.log"

        setup_logging(
            config=None,
            log_level="DEBUG",
            log_file=str(log_file),
            error_log_file=str(error_log_file),
        )

        # Create a temporary database
        db_file = tmp_path / "test.db"
        from btc_monitor.database import init_db
        init_db(str(db_file))

        # Create fetcher with circuit breaker disabled for testing
        fetcher = PriceFetcher(db_path=str(db_file), use_circuit_breaker=False)

        with caplog.at_level(logging.INFO):
            # Try to fetch current price (this might fail in test environment)
            price = fetcher.get_current_price()

        # Check that API call was logged
        if price is None:
            # Should have error logs
            assert any("API call" in record.message for record in caplog.records)

    def test_price_fetcher_circuit_breaker_health(self, tmp_path):
        """Test that PriceFetcher returns health status."""
        from btc_monitor.fetchers import PriceFetcher

        # Create a temporary database
        db_file = tmp_path / "test.db"
        from btc_monitor.database import init_db
        init_db(str(db_file))

        fetcher = PriceFetcher(db_path=str(db_file), use_circuit_breaker=True)

        health = fetcher.get_health()

        assert health["component"] == "price_fetcher"
        assert health["status"] == "healthy"
        assert health["circuit_breaker"] is not None
        assert health["circuit_breaker"]["state"] == "CLOSED"
