"""
Compare 6 trading strategies for BTC 2020-2026.

Strategies inspired by research on profitable crypto trading approaches:
1. EMA 50/200 "Golden Cross" - Classic trend following
2. RSI Mean Reversion - Buy oversold, sell overbought
3. MACD Histogram Reversal - Momentum shifts
4. Bollinger Band Squeeze - Volatility breakout
5. Supertrend - Popular crypto indicator
6. Dual MA with Trend Filter - Only trade with long-term trend

Based on research from:
- TradingView most popular strategies
- Crypto trading forums (Reddit r/algotrading)
- QuantConnect strategy library
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import numpy as np
from btc_monitor.backtest import (
    BacktestConfig, Backtester,
    calc_ema, calc_rsi, detect_crossover, detect_crossunder
)
import logging

logging.basicConfig(level=logging.WARNING)
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


def calc_sma(series: pd.Series, length: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=length).mean()


def calc_bollinger_bands(close: pd.Series, length: int = 20, mult: float = 2.0):
    """Calculate Bollinger Bands."""
    basis = calc_sma(close, length)
    dev = close.rolling(window=length).std()
    upper = basis + mult * dev
    lower = basis - mult * dev
    return upper, basis, lower


def calc_supertrend(df: pd.DataFrame, atr_period: int = 10, multiplier: float = 3.0):
    """
    Calculate Supertrend indicator.
    Popular in crypto trading for trend detection.
    """
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # Calculate ATR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean()
    
    # Supertrend calculation
    hl2 = (high + low) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    supertrend = pd.Series(0.0, index=close.index)
    direction = pd.Series(1, index=close.index)
    
    for i in range(1, len(close)):
        if close.iloc[i] > upper_band.iloc[i-1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower_band.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
        
        if direction.iloc[i] == 1:
            supertrend.iloc[i] = lower_band.iloc[i]
        else:
            supertrend.iloc[i] = upper_band.iloc[i]
    
    return supertrend, direction


# ============================================================================
# STRATEGY FUNCTIONS
# ============================================================================

def strategy_ema_50_200(df):
    """
    Strategy 1: EMA 50/200 "Golden Cross"
    
    Classic long-term trend following.
    Golden Cross = 50 crosses above 200 (buy)
    Death Cross = 50 crosses below 200 (sell)
    """
    df = df.copy()
    df['ema50'] = calc_ema(df['Close'], 50)
    df['ema200'] = calc_ema(df['Close'], 200)
    
    df['long_entry'] = detect_crossover(df['ema50'], df['ema200'])
    df['long_exit'] = detect_crossunder(df['ema50'], df['ema200'])
    
    return df, "EMA 50/200 Golden Cross"


def strategy_rsi_mean_reversion(df):
    """
    Strategy 2: RSI Mean Reversion
    
    Buy when RSI < 30 (oversold)
    Sell when RSI > 70 (overbought)
    
    Popular for ranging/sideways markets.
    """
    df = df.copy()
    df['rsi'] = calc_rsi(df['Close'], 14)
    
    # Entry: RSI crosses below 30 (oversold)
    df['long_entry'] = detect_crossunder(df['rsi'], pd.Series(30, index=df.index))
    
    # Exit: RSI crosses above 70 (overbought)
    df['long_exit'] = detect_crossover(df['rsi'], pd.Series(70, index=df.index))
    
    return df, "RSI Mean Reversion (30/70)"


def strategy_macd_histogram(df):
    """
    Strategy 3: MACD Histogram Reversal
    
    Enter when histogram crosses above zero (momentum shift up)
    Exit when histogram crosses below zero (momentum shift down)
    
    Based on momentum divergence principles.
    """
    df = df.copy()
    
    # MACD calculation
    ema12 = calc_ema(df['Close'], 12)
    ema26 = calc_ema(df['Close'], 26)
    macd_line = ema12 - ema26
    signal_line = calc_ema(macd_line, 9)
    histogram = macd_line - signal_line
    
    df['histogram'] = histogram
    
    # Entry: histogram crosses above zero
    df['long_entry'] = detect_crossover(histogram, pd.Series(0, index=df.index))
    
    # Exit: histogram crosses below zero
    df['long_exit'] = detect_crossunder(histogram, pd.Series(0, index=df.index))
    
    return df, "MACD Histogram Reversal"


def strategy_bollinger_squeeze(df):
    """
    Strategy 4: Bollinger Band Squeeze
    
    Entry: Price breaks above upper band after a squeeze
    Exit: Price breaks below lower band
    
    Based on volatility contraction/expansion cycles.
    """
    df = df.copy()
    
    upper, basis, lower = calc_bollinger_bands(df['Close'], 20, 2.0)
    
    df['upper'] = upper
    df['lower'] = lower
    
    # Entry: Close crosses above upper band
    df['long_entry'] = detect_crossover(df['Close'], upper)
    
    # Exit: Close crosses below lower band
    df['long_exit'] = detect_crossunder(df['Close'], lower)
    
    return df, "Bollinger Band Breakout"


def strategy_supertrend(df):
    """
    Strategy 5: Supertrend
    
    Very popular indicator in crypto trading community.
    Uses ATR to determine trend direction and support/resistance.
    
    Entry: Supertrend turns bullish (green)
    Exit: Supertrend turns bearish (red)
    """
    df = df.copy()
    
    supertrend, direction = calc_supertrend(df, atr_period=10, multiplier=3.0)
    
    df['direction'] = direction
    
    # Entry: Direction changes from -1 to 1
    df['long_entry'] = (direction.shift(1) == -1) & (direction == 1)
    
    # Exit: Direction changes from 1 to -1
    df['long_exit'] = (direction.shift(1) == 1) & (direction == -1)
    
    return df, "Supertrend (10, 3.0)"


def strategy_dual_ma_trend_filter(df):
    """
    Strategy 6: Dual MA with Trend Filter
    
    Use fast EMA (9) / slow EMA (21) for signals,
    but only take long trades when price > EMA 200 (uptrend).
    
    Filters out trades against the long-term trend.
    """
    df = df.copy()
    
    df['ema9'] = calc_ema(df['Close'], 9)
    df['ema21'] = calc_ema(df['Close'], 21)
    df['ema200'] = calc_ema(df['Close'], 200)
    
    # Basic crossover signals
    crossover = detect_crossover(df['ema9'], df['ema21'])
    crossunder = detect_crossunder(df['ema9'], df['ema21'])
    
    # Trend filter: only trade when price > EMA 200
    uptrend = df['Close'] > df['ema200']
    
    # Entry: crossover AND uptrend
    df['long_entry'] = crossover & uptrend
    
    # Exit: crossunder
    df['long_exit'] = crossunder
    
    return df, "EMA 9/21 + 200 Trend Filter"


# ============================================================================
# MAIN
# ============================================================================

def run_comparison():
    # Load data
    data_file = Path(__file__).parent.parent / "data" / "INDEX_BTCUSD, 1D.csv"
    df = load_tv_export(str(data_file))
    
    # Filter 2020-2026
    df = df[(df.index >= '2020-01-01') & (df.index <= '2026-01-31')].copy()
    
    print("=" * 80)
    print("  BTC TRADING STRATEGY COMPARISON (2020-2026)")
    print("=" * 80)
    print(f"  Period: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"  Bars: {len(df)}")
    print(f"  Initial Capital: $1,000 | Commission: 0.1%")
    print("=" * 80)
    
    # Price movement
    start_price = df['Close'].iloc[0]
    end_price = df['Close'].iloc[-1]
    price_return = ((end_price - start_price) / start_price) * 100
    
    print(f"\n  BTC Price Movement:")
    print(f"    Start: ${start_price:,.2f}")
    print(f"    End: ${end_price:,.2f}")
    print(f"    HODL Return: {price_return:+.1f}%")
    print("=" * 80)
    
    config = BacktestConfig(
        initial_capital=1000.0,
        commission_pct=0.1,
        start_date="2020-01-01",
        end_date="2026-01-31",
    )
    
    strategies = [
        strategy_ema_50_200,
        strategy_rsi_mean_reversion,
        strategy_macd_histogram,
        strategy_bollinger_squeeze,
        strategy_supertrend,
        strategy_dual_ma_trend_filter,
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
                'avg_trade_pct': kpis['avg_trade_pct'],
            })
        except Exception as e:
            print(f"Error with {name}: {e}")
    
    # Sort by Sharpe ratio
    results.sort(key=lambda x: x['sharpe'], reverse=True)
    
    # Display results
    print("\n" + "=" * 80)
    print("  RESULTS (Sorted by Sharpe Ratio)")
    print("=" * 80)
    print(f"\n{'Strategy':<30} {'Net Profit':>12} {'Trades':>8} {'Win%':>7} {'PF':>6} {'MaxDD%':>8} {'Sharpe':>7}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['name']:<30} ${r['net_profit']:>9,.0f} {r['total_trades']:>8} {r['win_rate']:>6.1f}% "
              f"{r['profit_factor']:>6.2f} {r['max_dd_pct']:>7.1f}% {r['sharpe']:>7.3f}")
    
    # Add HODL baseline
    print("-" * 80)
    print(f"{'HODL (Buy & Hold)':<30} ${price_return * 10:>9,.0f} {0:>8} {'N/A':>7} {'N/A':>6} {0:>8}% {0.000:>7.3f}")
    
    # Best strategy
    best = results[0]
    
    print("\n" + "=" * 80)
    print("  BEST STRATEGY")
    print("=" * 80)
    print(f"\n  {best['name']}")
    print(f"  Net Profit: ${best['net_profit']:,.0f} ({best['net_profit_pct']:.1f}%)")
    print(f"  Total Trades: {best['total_trades']}")
    print(f"  Win Rate: {best['win_rate']:.1f}%")
    print(f"  Profit Factor: {best['profit_factor']:.2f}")
    print(f"  Max Drawdown: {best['max_dd_pct']:.1f}%")
    print(f"  Sharpe Ratio: {best['sharpe']:.3f}")
    print(f"\n  vs HODL ({price_return:.1f}%): {best['net_profit_pct'] - price_return:+.1f}% better")
    print("=" * 80)
    
    # Trade efficiency
    print("\n" + "=" * 80)
    print("  TRADE EFFICIENCY (Profit per Trade)")
    print("=" * 80)
    for r in sorted(results, key=lambda x: x['avg_trade_pct'], reverse=True):
        avg_profit = r['net_profit'] / r['total_trades'] if r['total_trades'] > 0 else 0
        print(f"  {r['name']:<30} ${avg_profit:>8,.0f}/trade ({r['avg_trade_pct']:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    run_comparison()
