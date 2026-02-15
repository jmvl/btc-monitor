#!/usr/bin/env python3
"""
Run backtest for BTC/USD with simple RSI strategy.
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from btc_monitor.backtest import Backtester, RSIStrategy, generate_pinescript_for_strategy
from btc_monitor.config import load_config
from btc_monitor.database import init_db, get_session
from btc_monitor.indicators import RSI
from btc_monitor.models import PriceData
from sqlalchemy import desc
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_historical_prices(session, days: int = 365):
    """
    Fetch historical price data from database.
    
    Args:
        session: Database session
        days: Number of days of history
        
    Returns:
        Tuple of (timestamps, prices)
    """
    from datetime import timezone
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    prices = (
        session.query(PriceData)
        .filter(PriceData.timestamp >= start_date)
        .filter(PriceData.timestamp <= end_date)
        .order_by(PriceData.timestamp)
        .all()
    )
    
    if not prices:
        logger.error("No price data found in database")
        return [], []
    
    timestamps = [p.timestamp for p in prices]
    close_prices = [p.close for p in prices]
    
    logger.info(f"Fetched {len(prices)} price records from {timestamps[0]} to {timestamps[-1]}")
    
    return timestamps, close_prices


def calculate_rsi(prices: list, period: int = 14) -> list:
    """
    Calculate RSI for price series.
    
    Args:
        prices: List of closing prices
        period: RSI period
        
    Returns:
        List of RSI values (same length as prices, with None for initial values)
    """
    if len(prices) < period + 1:
        return [None] * len(prices)
    
    rsi_values = [None] * period
    
    # Calculate initial average gain/loss
    deltas = [prices[i] - prices[i-1] for i in range(1, period + 1)]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    # Calculate first RSI
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    rsi_values.append(rsi)
    
    # Calculate remaining RSI values using smoothed method
    for i in range(period + 1, len(prices)):
        delta = prices[i] - prices[i-1]
        gain = delta if delta > 0 else 0
        loss = -delta if delta < 0 else 0
        
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        rsi_values.append(rsi)
    
    return rsi_values


def run_backtest():
    """Run the backtest and display results."""
    try:
        # Load config
        config = load_config("config/config.yaml")
        
        # Initialize database
        db_path = config.db_path
        init_db(db_path)
        session = get_session()
        
        logger.info("=" * 60)
        logger.info("BTC/USD Backtest - RSI Strategy")
        logger.info("=" * 60)
        
        # Fetch historical data
        timestamps, prices = fetch_historical_prices(session, days=365)
        
        if not prices:
            logger.error("No price data available. Please fetch historical data first.")
            logger.info("Run: python -m btc_monitor fetch-historical --days 365")
            return
        
        # Calculate RSI
        logger.info("Calculating RSI indicator...")
        rsi_values = calculate_rsi(prices, period=14)
        
        # Create strategy
        strategy = RSIStrategy(rsi_period=14, oversold=30.0, overbought=70.0)
        
        # Run backtest
        logger.info("Running backtest...")
        backtester = Backtester(initial_capital=10000.0, commission=0.001)
        result = backtester.run_backtest(strategy, timestamps, prices, rsi_values)
        
        # Display results
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Strategy: {result.strategy_name}")
        print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
        print(f"Initial Capital: ${result.initial_capital:,.2f}")
        print(f"Final Capital: ${result.final_capital:,.2f}")
        print(f"Total Return: ${result.total_return:,.2f} ({result.total_return_percent:+.2f}%)")
        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {result.num_trades}")
        print(f"  Winning: {result.winning_trades}")
        print(f"  Losing: {result.losing_trades}")
        print(f"  Win Rate: {result.win_rate:.1f}%")
        print(f"\nRisk Metrics:")
        print(f"  Max Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_percent:.2f}%)")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print("=" * 60)
        
        # Generate PineScript
        print("\nGenerating PineScript for TradingView verification...")
        pinescript = generate_pinescript_for_strategy(strategy)
        
        # Save PineScript to file
        pinescript_file = "strategy_rsi.pine"
        with open(pinescript_file, "w") as f:
            f.write(pinescript)
        
        print(f"PineScript saved to: {pinescript_file}")
        print("\n" + "=" * 60)
        print("PINESCRIPT CODE:")
        print("=" * 60)
        print(pinescript)
        print("=" * 60)
        
        print("\n" + "=" * 60)
        print("VERIFICATION STEPS:")
        print("=" * 60)
        print("1. Copy the PineScript code above")
        print("2. Open TradingView (tradingview.com)")
        print("3. Open Pine Editor (bottom panel)")
        print("4. Paste the code and click 'Add to Chart'")
        print("5. Compare the strategy results with the backtest above")
        print("6. Results should match 100% if implemented correctly")
        print("=" * 60)
        
        session.close()
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_backtest()
