"""Price data fetcher for BTC/USD using CoinMarketCap API."""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, List, Optional, Union
import requests

from btc_monitor.database import get_session
from btc_monitor.logging import CircuitBreaker, CircuitBreakerOpenError, log_api_call
from btc_monitor.models import PriceData


logger = logging.getLogger(__name__)


class CoinMarketCapFetcher:
    """Fetches BTC/USD price data from CoinMarketCap API."""

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        db_path: Optional[Union[str, Path]] = None,
        use_circuit_breaker: bool = True,
    ):
        """
        Initialize CoinMarketCapFetcher.

        Args:
            api_key: CoinMarketCap API key.
            max_retries: Maximum number of retry attempts for API calls.
            initial_backoff: Initial backoff time in seconds for exponential backoff.
            max_backoff: Maximum backoff time in seconds.
            db_path: Path to database file. If None, uses default.
            use_circuit_breaker: Whether to use circuit breaker pattern for API calls.
        """
        self.api_key = api_key
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.db_path = db_path
        self.base_url = "https://pro-api.coinmarketcap.com/v1"

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
            *args: Positional arguments for function.
            **kwargs: Keyword arguments for function.

        Returns:
            Result of function, or None if all retries fail.
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

    def _make_request(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict[str, Any]]:
        """
        Make an authenticated request to CoinMarketCap API.

        Args:
            endpoint: API endpoint path (e.g., '/cryptocurrency/listings/latest').
            params: Query parameters.

        Returns:
            Response JSON as dict, or None if all retries fail.
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": self.api_key,
        }
        start_time = time.time()

        def _request() -> dict[str, Any]:
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30,
                )

                response_time_ms = (time.time() - start_time) * 1000
                log_api_call(
                    endpoint=f"CoinMarketCap {endpoint}",
                    method="GET",
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                )

                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result

            except Exception as e:
                response_time_ms = (time.time() - start_time) * 1000
                log_api_call(
                    endpoint=f"CoinMarketCap {endpoint}",
                    method="GET",
                    response_time_ms=response_time_ms,
                    error=e,
                )
                raise

        try:
            if self.use_circuit_breaker and self.circuit_breaker:
                result = self.circuit_breaker.call(_request)
            else:
                result = self._retry_with_backoff(_request)

            return result  # type: ignore[no-any-return]

        except CircuitBreakerOpenError as e:
            logger.error(f"Circuit breaker is blocking API calls: {e}")
            return None

    def get_current_price(self) -> Optional[dict[str, Any]]:
        """
        Get current BTC/USD price with OHLCV data.

        Returns:
            Dictionary with OHLCV data (open, high, low, close, volume), or None if fetch fails.

        Raises:
            ValueError: If price is out of valid range.
            CircuitBreakerOpenError: If circuit breaker is blocking calls.
        """
        def _fetch() -> dict[str, Any]:
            start_time = time.time()
            # Use quotes/latest endpoint for current OHLCV data
            data = self._make_request(
                "/cryptocurrency/quotes/latest",
                params={
                    "slug": "bitcoin",
                    "convert": "USD",
                    "include": "24hr",  # Get 24h OHLCV data
                },
            )

            if data is None:
                raise Exception("No data returned from CoinMarketCap API")

            # Extract OHLCV data from response
            # Response format: {"data": [{"symbol": "BTC", "quote": {"USD": {"price": ..., "high_24h": ..., "low_24h": ..., "volume_24h": ...}}]}
            if "data" not in data or not data["data"]:
                raise Exception("Unexpected response format from CoinMarketCap API")

            btc_data = data["data"][0]
            if "quote" not in btc_data:
                raise Exception("No quote data in response")

            quote = btc_data["quote"]
            if "USD" not in quote:
                raise Exception("No USD price in quote")

            # Extract OHLCV fields
            price = float(quote["USD"].get("price", 0))
            high = float(quote["USD"].get("high_24h", price))
            low = float(quote["USD"].get("low_24h", price))
            volume = float(quote["USD"].get("volume_24h", 0))

            # Validate price is in reasonable range
            if not (0 < price < 1_000_000):
                raise ValueError(f"Price {price} is out of valid range (0, 1,000,000)")

            # Log successful API call
            response_time_ms = (time.time() - start_time) * 1000
            log_api_call(
                endpoint="BTC-USD (CoinMarketCap)",
                method="GET",
                status_code=200,
                response_time_ms=response_time_ms,
            )

            # Return OHLCV data as dict
            return {
                "open": price,
                "high": high,
                "low": low,
                "close": price,  # Use price as close
                "volume": volume,
            }

        try:
            result = self._retry_with_backoff(_fetch)

            if result is None:
                logger.error("Failed to fetch current price after all retries")
                return None

            price: dict[str, Any] = result
            logger.info(f"Current BTC/USD price: ${price['close']:,.2f}")
            return price

        except CircuitBreakerOpenError as e:
            logger.error(f"Circuit breaker is blocking API calls: {e}")
            return None

    def get_historical_data(
        self,
        start_date: Union[datetime, str],
        end_date: Union[datetime, str],
    ) -> List[PriceData]:
        """
        Get historical BTC/USD price data for a date range.

        Args:
            start_date: Start date (datetime or string in YYYY-MM-DD format).
            end_date: End date (datetime or string in YYYY-MM-DD format).

        Returns:
            List of PriceData objects.
        """
        def _fetch() -> dict[str, Any]:
            # Use tools/price-converter endpoint for historical data
            # Note: This requires a different endpoint than current price
            data = self._make_request(
                "/tools/price-conversions",
                params={
                    "amount": 1,
                    "symbol": "BTC",
                    "time": "start_date.isoformat() if isinstance(start_date, datetime) else start_date",
                    "convert": "USD",
                },
            )

            if data is None:
                raise Exception("No data returned from CoinMarketCap API")

            # Extract price from response
            # Response format varies based on endpoint
            price = float(data.get("data", {}).get("quote", {}).get("USD", {}).get("price", 0))

            if price == 0:
                raise Exception("No price data in response")

            # Convert to PriceData format
            if isinstance(start_date, datetime):
                ts = start_date
            else:
                ts = datetime.fromisoformat(start_date)

            price_data = PriceData(timestamp=ts, close=price, volume=None)  # type: ignore[call-arg]

            return [price_data]  # type: ignore[return-value]

        try:
            if self.use_circuit_breaker and self.circuit_breaker:
                records_raw = self.circuit_breaker.call(_fetch)
                records_list = records_raw if isinstance(records_raw, list) else []
            else:
                records_raw = self._retry_with_backoff(_fetch)
                records_list = records_raw if isinstance(records_raw, list) else []

            if not records_list:
                logger.error("Failed to fetch historical data after all retries")
                return []

            logger.info(f"Fetched {len(records_list)} historical price records")
            return records_list

        except CircuitBreakerOpenError as e:
            logger.error(f"Circuit breaker is blocking API calls: {e}")
            return []

    def save_to_database(self, price_data: dict[str, Any]) -> bool:
        """
        Save a single price data record with OHLCV data to database.

        Args:
            price_data: Dictionary with OHLCV data (open, high, low, close, volume).

        Returns:
            True if save was successful, False otherwise.
        """
        from btc_monitor.logging import log_database_operation

        try:
            session = get_session(self.db_path if self.db_path is not None else "")
            try:
                # Check if record already exists (upsert logic)
                existing = session.query(PriceData).filter(
                    PriceData.timestamp == price_data["timestamp"]
                ).first()

                operation = "UPDATE" if existing else "INSERT"

                if existing:
                    # Update existing record with OHLCV data
                    existing.open_price = price_data.get("open")
                    existing.high = price_data.get("high")
                    existing.low = price_data.get("low")
                    if price_data.get("close") is not None:
                        existing.close = price_data["close"]
                    existing.volume = price_data.get("volume")
                else:
                    # Insert new record with OHLCV data
                    record = PriceData(  # type: ignore[call-arg]
                        timestamp=price_data["timestamp"],
                        open_price=price_data.get("open"),
                        high=price_data.get("high"),
                        low=price_data.get("low"),
                        close=price_data.get("close"),
                        volume=price_data.get("volume"),
                    )
                    session.add(record)

                session.commit()
                log_database_operation(operation, "price_data")
                logger.debug(f"Saved OHLCV price data for {price_data['timestamp']}")
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

    def fetch_and_save_current_price(self) -> Optional[dict[str, Any]]:
        """
        Fetch current price with OHLCV data and save it to database.
        
        Returns:
            Dictionary with OHLCV data (open, high, low, close, volume), or None if successful.
        """
        price_dict = self.get_current_price()
        if price_dict is None:
            return None
        
        # Create PriceData with current timestamp and OHLCV data
        price_data = {
            "timestamp": datetime.utcnow(),
            "open": price_dict.get("open"),
            "high": price_dict.get("high"),
            "low": price_dict.get("low"),
            "close": price_dict.get("close"),
            "volume": price_dict.get("volume"),
        }
        
        if self.save_to_database(price_data):
            return price_dict
        
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
            rec_dict: dict[str, Any] = {
                "timestamp": record.timestamp,
                "open": record.open_price,
                "high": record.high,
                "low": record.low,
                "close": record.close,
                "volume": record.volume,
            }
            if self.save_to_database(rec_dict):
                saved_count += 1

        logger.info(f"Saved {saved_count}/{len(price_records)} price records to database")
        return saved_count

    def get_health(self) -> dict[str, Any]:
        """
        Get health status of the CoinMarketCap fetcher.

        Returns:
            Dictionary with health information.
        """
        health: dict[str, Any] = {
            "component": "coinmarketcap_fetcher",
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
