"""
Run backtest using TradingView CSV export for exact match.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from btc_monitor.backtest import (
    BacktestConfig, Backtester, RSIStrategy,
    print_kpis, print_trades
)
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_tv_export(filepath: str) -> pd.DataFrame:
    """
    Load TradingView CSV export.
    
    TV export format: time, open, high, low, close
    Time is Unix timestamp in seconds.
    """
    df = pd.read_csv(filepath)
    
    # Convert time column
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    
    # Ensure float type
    df['Open'] = df['open'].astype(float)
    df['High'] = df['high'].astype(float)
    df['Low'] = df['low'].astype(float)
    df['Close'] = df['close'].astype(float)
    
    # Drop the last bar (unfinished candle)
    df = df.iloc[:-1]
    
    logger.info(f"Loaded TV export: {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}")
    
    return df


def run_backtest():
    """Run backtest with TradingView data."""
    
    # Load TradingView export
    data_file = Path(__file__).parent.parent / "data" / "INDEX_BTCUSD, 1D.csv"
    
    if not data_file.exists():
        logger.error(f"Data file not found: {data_file}")
        logger.info("Please export BTCUSD 1D data from TradingView:")
        logger.info("1. Open BTCUSD chart on TradingView")
        logger.info("2. Click 'Export chart data' (download icon)")
        logger.info("3. Save to: data/INDEX_BTCUSD, 1D.csv")
        return
    
    df = load_tv_export(str(data_file))
    
    # Create EMA strategy (same as reference)
    from btc_monitor.backtest import calc_ema, detect_crossover, detect_crossunder
    
    df['fast_ema'] = calc_ema(df['Close'], 9)
    df['slow_ema'] = calc_ema(df['Close'], 21)
    df['long_entry'] = detect_crossover(df['fast_ema'], df['slow_ema'])
    df['long_exit'] = detect_crossunder(df['fast_ema'], df['slow_ema'])
    
    # Configure (matching reference)
    config = BacktestConfig(
        initial_capital=1000.0,
        commission_pct=0.1,
        slippage_ticks=0,
        qty_type="percent_of_equity",
        qty_value=100.0,
        pyramiding=1,
        start_date="2018-01-01",
        end_date="2069-12-31",
    )
    
    # Run
    logger.info("Running backtest...")
    backtester = Backtester(config)
    kpis = backtester.run_backtest(df)
    
    # Display
    print("\n" + "=" * 60)
    print("  BACKTEST CONFIGURATION")
    print("=" * 60)
    print(f"  Chart Data:       INDEX:BTCUSD 1D (TradingView export)")
    print(f"  Date Range:       {kpis['actual_start_date']} to {kpis['actual_end_date']}")
    print(f"  Initial Capital:  ${config.initial_capital:,.0f}")
    print(f"  Commission:       {config.commission_pct}%")
    print(f"  Strategy:         EMA Crossover (9/21)")
    print("=" * 60)
    
    print_kpis(kpis)
    print_trades(kpis['trades'], max_trades=10)


if __name__ == "__main__":
    run_backtest()
