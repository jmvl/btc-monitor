"""Technical analysis indicators for BTC Monitor."""

import math
from datetime import datetime
from typing import List, Optional, Union

from sqlalchemy.orm import Session

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
        # Fetch price data needed for RSI calculation
        prices = self._fetch_prices(session, timestamp)
        
        if prices is None:
            return None
        
        # Calculate RSI
        rsi = self.calculate(prices)
        
        if rsi is None:
            return None
        
        # Save to database
        self._save_indicator(session, timestamp, rsi)
        
        return rsi
    
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
        query = session.query(PriceData.price).filter(
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
        # Check if indicator record exists
        indicator = session.query(TechnicalIndicators).filter(
            TechnicalIndicators.timestamp == timestamp
        ).first()
        
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
