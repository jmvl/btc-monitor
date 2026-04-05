#!/usr/bin/env python3
"""
Run backtest for BTC/USD with RSI strategy.
Matches TradingView's Strategy Tester behavior.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

from btc_monitor.backtest import (
    BacktestConfig, Backtester, RSIStrategy,
    print_kpis, print_trades
)
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_btc_data(days: int = 365) -> pd.DataFrame:
    """
    Fetch BTC-USD historical data from yfinance.
    
    Note: yfinance OHLC may differ slightly from TradingView's INDEX:BTCUSD.
    For exact match, export CSV from TradingView and use load_tv_export().
    """
    logger.info(f"Fetching {days} days of BTC-USD data from yfinance...")
    
    ticker = yf.Ticker('BTC-USD')
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    df = ticker.history(start=start_date, end=end_date, interval='1d')
    
    # Ensure proper column names (yfinance uses Title case)
    df = df.rename(columns={
        'Open': 'Open',
        'High': 'High', 
        'Low': 'Low',
        'Close': 'Close'
    })
    
    logger.info(f"Fetched {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}")
    
    return df


def run_backtest():
    """Run the backtest and display results."""
    logger.info("=" * 60)
    logger.info("BTC/USD Backtest - RSI Strategy")
    logger.info("=" * 60)
    
    # Fetch data
    df = fetch_btc_data(days=365)
    
    # Create strategy
    strategy = RSIStrategy(rsi_period=14, oversold=30.0, overbought=70.0)
    
    # Generate signals (adds long_entry, long_exit columns)
    df = strategy.generate_signals(df)
    
    # Configure backtest to match TradingView settings
    config = BacktestConfig(
        initial_capital=10000.0,
        commission_pct=0.1,  # 0.1% = matches TradingView default
        slippage_ticks=0,
        qty_type="percent_of_equity",
        qty_value=100.0,
        pyramiding=1,
        start_date="2025-01-01",
        end_date="2026-12-31",
    )
    
    # Run backtest
    logger.info("Running backtest...")
    backtester = Backtester(config)
    kpis = backtester.run_backtest(df)
    
    # Display results
    print("\n" + "=" * 60)
    print("  BACKTEST CONFIGURATION")
    print("=" * 60)
    print(f"  Chart Data:       BTC-USD (yfinance)")
    print(f"  Date Range:       {kpis['actual_start_date']} to {kpis['actual_end_date']}")
    print(f"  Initial Capital:  ${config.initial_capital:,.0f}")
    print(f"  Order Size:       {config.qty_value:.0f}% of equity")
    print(f"  Commission:       {config.commission_pct}%")
    print(f"  Slippage:         0 (matching TradingView)")
    print(f"  Strategy:         {strategy.name}")
    print("=" * 60)
    
    print_kpis(kpis)
    
    if kpis.get('trades'):
        print_trades(kpis['trades'], max_trades=10)
    
    # Generate PineScript
    print("\n" + "=" * 60)
    print("  TRADINGVIEW VERIFICATION")
    print("=" * 60)
    
    pinescript = strategy.to_pinescript()
    
    # Save PineScript
    pinescript_file = Path(__file__).parent.parent / "strategy_rsi.pine"
    with open(pinescript_file, "w") as f:
        f.write(pinescript)
    
    print(f"PineScript saved to: {pinescript_file}")
    print()
    print("To verify results match TradingView:")
    print("1. Open TradingView (tradingview.com)")
    print("2. Open BTC/USD chart (1D timeframe)")
    print("3. Open Pine Editor (bottom panel)")
    print("4. Paste the PineScript code")
    print("5. Click 'Add to Chart'")
    print("6. Compare Strategy Tester results with this output")
    print()
    print("IMPORTANT TradingView settings:")
    print("- Margin Long: 0%")
    print("- Margin Short: 0%")
    print("- Commission: 0.1%")
    print("- Slippage: 0")
    print("=" * 60)
    
    # Print PineScript
    print("\n" + "=" * 60)
    print("  PINESCRIPT CODE")
    print("=" * 60)
    print(pinescript)


if __name__ == "__main__":
    run_backtest()
