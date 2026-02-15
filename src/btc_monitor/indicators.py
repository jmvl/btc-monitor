"""Technical analysis indicators for BTC Monitor."""

import math
from datetime import datetime
from typing import List, Optional, Union

from sqlalchemy.orm import Session

from btc_monitor.logging import log_indicator_calculation, log_database_operation
from btc_monitor.models import PriceData, TechnicalIndicators


class RSI:
    """Relative Strength Index (RSI) indicator calculator."""
    
    def __init__(self, period: int = 14):
        """
        Initialize RSI calculator.
        
        Args:
            period: Lookback period for RSI calculation. Default is 14.
        """
        self.period = period
    
    def calculate(self, prices: List[float]) -> Optional[float]:
        """
        Calculate RSI for the last price in the series.
        
        Args:
            prices: List of closing prices in chronological order (oldest first).
        
        Returns:
            RSI value (0-100) or None if insufficient data.
        
        Note:
            Returns None if there are fewer than period + 1 prices.
        """
        # Handle edge cases
        if not prices:
            return None
        
        # Filter out NaN values
        valid_prices = [p for p in prices if not (isinstance(p, float) and math.isnan(p))]
        
        # Check for sufficient data
        if len(valid_prices) < self.period + 1:
            return None
        
        # Calculate price changes
        changes = []
        for i in range(1, len(valid_prices)):
            change = valid_prices[i] - valid_prices[i - 1]
            changes.append(change)
        
        # Separate gains and losses
        gains = [max(0, change) for change in changes]
        losses = [max(0, -change) for change in changes]
        
        # Calculate initial average gain and loss (using first period values)
        avg_gain = sum(gains[:self.period]) / self.period
        avg_loss = sum(losses[:self.period]) / self.period
        
        # Use Wilder's smoothing for remaining values
        for i in range(self.period, len(changes)):
            avg_gain = ((avg_gain * (self.period - 1)) + gains[i]) / self.period
            avg_loss = ((avg_loss * (self.period - 1)) + losses[i]) / self.period
        
        # Avoid division by zero
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        
        # Calculate Relative Strength
        rs = avg_gain / avg_loss
        
        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))
        
        # Ensure RSI is in valid range (0-100)
        rsi = max(0.0, min(100.0, rsi))
        
        return rsi
    
    def calculate_and_save(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[float]:
        """
        Calculate RSI for a given timestamp and save to database.

        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp for which to calculate RSI.

        Returns:
            RSI value or None if calculation failed.
        """
        try:
            # Fetch price data needed for RSI calculation
            prices = self._fetch_prices(session, timestamp)

            if prices is None:
                log_indicator_calculation(
                    "RSI",
                    {"period": self.period, "timestamp": timestamp},
                    None,
                )
                return None

            # Calculate RSI
            rsi = self.calculate(prices)

            if rsi is None:
                log_indicator_calculation(
                    "RSI",
                    {"period": self.period, "timestamp": timestamp},
                    None,
                )
                return None

            # Save to database
            self._save_indicator(session, timestamp, rsi)

            log_indicator_calculation(
                "RSI",
                {"period": self.period, "timestamp": timestamp},
                rsi,
            )

            return rsi

        except Exception as e:
            log_indicator_calculation(
                "RSI",
                {"period": self.period, "timestamp": timestamp},
                None,
                error=e,
            )
            return None
    
    def _fetch_prices(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[List[float]]:
        """
        Fetch historical prices needed for RSI calculation.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The end timestamp for price data.
        
        Returns:
            List of prices in chronological order or None if insufficient data.
        """
        # Query for price data, ordered by timestamp (ascending)
        query = session.query(PriceData.close).filter(
            PriceData.timestamp <= timestamp
        ).order_by(PriceData.timestamp.asc()).limit(self.period + 1)
        
        results = query.all()
        
        # Extract prices from query results
        prices = [row[0] for row in results]
        
        # Check if we have enough data
        if len(prices) < self.period + 1:
            return None
        
        return prices
    
    def _save_indicator(
        self,
        session: Session,
        timestamp: datetime,
        rsi: float
    ) -> None:
        """
        Save RSI value to TechnicalIndicators table.

        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp for the indicator.
            rsi: RSI value to save.
        """
        try:
            # Check if indicator record exists
            indicator = session.query(TechnicalIndicators).filter(
                TechnicalIndicators.timestamp == timestamp
            ).first()

            operation = "UPDATE" if indicator else "INSERT"

            if indicator is None:
                # Create new indicator record
                indicator = TechnicalIndicators(
                    timestamp=timestamp,
                    rsi=rsi,
                    price_timestamp=timestamp
                )
                session.add(indicator)
            else:
                # Update existing record
                indicator.rsi = rsi

            session.commit()
            log_database_operation(operation, "technical_indicators")

        except Exception as e:
            session.rollback()
            log_database_operation("INSERT" if indicator is None else "UPDATE", "technical_indicators", error=e)
            raise


class MACD:
    """Moving Average Convergence Divergence (MACD) indicator calculator."""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        """
        Initialize MACD calculator.
        
        Args:
            fast: Fast EMA period. Default is 12.
            slow: Slow EMA period. Default is 26.
            signal: Signal line EMA period. Default is 9.
        """
        self.fast = fast
        self.slow = slow
        self.signal = signal
    
    def calculate(
        self,
        prices: List[float]
    ) -> Optional[tuple]:
        """
        Calculate MACD for the last price in the series.
        
        Args:
            prices: List of closing prices in chronological order (oldest first).
        
        Returns:
            Tuple of (macd_line, signal_line, histogram) or None if insufficient data.
        
        Note:
            Returns None if there are fewer than slow + signal prices.
        """
        # Handle edge cases
        if not prices:
            return None
        
        # Filter out NaN values
        valid_prices = [p for p in prices if not (isinstance(p, float) and math.isnan(p))]
        
        # Check for sufficient data (need slow + signal samples)
        min_samples = self.slow + self.signal
        if len(valid_prices) < min_samples:
            return None
        
        # Calculate fast EMA
        fast_ema = self._calculate_ema(valid_prices, self.fast)
        
        # Calculate slow EMA
        slow_ema = self._calculate_ema(valid_prices, self.slow)
        
        # Calculate MACD line (fast EMA - slow EMA)
        macd_line = fast_ema - slow_ema
        
        # Calculate signal line (EMA of MACD line)
        # Need to reconstruct MACD line for entire series to calculate its EMA
        macd_series = []
        for i in range(len(valid_prices)):
            # Calculate EMA values up to this point
            fast_ema_i = self._calculate_ema(valid_prices[:i + 1], self.fast)
            slow_ema_i = self._calculate_ema(valid_prices[:i + 1], self.slow)
            macd_series.append(fast_ema_i - slow_ema_i)
        
        # Calculate signal line as EMA of MACD series
        signal_line = self._calculate_ema(macd_series, self.signal)
        
        # Calculate histogram (MACD line - signal line)
        histogram = macd_line - signal_line
        
        return (macd_line, signal_line, histogram)
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """
        Calculate Exponential Moving Average (EMA).
        
        Args:
            prices: List of prices in chronological order.
            period: EMA period.
        
        Returns:
            EMA value for the last price in the series.
        """
        if not prices:
            return 0.0
        
        if len(prices) < period:
            # Use simple moving average if insufficient data for EMA
            return sum(prices) / len(prices)
        
        # Calculate multiplier
        multiplier = 2.0 / (period + 1)
        
        # Start with SMA for first period values
        sma = sum(prices[:period]) / period
        ema = sma
        
        # Apply EMA formula for remaining values
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_and_save(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[tuple]:
        """
        Calculate MACD for a given timestamp and save to database.

        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp for which to calculate MACD.

        Returns:
            Tuple of (macd_line, signal_line, histogram) or None if calculation failed.
        """
        try:
            # Fetch price data needed for MACD calculation
            prices = self._fetch_prices(session, timestamp)

            if prices is None:
                log_indicator_calculation(
                    "MACD",
                    {"fast": self.fast, "slow": self.slow, "signal": self.signal, "timestamp": timestamp},
                    None,
                )
                return None

            # Calculate MACD
            result = self.calculate(prices)

            if result is None:
                log_indicator_calculation(
                    "MACD",
                    {"fast": self.fast, "slow": self.slow, "signal": self.signal, "timestamp": timestamp},
                    None,
                )
                return None

            macd_line, signal_line, histogram = result

            # Save to database
            self._save_indicator(session, timestamp, macd_line, signal_line, histogram)

            log_indicator_calculation(
                "MACD",
                {"fast": self.fast, "slow": self.slow, "signal": self.signal, "timestamp": timestamp},
                {"macd": macd_line, "signal": signal_line, "histogram": histogram},
            )

            return result

        except Exception as e:
            log_indicator_calculation(
                "MACD",
                {"fast": self.fast, "slow": self.slow, "signal": self.signal, "timestamp": timestamp},
                None,
                error=e,
            )
            return None
    
    def _fetch_prices(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[List[float]]:
        """
        Fetch historical prices needed for MACD calculation.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The end timestamp for price data.
        
        Returns:
            List of prices in chronological order or None if insufficient data.
        """
        # Query for price data, ordered by timestamp (ascending)
        min_samples = self.slow + self.signal
        query = session.query(PriceData.close).filter(
            PriceData.timestamp <= timestamp
        ).order_by(PriceData.timestamp.asc()).limit(min_samples)
        
        results = query.all()
        
        # Extract prices from query results
        prices = [row[0] for row in results]
        
        # Check if we have enough data
        if len(prices) < min_samples:
            return None
        
        return prices
    
    def _save_indicator(
        self,
        session: Session,
        timestamp: datetime,
        macd_line: float,
        signal_line: float,
        histogram: float
    ) -> None:
        """
        Save MACD values to TechnicalIndicators table.

        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp for the indicator.
            macd_line: MACD line value to save.
            signal_line: Signal line value to save.
            histogram: Histogram value to save.
        """
        try:
            # Check if indicator record exists
            indicator = session.query(TechnicalIndicators).filter(
                TechnicalIndicators.timestamp == timestamp
            ).first()

            operation = "UPDATE" if indicator else "INSERT"

            if indicator is None:
                # Create new indicator record
                indicator = TechnicalIndicators(
                    timestamp=timestamp,
                    macd=macd_line,
                    macd_signal=signal_line,
                    macd_hist=histogram,
                    price_timestamp=timestamp
                )
                session.add(indicator)
            else:
                # Update existing record
                indicator.macd = macd_line
                indicator.macd_signal = signal_line
                indicator.macd_hist = histogram

            session.commit()
            log_database_operation(operation, "technical_indicators")

        except Exception as e:
            session.rollback()
            log_database_operation("INSERT" if indicator is None else "UPDATE", "technical_indicators", error=e)
            raise


class MovingAverages:
    """Moving Averages (SMA and EMA) indicator calculator."""
    
    def __init__(self, sma_50_period: int = 50, sma_200_period: int = 200):
        """
        Initialize Moving Averages calculator.
        
        Args:
            sma_50_period: Period for 50-day SMA. Default is 50.
            sma_200_period: Period for 200-day SMA. Default is 200.
        """
        self.sma_50_period = sma_50_period
        self.sma_200_period = sma_200_period
    
    def calculate_sma(self, prices: List[float], period: int) -> Optional[float]:
        """
        Calculate Simple Moving Average (SMA).
        
        Args:
            prices: List of closing prices in chronological order (oldest first).
            period: Period for SMA calculation.
        
        Returns:
            SMA value or None if insufficient data.
        
        Note:
            Returns None if there are fewer than period prices.
        """
        # Handle edge cases
        if not prices:
            return None
        
        # Filter out NaN values
        valid_prices = [p for p in prices if not (isinstance(p, float) and math.isnan(p))]
        
        # Check for sufficient data
        if len(valid_prices) < period:
            return None
        
        # Calculate SMA (average of last 'period' prices)
        # Take the last 'period' prices for the current SMA value
        recent_prices = valid_prices[-period:]
        sma = sum(recent_prices) / period
        
        return sma
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """
        Calculate Exponential Moving Average (EMA).
        
        Args:
            prices: List of closing prices in chronological order (oldest first).
            period: EMA period.
        
        Returns:
            EMA value for the last price in the series or None if insufficient data.
        
        Note:
            Returns None if there are fewer than period prices.
        """
        # Handle edge cases
        if not prices:
            return None
        
        # Filter out NaN values
        valid_prices = [p for p in prices if not (isinstance(p, float) and math.isnan(p))]
        
        # Check for sufficient data
        if len(valid_prices) < period:
            return None
        
        # Calculate multiplier
        multiplier = 2.0 / (period + 1)
        
        # Start with SMA for first period values
        sma = sum(valid_prices[:period]) / period
        ema = sma
        
        # Apply EMA formula for remaining values
        for price in valid_prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_and_save(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[tuple]:
        """
        Calculate SMA 50 and SMA 200 for a given timestamp and save to database.

        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp for which to calculate moving averages.

        Returns:
            Tuple of (sma_50, sma_200) or None if calculation failed.
        """
        try:
            # Fetch price data needed for SMA 200 calculation
            # Need at least 200 samples for SMA 200
            prices = self._fetch_prices(session, timestamp)

            if prices is None:
                log_indicator_calculation(
                    "MovingAverages",
                    {"sma_50": self.sma_50_period, "sma_200": self.sma_200_period, "timestamp": timestamp},
                    None,
                )
                return None

            # Calculate SMA 50
            sma_50 = self.calculate_sma(prices, self.sma_50_period)

            # Calculate SMA 200
            sma_200 = self.calculate_sma(prices, self.sma_200_period)

            # If we can calculate at least SMA 50, save it
            if sma_50 is None:
                log_indicator_calculation(
                    "MovingAverages",
                    {"sma_50": self.sma_50_period, "sma_200": self.sma_200_period, "timestamp": timestamp},
                    None,
                )
                return None

            # Save to database
            self._save_indicator(session, timestamp, sma_50, sma_200)

            log_indicator_calculation(
                "MovingAverages",
                {"sma_50": self.sma_50_period, "sma_200": self.sma_200_period, "timestamp": timestamp},
                {"sma_50": sma_50, "sma_200": sma_200},
            )

            return (sma_50, sma_200)

        except Exception as e:
            log_indicator_calculation(
                "MovingAverages",
                {"sma_50": self.sma_50_period, "sma_200": self.sma_200_period, "timestamp": timestamp},
                None,
                error=e,
            )
            return None
    
    def _fetch_prices(
        self,
        session: Session,
        timestamp: datetime
    ) -> Optional[List[float]]:
        """
        Fetch historical prices needed for SMA calculation.
        
        Args:
            session: SQLAlchemy database session.
            timestamp: The end timestamp for price data.
        
        Returns:
            List of prices in chronological order or None if insufficient data.
        """
        # Query for price data, ordered by timestamp (ascending)
        # Need at least sma_200_period samples
        query = session.query(PriceData.close).filter(
            PriceData.timestamp <= timestamp
        ).order_by(PriceData.timestamp.asc()).limit(self.sma_200_period)
        
        results = query.all()
        
        # Extract prices from query results
        prices = [row[0] for row in results]
        
        # Check if we have enough data for at least SMA 50
        if len(prices) < self.sma_50_period:
            return None
        
        return prices
    
    def _save_indicator(
        self,
        session: Session,
        timestamp: datetime,
        sma_50: Optional[float],
        sma_200: Optional[float]
    ) -> None:
        """
        Save SMA values to TechnicalIndicators table.

        Args:
            session: SQLAlchemy database session.
            timestamp: The timestamp for the indicator.
            sma_50: SMA 50 value to save (can be None).
            sma_200: SMA 200 value to save (can be None).
        """
        try:
            # Check if indicator record exists
            indicator = session.query(TechnicalIndicators).filter(
                TechnicalIndicators.timestamp == timestamp
            ).first()

            operation = "UPDATE" if indicator else "INSERT"

            if indicator is None:
                # Create new indicator record
                indicator = TechnicalIndicators(
                    timestamp=timestamp,
                    sma_50=sma_50,
                    sma_200=sma_200,
                    price_timestamp=timestamp
                )
                session.add(indicator)
            else:
                # Update existing record
                indicator.sma_50 = sma_50
                indicator.sma_200 = sma_200

            session.commit()
            log_database_operation(operation, "technical_indicators")

        except Exception as e:
            session.rollback()
            log_database_operation("INSERT" if indicator is None else "UPDATE", "technical_indicators", error=e)
            raise
