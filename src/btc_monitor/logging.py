"""Logging configuration and utilities for BTC Monitor."""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Optional, Union

from btc_monitor.config import Config


def setup_logging(
    config: Optional[Config] = None,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    error_log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Set up comprehensive logging configuration for BTC Monitor.

    Creates two log files:
    - Main log file (INFO level and above): btc_monitor.log
    - Error log file (ERROR level and above): error.log

    Args:
        config: Configuration object (optional, for default values)
        log_level: Logging level (overrides config)
        log_file: Path to main log file (overrides config)
        error_log_file: Path to error log file (optional, default: error.log)

    Returns:
        Configured root logger instance.

    Raises:
        ValueError: If log_level is invalid.
    """
    # Determine log level
    if log_level is None and config is not None:
        log_level = config.logging.level
    if log_level is None:
        log_level = "INFO"

    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level.upper() not in valid_levels:
        raise ValueError(f"Invalid log level: {log_level}. Must be one of: {valid_levels}")

    # Determine log file paths
    if log_file is None and config is not None:
        log_file = config.logging.file
    if log_file is None:
        log_file = "btc_monitor.log"

    if error_log_file is None:
        # Use error.log in same directory as main log file
        log_dir = Path(log_file).parent
        error_log_file = str(log_dir / "error.log")

    # Create log directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    error_log_path = Path(error_log_file)
    error_log_path.parent.mkdir(parents=True, exist_ok=True)

    # Define log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # 1. Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # Show all levels on console
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. Main log file handler (INFO and above)
    # Use rotating file handler to prevent files from growing too large
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 3. Error log file handler (ERROR and above)
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("BTC Monitor logging initialized")
    logger.info(f"Log level: {log_level.upper()}")
    logger.info(f"Main log file: {log_file}")
    logger.info(f"Error log file: {error_log_file}")
    logger.info("=" * 60)

    return root_logger


def log_api_call(
    endpoint: str,
    method: str = "GET",
    status_code: Optional[int] = None,
    response_time_ms: Optional[float] = None,
    error: Optional[Exception] = None,
) -> None:
    """
    Log an API call with details.

    Args:
        endpoint: API endpoint being called.
        method: HTTP method (GET, POST, etc.).
        status_code: HTTP response status code (if successful).
        response_time_ms: Response time in milliseconds.
        error: Exception if the call failed.
    """
    logger = logging.getLogger("btc_monitor.api")

    if error:
        logger.error(
            f"API call failed: {method} {endpoint} - "
            f"Error: {type(error).__name__}: {error}",
            exc_info=True
        )
    else:
        status_text = f"HTTP {status_code}" if status_code else "completed"
        time_text = f" ({response_time_ms:.0f}ms)" if response_time_ms else ""
        logger.info(f"API call: {method} {endpoint} - {status_text}{time_text}")


def log_indicator_calculation(
    indicator_name: str,
    parameters: dict,
    result: Union[Optional[float], dict[str, Any]],
    error: Optional[Exception] = None,
) -> None:
    """
    Log an indicator calculation with parameters and result.

    Args:
        indicator_name: Name of the indicator (e.g., "RSI", "MACD").
        parameters: Dictionary of calculation parameters.
        result: Calculated value (if successful). Can be float or dict for multi-value indicators.
        error: Exception if calculation failed.
    """
    logger = logging.getLogger("btc_monitor.indicators")

    params_str = ", ".join(f"{k}={v}" for k, v in parameters.items())

    if error:
        logger.error(
            f"{indicator_name} calculation failed [{params_str}] - "
            f"Error: {type(error).__name__}: {error}",
            exc_info=True
        )
    elif result is not None:
        if isinstance(result, dict):
            # Format dict result
            result_str = ", ".join(f"{k}={v}" for k, v in result.items())
            logger.info(f"{indicator_name} calculated [{params_str}] - Result: {result_str}")
        else:
            logger.info(f"{indicator_name} calculated [{params_str}] - Result: {result}")
    else:
        logger.warning(f"{indicator_name} calculation returned None [{params_str}]")


def log_database_operation(
    operation: str,
    table: str,
    record_id: Optional[int] = None,
    error: Optional[Exception] = None,
) -> None:
    """
    Log a database operation.

    Args:
        operation: Type of operation (INSERT, UPDATE, DELETE, SELECT).
        table: Database table name.
        record_id: ID of the record being operated on (if applicable).
        error: Exception if operation failed.
    """
    logger = logging.getLogger("btc_monitor.database")

    record_text = f" (id={record_id})" if record_id is not None else ""

    if error:
        logger.error(
            f"Database {operation} failed on {table}{record_text} - "
            f"Error: {type(error).__name__}: {error}",
            exc_info=True
        )
    else:
        logger.debug(f"Database {operation} on {table}{record_text}")


class CircuitBreaker:
    """
    Circuit breaker pattern for API calls.

    Prevents cascading failures by stopping calls to a failing service
    after a threshold of failures is reached. After a cooldown period,
    allows a single test request to see if the service has recovered.

    States:
        - CLOSED: Normal operation, requests are allowed
        - OPEN: Service is failing, requests are blocked
        - HALF_OPEN: Testing if service has recovered, single request allowed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit.
            recovery_timeout: Seconds to wait before attempting recovery.
            expected_exception: Exception type that counts as failure.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        # State tracking
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

        self.logger = logging.getLogger("btc_monitor.circuit_breaker")

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Function to call.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Result of the function call.

        Raises:
            CircuitBreakerOpenError: If circuit is open and blocking calls.
            Exception: The exception from the function call if it fails.
        """
        if self.state == "OPEN":
            # Check if we should try recovery
            if self._should_attempt_recovery():
                self.state = "HALF_OPEN"
                self.logger.info(
                    f"Circuit breaker entering HALF_OPEN state to test recovery"
                )
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Blocked call to {func.__name__}. "
                    f"Failures: {self.failure_count}/{self.failure_threshold}"
                )

        try:
            result = func(*args, **kwargs)

            # Success - reset or close the circuit
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                self.logger.info(
                    f"Circuit breaker recovered and returned to CLOSED state"
                )
            elif self.state == "CLOSED":
                self.failure_count = 0

            return result

        except self.expected_exception as e:
            self._on_failure(e)
            raise

    def _should_attempt_recovery(self) -> bool:
        """
        Check if enough time has passed to attempt recovery.

        Returns:
            True if recovery timeout has elapsed.
        """
        if self.last_failure_time is None:
            return True

        import time
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_failure(self, error: Exception) -> None:
        """
        Handle a failure event.

        Args:
            error: The exception that occurred.
        """
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()

        self.logger.warning(
            f"Circuit breaker failure detected: {type(error).__name__}: {error}. "
            f"Failure count: {self.failure_count}/{self.failure_threshold}"
        )

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.logger.error(
                f"Circuit breaker opened after {self.failure_count} failures. "
                f"Will attempt recovery after {self.recovery_timeout} seconds."
            )

    def reset(self) -> None:
        """Reset the circuit breaker to CLOSED state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        self.logger.info("Circuit breaker manually reset to CLOSED state")

    def get_state(self) -> dict:
        """
        Get the current state of the circuit breaker.

        Returns:
            Dictionary with state information.
        """
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open and blocking calls."""

    pass
