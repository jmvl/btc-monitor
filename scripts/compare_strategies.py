"""
Compare 5 trading strategies against the EMA 9/21 baseline.

Strategies:
1. EMA 20/50 - Fewer trades, less whipsaw
2. EMA 9/21 + RSI filter - Only buy when RSI < 50
3. MACD (12/26/9) - Classic momentum
4. Triple EMA - TE 5/13/21
5. EMA 9/21 + ADX filter - Only trade strong trends
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import numpy as np
from btc_monitor.backtest import (
    BacktestConfig, Backtester,
    calc_ema, calc_rsi, detect_crossover, detect_crossunder,
    print_kpis
)
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def load_tv_export(filepath: str) -> pd.DataFrame:
    """Load TradingView CSV export."""
    df = pd.read_csv(filepath)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df.set_index('time')
    df['Open'] = df['open'].astype(float)
    df['High'] = df['high'].astype(float)
    df['Low'] = df['low'].astype(float)
    df['Close'] = df['close'].astype(float)
    return df.iloc[:-1]


def calc_adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Calculate ADX (Average Directional Index)."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement
    up = high - high.shift(1)
    down = low.shift(1) - low
    
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    
    # Smoothed values (using RMA/SMMA)
    def smma(s, l):
        result = s.copy()
        result.iloc[:l] = np.nan
        result.iloc[l-1] = s.iloc[:l].mean()
        for i in range(l, len(s)):
            result.iloc[i] = (result.iloc[i-1] * (l-1) + s.iloc[i]) / l
        return result
    
    atr = smma(tr, length)
    plus_di = 100 * smma(pd.Series(plus_dm), length) / atr
    minus_di = 100 * smma(pd.Series(minus_dm), length) / atr
    
    # DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = smma(dx, length)
    
    return adx


def calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    """Calculate MACD, Signal, and Histogram."""
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ============================================================================
# STRATEGY FUNCTIONS
# ============================================================================

def strategy_ema_9_21(df):
    """Baseline: EMA 9/21 crossover."""
    df = df.copy()
    df['fast'] = calc_ema(df['Close'], 9)
    df['slow'] = calc_ema(df['Close'], 21)
    df['long_entry'] = detect_crossover(df['fast'], df['slow'])
    df['long_exit'] = detect_crossunder(df['fast'], df['slow'])
    return df, "EMA 9/21 (Baseline)"


def strategy_ema_20_50(df):
    """Strategy 1: EMA 20/50 - Fewer trades."""
    df = df.copy()
    df['fast'] = calc_ema(df['Close'], 20)
    df['slow'] = calc_ema(df['Close'], 50)
    df['long_entry'] = detect_crossover(df['fast'], df['slow'])
    df['long_exit'] = detect_crossunder(df['fast'], df['slow'])
    return df, "EMA 20/50"


def strategy_ema_rsi_filter(df):
    """Strategy 2: EMA 9/21 + RSI < 50 filter."""
    df = df.copy()
    df['fast'] = calc_ema(df['Close'], 9)
    df['slow'] = calc_ema(df['Close'], 21)
    df['rsi'] = calc_rsi(df['Close'], 14)
    
    # Entry: EMA cross AND RSI < 50 (not overbought)
    ema_cross = detect_crossover(df['fast'], df['slow'])
    df['long_entry'] = ema_cross & (df['rsi'] < 50)
    
    # Exit: EMA cross under
    df['long_exit'] = detect_crossunder(df['fast'], df['slow'])
    return df, "EMA 9/21 + RSI<50"


def strategy_macd(df):
    """Strategy 3: MACD (12/26/9)."""
    df = df.copy()
    macd_line, signal_line, histogram = calc_macd(df['Close'], 12, 26, 9)
    df['macd'] = macd_line
    df['signal'] = signal_line
    
    # Entry: MACD crosses above signal
    df['long_entry'] = detect_crossover(df['macd'], df['signal'])
    
    # Exit: MACD crosses below signal
    df['long_exit'] = detect_crossunder(df['macd'], df['signal'])
    return df, "MACD (12/26/9)"


def strategy_triple_ema(df):
    """Strategy 4: Triple EMA (5/13/21)."""
    df = df.copy()
    df['ema5'] = calc_ema(df['Close'], 5)
    df['ema13'] = calc_ema(df['Close'], 13)
    df['ema21'] = calc_ema(df['Close'], 21)
    
    # Entry: All EMAs aligned bullish (5 > 13 > 21)
    prev_bullish = (df['ema5'].shift(1) <= df['ema13'].shift(1)) | \
                   (df['ema13'].shift(1) <= df['ema21'].shift(1))
    curr_bullish = (df['ema5'] > df['ema13']) & (df['ema13'] > df['ema21'])
    df['long_entry'] = prev_bullish & curr_bullish
    
    # Exit: EMA 5 crosses below EMA 13
    df['long_exit'] = detect_crossunder(df['ema5'], df['ema13'])
    return df, "Triple EMA (5/13/21)"


def strategy_ema_adx_filter(df):
    """Strategy 5: EMA 9/21 + ADX > 25 (strong trend only)."""
    df = df.copy()
    df['fast'] = calc_ema(df['Close'], 9)
    df['slow'] = calc_ema(df['Close'], 21)
    df['adx'] = calc_adx(df, 14)
    
    # Entry: EMA cross AND ADX > 25 (strong trend)
    ema_cross = detect_crossover(df['fast'], df['slow'])
    df['long_entry'] = ema_cross & (df['adx'] > 25)
    
    # Exit: EMA cross under
    df['long_exit'] = detect_crossunder(df['fast'], df['slow'])
    return df, "EMA 9/21 + ADX>25"


# ============================================================================
# MAIN
# ============================================================================

def run_comparison():
    # Load data
    data_file = Path(__file__).parent.parent / "data" / "INDEX_BTCUSD, 1D.csv"
    df = load_tv_export(str(data_file))
    
    print("=" * 80)
    print("  STRATEGY COMPARISON - BTC/USD 1D (2018-2026)")
    print("=" * 80)
    print(f"  Data: {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}")
    print(f"  Initial Capital: $1,000 | Commission: 0.1%")
    print("=" * 80)
    
    config = BacktestConfig(
        initial_capital=1000.0,
        commission_pct=0.1,
        start_date="2018-01-01",
        end_date="2026-12-31",
    )
    
    strategies = [
        strategy_ema_9_21,      # Baseline
        strategy_ema_20_50,     # 1
        strategy_ema_rsi_filter, # 2
        strategy_macd,          # 3
        strategy_triple_ema,    # 4
        strategy_ema_adx_filter, # 5
    ]
    
    results = []
    
    for strat_func in strategies:
        df_strat, name = strat_func(df)
        
        try:
            backtester = Backtester(config)
            kpis = backtester.run_backtest(df_strat)
            
            results.append({
                'name': name,
                'net_profit': kpis['net_profit'],
                'net_profit_pct': kpis['net_profit_pct'],
                'total_trades': kpis['total_trades'],
                'win_rate': kpis['win_rate'],
                'profit_factor': kpis['profit_factor'],
                'max_dd_pct': kpis['max_drawdown_pct'],
                'sharpe': kpis['sharpe_ratio'],
            })
        except Exception as e:
            print(f"Error with {name}: {e}")
    
    # Display results table
    print("\n" + "=" * 80)
    print("  RESULTS SUMMARY (sorted by Sharpe Ratio)")
    print("=" * 80)
    
    # Sort by Sharpe ratio
    results.sort(key=lambda x: x['sharpe'], reverse=True)
    
    # Print header
    print(f"\n{'Strategy':<25} {'Net Profit':>12} {'Trades':>8} {'Win%':>8} {'PF':>6} {'MaxDD%':>8} {'Sharpe':>8}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['name']:<25} ${r['net_profit']:>9,.0f} {r['total_trades']:>8} {r['win_rate']:>7.1f}% "
              f"{r['profit_factor']:>6.2f} {r['max_dd_pct']:>7.1f}% {r['sharpe']:>8.3f}")
    
    print("\n" + "=" * 80)
    print("  KEY METRICS EXPLANATION")
    print("=" * 80)
    print("  Net Profit: Total profit from closed trades")
    print("  Trades: Number of completed trades (fewer = less fees)")
    print("  Win%: Percentage of profitable trades")
    print("  PF: Profit Factor (gross profit / gross loss, >1.5 is good)")
    print("  MaxDD%: Maximum drawdown percentage (lower = less risk)")
    print("  Sharpe: Risk-adjusted return (higher = better)")
    print("=" * 80)
    
    # Best strategy recommendation
    best = results[0]
    baseline = next((r for r in results if 'Baseline' in r['name']), None)
    
    print("\n" + "=" * 80)
    print("  RECOMMENDATION")
    print("=" * 80)
    print(f"\n  Best strategy: {best['name']}")
    print(f"  Sharpe Ratio: {best['sharpe']:.3f}")
    print(f"  Net Profit: ${best['net_profit']:,.0f} ({best['net_profit_pct']:.1f}%)")
    print(f"  Max Drawdown: {best['max_dd_pct']:.1f}%")
    print(f"  Total Trades: {best['total_trades']}")
    
    if baseline:
        print(f"\n  vs Baseline (EMA 9/21):")
        print(f"    Sharpe improvement: {best['sharpe'] - baseline['sharpe']:+.3f}")
        print(f"    Trade reduction: {baseline['total_trades'] - best['total_trades']:+d}")
        print(f"    MaxDD improvement: {baseline['max_dd_pct'] - best['max_dd_pct']:+.1f}%")
    
    print("=" * 80)


if __name__ == "__main__":
    run_comparison()
