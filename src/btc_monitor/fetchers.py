"""Price data fetcher for BTC/USD using yfinance."""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, List, Optional, Union

import yfinance as yf

from btc_monitor.database import get_session
from btc_monitor.logging import CircuitBreaker, CircuitBreakerOpenError, log_api_call
from btc_monitor.models import PriceData


logger = logging.getLogger(__name__)


class PriceFetcher:
    """Fetches BTC/USD price data from yfinance and stores it in the database."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        db_path: Optional[Union[str, "Path"]] = None,
        use_circuit_breaker: bool = True,
    ):
        """
        Initialize the PriceFetcher.

        Args:
            max_retries: Maximum number of retry attempts for API calls.
            initial_backoff: Initial backoff time in seconds for exponential backoff.
            max_backoff: Maximum backoff time in seconds.
            db_path: Path to the database file. If None, uses default.
            use_circuit_breaker: Whether to use circuit breaker pattern for API calls.
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.db_path = db_path
        self.ticker = yf.Ticker("BTC-USD")

        # Initialize circuit breaker
        self.use_circuit_breaker = use_circuit_breaker
        if use_circuit_breaker:
            self.circuit_breaker: Optional[CircuitBreaker] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60.0,
                expected_exception=Exception,
            )
        else:
            self.circuit_breaker = None
    
    def _retry_with_backoff(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Optional[Any]:
        """
        Execute a function with exponential backoff retry logic.

        Args:
            func: Function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Result of the function, or None if all retries fail.
        """
        backoff = self.initial_backoff
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"All {self.max_retries} retries failed. Last error: {e}"
                    )
                    return None
                
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                    f"Retrying in {backoff:.2f}s..."
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)
        
        return None
    
    def get_current_price(self) -> Optional[float]:
        """
        Get the current BTC/USD price.

        Returns:
            Current BTC/USD price as float, or None if fetch fails.

        Raises:
            ValueError: If price is out of valid range.
            CircuitBreakerOpenError: If circuit breaker is blocking calls.
        """
        def _fetch():
            start_time = time.time()
            try:
                ticker = yf.Ticker("BTC-USD")
                # Using history with period='1d' to get the most recent price
                hist = ticker.history(period="1d", interval="1m")

                if hist.empty:
                    raise ValueError("No price data returned from yfinance")

                # Get the most recent price (last row)
                current_price = float(hist["Close"].iloc[-1])

                # Validate price is in reasonable range
                if not (0 < current_price < 1_000_000):
                    raise ValueError(f"Price {current_price} is out of valid range (0, 1,000,000)")

                # Log successful API call
                response_time_ms = (time.time() - start_time) * 1000
                log_api_call(
                    endpoint="BTC-USD (yfinance)",
                    method="GET",
                    status_code=200,
                    response_time_ms=response_time_ms,
                )

                return current_price

            except Exception as e:
                # Log failed API call
                response_time_ms = (time.time() - start_time) * 1000
                log_api_call(
                    endpoint="BTC-USD (yfinance)",
                    method="GET",
                    response_time_ms=response_time_ms,
                    error=e,
                )
                raise

        try:
            if self.use_circuit_breaker and self.circuit_breaker:
                price = self.circuit_breaker.call(_fetch)
            else:
                price = self._retry_with_backoff(_fetch)

            if price is None:
                logger.error("Failed to fetch current price after all retries")
                return None

            logger.info(f"Current BTC/USD price: ${price:,.2f}")
            return price

        except CircuitBreakerOpenError as e:
            logger.error(f"Circuit breaker is blocking API calls: {e}")
            return None
    
    def get_historical_data(
        self,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
    ) -> List[PriceData]:  # type: ignore[override]
        """
        Get historical BTC/USD price data for a date range.

        Args:
            start_date: Start date (datetime or string in YYYY-MM-DD format).
            end_date: End date (datetime or string in YYYY-MM-DD format).

        Returns:
            List of PriceData objects.
        """
        def _fetch():
            start_time = time.time()
            try:
                ticker = yf.Ticker("BTC-USD")
                hist = ticker.history(start=start_date, end=end_date, interval="1d")

                if hist.empty:
                    raise ValueError(f"No historical data returned for range {start_date} to {end_date}")

                # Log successful API call
                response_time_ms = (time.time() - start_time) * 1000
                log_api_call(
                    endpoint=f"BTC-USD historical (yfinance)",
                    method="GET",
                    status_code=200,
                    response_time_ms=response_time_ms,
                )

                return hist

            except Exception as e:
                # Log failed API call
                response_time_ms = (time.time() - start_time) * 1000
                log_api_call(
                    endpoint=f"BTC-USD historical (yfinance)",
                    method="GET",
                    response_time_ms=response_time_ms,
                    error=e,
                )
                raise

        try:
            if self.use_circuit_breaker and self.circuit_breaker:
                hist = self.circuit_breaker.call(_fetch)
            else:
                hist = self._retry_with_backoff(_fetch)

            if hist is None:
                logger.error("Failed to fetch historical data after all retries")
                return []

            # Convert to list of PriceData objects
            price_records = []
            for timestamp, row in hist.iterrows():
                # yfinance returns timestamp as tz-aware UTC
                # Convert to datetime if it's a pandas Timestamp
                if hasattr(timestamp, "to_pydatetime"):
                    ts = timestamp.to_pydatetime()
                else:
                    ts = timestamp

                price = float(row["Close"])
                volume = float(row["Volume"]) if "Volume" in row and not None else None

                price_data = PriceData(
                    timestamp=ts,
                    close=price,
                    volume=volume,
                )
                price_records.append(price_data)

            logger.info(f"Fetched {len(price_records)} historical price records")
            return price_records

        except CircuitBreakerOpenError as e:
            logger.error(f"Circuit breaker is blocking API calls: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return []
    
    def save_to_database(self, price_data: PriceData) -> bool:
        """
        Save a single price data record to the database.

        Args:
            price_data: PriceData object to save.

        Returns:
            True if save was successful, False otherwise.
        """
        from btc_monitor.logging import log_database_operation

        try:
            session = get_session(self.db_path)
            try:
                # Check if record already exists (upsert logic)
                existing = session.query(PriceData).filter(
                    PriceData.timestamp == price_data.timestamp
                ).first()

                operation = "UPDATE" if existing else "INSERT"

                if existing:
                    # Update existing record
                    existing.close = price_data.close
                    existing.volume = price_data.volume
                else:
                    # Insert new record
                    session.add(price_data)

                session.commit()
                log_database_operation(operation, "price_data")
                logger.debug(f"Saved price data for {price_data.timestamp}")
                return True
            except Exception as e:
                session.rollback()
                operation = "UPDATE" if existing else "INSERT"
                log_database_operation(operation, "price_data", error=e)
                logger.error(f"Failed to save price data: {e}")
                return False
            finally:
                session.close()
        except Exception as e:
            log_database_operation("INSERT", "price_data", error=e)
            logger.error(f"Failed to get database session: {e}")
            return False
    
    def fetch_and_save_current_price(self) -> Optional[float]:
        """
        Fetch current price and save it to the database.
        
        Returns:
            Current price if successful, None otherwise.
        """
        price = self.get_current_price()
        if price is None:
            return None
        
        # Create PriceData with current timestamp
        now = datetime.utcnow()
        price_data = PriceData(timestamp=now, close=price, volume=None)
        
        if self.save_to_database(price_data):
            return price
        
        return None
    
    def fetch_and_save_historical_data(
        self,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
    ) -> int:
        """
        Fetch historical data and save it to the database.
        
        Args:
            start_date: Start date (datetime or string in YYYY-MM-DD format).
            end_date: End date (datetime or string in YYYY-MM-DD format).
        
        Returns:
            Number of records saved, or -1 if fetch failed.
        """
        price_records = self.get_historical_data(start_date, end_date)
        if not price_records:
            return -1
        
        saved_count = 0
        for record in price_records:
            if self.save_to_database(record):
                saved_count += 1
        
        logger.info(f"Saved {saved_count}/{len(price_records)} price records to database")
        return saved_count

    def get_health(self) -> dict:
        """
        Get health status of the price fetcher.

        Returns:
            Dictionary with health information.
        """
        health = {
            "component": "price_fetcher",
            "status": "healthy",
            "circuit_breaker": None,
        }

        if self.use_circuit_breaker and self.circuit_breaker:
            circuit_state = self.circuit_breaker.get_state()
            health["circuit_breaker"] = circuit_state

            if circuit_state["state"] == "OPEN":
                health["status"] = "degraded"
            elif circuit_state["state"] == "HALF_OPEN":
                health["status"] = "recovering"

        return health
