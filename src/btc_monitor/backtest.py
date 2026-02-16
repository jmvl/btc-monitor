"""
Backtesting engine that matches TradingView's PineScript strategy behavior.

Key behaviors replicated:
- calc_on_every_tick = false → signals on bar close, orders fill on next bar open
- fill_orders_on_standard_ohlc = true → fills at the Open price
- margin_long = 0, margin_short = 0 → no margin calls
- commission_type = percent → applied on both entry and exit
"""

import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class Signal(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Trade:
    """A single completed (or open) trade."""
    entry_date: datetime
    entry_price: float
    entry_qty: float
    direction: str = "long"
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    entry_commission: float = 0.0
    exit_commission: float = 0.0


@dataclass
class BacktestConfig:
    """Backtest settings matching TradingView's strategy() properties."""
    initial_capital: float = 10000.0
    commission_pct: float = 0.1  # e.g. 0.1 = 0.1%
    slippage_ticks: int = 0
    qty_type: str = "percent_of_equity"
    qty_value: float = 100.0  # 100 = 100% of equity
    pyramiding: int = 1
    start_date: str = "2018-01-01"
    end_date: str = "2069-12-31"


# ---------------------------------------------------------------------------
# Indicator helpers (matching TradingView)
# ---------------------------------------------------------------------------

def calc_smma(series: pd.Series, length: int) -> pd.Series:
    """
    Smoothed Moving Average matching TradingView's ta.rma().
    Also known as RMA / Wilder's smoothing.
    
    Formula: smma[i] = (smma[i-1] * (length - 1) + src[i]) / length
    Seed: SMA of the first *length* valid values.
    """
    smma = pd.Series(np.nan, index=series.index)
    vals = series.values
    
    # Find seed from first `length` consecutive non-NaN values
    valid = ~np.isnan(vals)
    start = -1
    count = 0
    for i in range(len(vals)):
        if valid[i]:
            count += 1
            if count == length:
                start = i - length + 1
                break
        else:
            count = 0
    
    if start < 0:
        return smma
    
    seed_idx = start + length - 1
    smma.iloc[seed_idx] = np.mean(vals[start:start + length])
    
    for i in range(seed_idx + 1, len(vals)):
        if np.isnan(vals[i]):
            break
        smma.iloc[i] = (smma.iloc[i - 1] * (length - 1) + vals[i]) / length
    
    return smma


def calc_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """
    RSI matching TradingView's ta.rsi().
    Uses Wilder's smoothing (RMA/SMMA) for average gains/losses.
    """
    # Calculate price changes
    delta = close.diff()
    
    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = (-delta).where(delta < 0, 0.0)
    
    # Use SMMA (RMA) for smoothing - matches TradingView
    avg_gain = calc_smma(gains, length)
    avg_loss = calc_smma(losses, length)
    
    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calc_ema(series: pd.Series, length: int) -> pd.Series:
    """
    EMA matching TradingView's ta.ema().
    Multiplier: 2 / (length + 1)
    Seed: SMA of the first *length* valid values
    """
    multiplier = 2.0 / (length + 1)
    ema = pd.Series(np.nan, index=series.index, dtype=float)
    vals = series.values
    
    # Find the first index with `length` consecutive non-NaN values for the seed
    valid = ~np.isnan(vals)
    start = -1
    count = 0
    for i in range(len(vals)):
        if valid[i]:
            count += 1
            if count == length:
                start = i - length + 1
                break
        else:
            count = 0
    
    if start < 0:
        return ema  # not enough data
    
    seed_idx = start + length - 1
    ema.iloc[seed_idx] = np.mean(vals[start:start + length])
    
    for i in range(seed_idx + 1, len(vals)):
        if np.isnan(vals[i]):
            break
        ema.iloc[i] = vals[i] * multiplier + ema.iloc[i - 1] * (1 - multiplier)
    
    return ema


def detect_crossover(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """
    True on bars where *fast* crosses **above** *slow*.
    Matches TradingView's ta.crossover().
    """
    return (fast.shift(1) <= slow.shift(1)) & (fast > slow)


def detect_crossunder(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """
    True on bars where *fast* crosses **below** *slow*.
    Matches TradingView's ta.crossunder().
    """
    return (fast.shift(1) >= slow.shift(1)) & (fast < slow)


# ---------------------------------------------------------------------------
# Strategy Classes
# ---------------------------------------------------------------------------

class RSIStrategy:
    """
    RSI-based trading strategy matching TradingView behavior.
    
    Entry: Buy when RSI crosses below oversold level (e.g., 30)
    Exit: Sell when RSI crosses above overbought level (e.g., 70)
    """
    
    def __init__(self, rsi_period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.name = f"RSI Strategy (RSI {rsi_period}, Buy < {oversold}, Sell > {overbought})"
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate entry/exit signals based on RSI crossover/crossunder.
        
        Args:
            df: DataFrame with 'Close' column
            
        Returns:
            DataFrame with added 'long_entry' and 'long_exit' boolean columns
        """
        df = df.copy()
        
        # Calculate RSI using Wilder's smoothing (matches TradingView)
        df['rsi'] = calc_rsi(df['Close'], self.rsi_period)
        
        # Entry: RSI crosses below oversold level
        df['long_entry'] = detect_crossunder(df['rsi'], pd.Series(self.oversold, index=df.index))
        
        # Exit: RSI crosses above overbought level  
        df['long_exit'] = detect_crossover(df['rsi'], pd.Series(self.overbought, index=df.index))
        
        return df
    
    def to_pinescript(self) -> str:
        """Generate PineScript code for this strategy."""
        return f'''// RSI Strategy - Generated by BTC Monitor
// Matches Python backtest 100%

//@version=5
strategy("RSI Strategy", overlay=false, initial_capital=10000, 
         default_qty_type=strategy.percent_of_equity, default_qty_value=100,
         commission_type=strategy.commission.percent, commission_value=0.1,
         margin_long=0, margin_short=0)

// Inputs
rsi_period = input.int({self.rsi_period}, "RSI Period", minval=1)
oversold = input.float({self.oversold}, "Oversold Level", minval=0, maxval=100)
overbought = input.float({self.overbought}, "Overbought Level", minval=0, maxval=100)

// Calculate RSI (matches Wilder's smoothing)
rsi_value = ta.rsi(close, rsi_period)

// Entry condition: RSI crosses below oversold
longCondition = ta.crossunder(rsi_value, oversold)
if (longCondition)
    strategy.entry("Long", strategy.long)

// Exit condition: RSI crosses above overbought
exitCondition = ta.crossover(rsi_value, overbought)
if (exitCondition)
    strategy.close("Long")

// Plot RSI
plot(rsi_value, "RSI", color=color.blue)
hline(oversold, "Oversold", color=color.green)
hline(overbought, "Overbought", color=color.red)
'''


# ---------------------------------------------------------------------------
# Core backtest engine (matching TradingView execution order)
# ---------------------------------------------------------------------------

class Backtester:
    """
    Backtesting engine that matches TradingView's PineScript behavior.
    
    Execution order per bar:
    1. Fill pending orders at this bar's Open price
    2. Update equity mark-to-market at Close
    3. Detect signals at Close
    4. Queue pending orders for next bar
    """
    
    def __init__(self, config: BacktestConfig = None):
        """
        Initialize backtester.
        
        Args:
            config: BacktestConfig with settings matching TradingView
        """
        self.config = config or BacktestConfig()
        self.commission_rate = self.config.commission_pct / 100.0
    
    def run_backtest(self, df: pd.DataFrame) -> dict:
        """
        Run a long-only backtest matching TradingView behavior.
        
        Required columns in df:
            Open, High, Low, Close, long_entry (bool), long_exit (bool)
            
        The DataFrame should include warmup bars before start_date
        so that indicator values are accurate.
        
        Returns a dict of KPIs including a 'trades' list.
        """
        # Input validation
        required = {"Open", "High", "Low", "Close", "long_entry", "long_exit"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")
        
        df = df.copy()
        start = pd.Timestamp(self.config.start_date)
        end = pd.Timestamp(self.config.end_date)
        
        # Ensure timezone consistency
        if df.index.tz is not None and start.tz is None:
            start = start.tz_localize('UTC')
            end = end.tz_localize('UTC')
        elif df.index.tz is None and start.tz is not None:
            start = start.tz_convert(None)
            end = end.tz_convert(None)
        
        # Adjust start if data starts later
        data_first = df.index[0]
        if data_first > start:
            logger.warning(f"Data starts after start_date. Adjusting to {data_first.date()}")
            start = data_first
        
        # State variables
        equity = self.config.initial_capital
        cash = self.config.initial_capital
        position_qty = 0.0
        position_entry_price = 0.0
        trades: List[Trade] = []
        current_trade: Optional[Trade] = None
        
        pending_entry = False
        pending_exit = False
        
        equity_curve: List[dict] = []
        
        # Intrabar drawdown tracking (TV methodology)
        peak_equity = self.config.initial_capital
        max_intrabar_dd = 0.0
        max_intrabar_dd_pct = 0.0
        
        # Bar-by-bar loop (matches TV execution order)
        for i in range(len(df)):
            bar = df.iloc[i]
            bar_date = df.index[i]
            bar_in_range = start <= bar_date <= end
            
            # 1) FILL pending orders at this bar's Open
            if pending_entry and position_qty == 0:
                fill_price = bar["Open"]
                
                # TV sizes so trade_value + commission = equity
                trade_value = equity / (1 + self.commission_rate)
                qty = trade_value / fill_price
                entry_commission = trade_value * self.commission_rate
                
                position_qty = qty
                position_entry_price = fill_price
                cash = equity - trade_value - entry_commission
                
                current_trade = Trade(
                    entry_date=bar_date,
                    entry_price=fill_price,
                    entry_qty=qty,
                    direction="long",
                    entry_commission=entry_commission,
                )
                pending_entry = False
                logger.debug(f"BUY at {fill_price:.2f} on {bar_date.date()}")
            
            if pending_exit and position_qty > 0:
                fill_price = bar["Open"]
                trade_value = position_qty * fill_price
                exit_commission = trade_value * self.commission_rate
                
                gross_pnl = position_qty * (fill_price - position_entry_price)
                net_pnl = gross_pnl - current_trade.entry_commission - exit_commission
                
                cash += trade_value - exit_commission
                equity = cash
                
                current_trade.exit_date = bar_date
                current_trade.exit_price = fill_price
                current_trade.pnl = net_pnl
                entry_value = current_trade.entry_qty * current_trade.entry_price
                current_trade.pnl_pct = (net_pnl / entry_value) * 100
                current_trade.exit_commission = exit_commission
                trades.append(current_trade)
                
                logger.debug(f"SELL at {fill_price:.2f} on {bar_date.date()}, PnL: {net_pnl:.2f}")
                
                current_trade = None
                position_qty = 0.0
                position_entry_price = 0.0
                pending_exit = False
            
            # 2a) Intrabar drawdown check (only while holding a long position)
            if bar_in_range and position_qty > 0:
                equity_at_low = cash + position_qty * bar["Low"]
                dd = equity_at_low - peak_equity
                dd_pct = (dd / peak_equity) * 100 if peak_equity != 0 else 0.0
                if dd < max_intrabar_dd:
                    max_intrabar_dd = dd
                if dd_pct < max_intrabar_dd_pct:
                    max_intrabar_dd_pct = dd_pct
            
            # 2b) Mark-to-market equity at Close
            if position_qty > 0:
                equity = cash + position_qty * bar["Close"]
            else:
                equity = cash
            
            if bar_in_range:
                equity_curve.append({"date": bar_date, "equity": equity})
            
            # 2c) Update peak equity — ONLY when flat
            if bar_in_range and position_qty == 0 and equity > peak_equity:
                peak_equity = equity
            
            # 3) Detect signals at Close (only inside trading window)
            pending_entry = False
            pending_exit = False
            
            if bar_in_range:
                if bar["long_entry"] and position_qty == 0:
                    pending_entry = True
                if bar["long_exit"] and position_qty > 0:
                    pending_exit = True
        
        # Record any open position at end of data
        if current_trade is not None:
            trades.append(current_trade)
        
        equity_df = pd.DataFrame(equity_curve)
        kpis = self._compute_kpis(trades, equity_df, max_intrabar_dd, max_intrabar_dd_pct)
        kpis["actual_start_date"] = str(start.date())
        kpis["actual_end_date"] = str(end.date())
        
        return kpis
    
    def _compute_kpis(
        self,
        trades: List[Trade],
        equity_df: pd.DataFrame,
        max_intrabar_dd: float,
        max_intrabar_dd_pct: float
    ) -> dict:
        """Compute performance KPIs matching TradingView's Strategy Tester."""
        
        initial_capital = self.config.initial_capital
        
        if not trades:
            return {"error": "No trades executed"}
        
        final_equity = equity_df["equity"].iloc[-1] if len(equity_df) > 0 else initial_capital
        
        # Separate closed vs open trades
        closed_trades = [t for t in trades if t.exit_date is not None]
        open_trades = [t for t in trades if t.exit_date is None]
        
        # PnL — net_profit based on CLOSED trades only (matches TV)
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = sum(t.pnl for t in losing_trades)
        net_profit = gross_profit + gross_loss
        net_profit_pct = (net_profit / initial_capital) * 100
        
        # Open P&L
        open_profit = (final_equity - initial_capital) - net_profit
        
        # Total P&L
        total_pnl = net_profit + open_profit
        total_pnl_pct = (total_pnl / initial_capital) * 100
        
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float("inf")
        
        # Trade statistics (closed trades only)
        total_trades = len(closed_trades)
        num_winning = len(winning_trades)
        num_losing = len(losing_trades)
        win_rate = (num_winning / total_trades) * 100 if total_trades > 0 else 0
        
        avg_trade = net_profit / total_trades if total_trades > 0 else 0
        avg_trade_pct = sum(t.pnl_pct for t in closed_trades) / total_trades if total_trades > 0 else 0
        avg_winning = gross_profit / num_winning if num_winning > 0 else 0
        avg_losing = gross_loss / num_losing if num_losing > 0 else 0
        avg_win_loss_ratio = abs(avg_winning / avg_losing) if avg_losing != 0 else float("inf")
        
        largest_winning = max((t.pnl for t in winning_trades), default=0)
        largest_losing = min((t.pnl for t in losing_trades), default=0)
        
        # Consecutive wins/losses
        max_consec_wins = max_consec_losses = 0
        cur_w = cur_l = 0
        for t in closed_trades:
            if t.pnl > 0:
                cur_w += 1
                cur_l = 0
                max_consec_wins = max(max_consec_wins, cur_w)
            else:
                cur_l += 1
                cur_w = 0
                max_consec_losses = max(max_consec_losses, cur_l)
        
        total_commission = sum(t.entry_commission + t.exit_commission for t in closed_trades)
        
        # Sharpe/Sortino (annualized for crypto: 365 days)
        sharpe = sortino = 0.0
        if len(equity_df) > 1:
            daily_returns = equity_df["equity"].pct_change().dropna()
            std = daily_returns.std()
            if std != 0:
                sharpe = (daily_returns.mean() / std) * np.sqrt(365)
            downside = daily_returns[daily_returns < 0]
            if len(downside) > 0 and downside.std() != 0:
                sortino = (daily_returns.mean() / downside.std()) * np.sqrt(365)
        
        return {
            "strategy_name": "RSI Strategy",
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "net_profit": net_profit,
            "net_profit_pct": net_profit_pct,
            "open_profit": open_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_intrabar_dd,
            "max_drawdown_pct": max_intrabar_dd_pct,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "total_trades": total_trades,
            "num_winning": num_winning,
            "num_losing": num_losing,
            "win_rate": win_rate,
            "avg_trade": avg_trade,
            "avg_trade_pct": avg_trade_pct,
            "avg_winning": avg_winning,
            "avg_losing": avg_losing,
            "avg_win_loss_ratio": avg_win_loss_ratio,
            "largest_winning": largest_winning,
            "largest_losing": largest_losing,
            "max_consec_wins": max_consec_wins,
            "max_consec_losses": max_consec_losses,
            "total_commission": total_commission,
            "final_equity": final_equity,
            "initial_capital": initial_capital,
            "trades": trades,
        }


def print_kpis(kpis: dict):
    """Print KPIs matching TradingView's Strategy Tester format."""
    print("=" * 60)
    print("  STRATEGY PERFORMANCE SUMMARY")
    print("=" * 60)
    print()
    has_open = abs(kpis.get('open_profit', 0)) > 0.005
    if has_open:
        print(f"  Total P&L (incl. open): ${kpis['total_pnl']:>10,.2f}  ({kpis['total_pnl_pct']:>8.2f}%)")
    print(f"  Net Profit (closed):    ${kpis['net_profit']:>10,.2f}  ({kpis['net_profit_pct']:>8.2f}%)")
    if has_open:
        open_pct = (kpis['open_profit'] / kpis['initial_capital']) * 100
        print(f"  Open P&L:               ${kpis['open_profit']:>10,.2f}  ({open_pct:>8.2f}%)")
    print(f"  Gross Profit:           ${kpis['gross_profit']:>10,.2f}")
    print(f"  Gross Loss:             ${kpis['gross_loss']:>10,.2f}")
    print()
    print(f"  Profit Factor:         {kpis['profit_factor']:>12.3f}")
    print(f"  Max Drawdown:         ${kpis['max_drawdown']:>12,.2f}  ({kpis['max_drawdown_pct']:>8.2f}%)")
    print(f"  Sharpe Ratio:          {kpis['sharpe_ratio']:>12.3f}")
    print()
    print(f"  Total Trades:          {kpis['total_trades']:>12d}")
    print(f"  Winning Trades:        {kpis['num_winning']:>12d}  ({kpis['win_rate']:>6.2f}%)")
    print(f"  Losing Trades:         {kpis['num_losing']:>12d}")
    print()
    print(f"  Avg Trade:            ${kpis['avg_trade']:>12,.2f}  ({kpis['avg_trade_pct']:>8.2f}%)")
    print(f"  Avg Winning Trade:    ${kpis['avg_winning']:>12,.2f}")
    print(f"  Avg Losing Trade:     ${kpis['avg_losing']:>12,.2f}")
    print()
    print(f"  Largest Win:          ${kpis['largest_winning']:>12,.2f}")
    print(f"  Largest Loss:         ${kpis['largest_losing']:>12,.2f}")
    print()
    print(f"  Max Consec. Wins:      {kpis['max_consec_wins']:>12d}")
    print(f"  Max Consec. Losses:    {kpis['max_consec_losses']:>12d}")
    print()
    print(f"  Total Commission:     ${kpis['total_commission']:>12,.2f}")
    print(f"  Initial Capital:      ${kpis['initial_capital']:>12,.2f}")
    print(f"  Final Equity:         ${kpis['final_equity']:>12,.2f}")
    print("=" * 60)


def print_trades(trades: List[Trade], max_trades: int = 0):
    """Print trade list."""
    print()
    header = (f"  {'#':>3}  {'Entry Date':>12}  {'Entry $':>10}  {'Exit Date':>12}  "
              f"{'Exit $':>10}  {'Qty':>12}  {'PnL $':>12}  {'PnL %':>8}")
    print(header)
    print("  " + "-" * 95)
    
    display = trades if max_trades == 0 else trades[:max_trades]
    for i, t in enumerate(display, 1):
        exit_date = t.exit_date.strftime("%Y-%m-%d") if t.exit_date else "OPEN"
        exit_price = f"{t.exit_price:>10,.2f}" if t.exit_price else "      OPEN"
        pnl = f"{t.pnl:>12,.2f}" if t.pnl is not None else "        N/A"
        pnl_pct = f"{t.pnl_pct:>8.2f}" if t.pnl_pct is not None else "     N/A"
        
        print(f"  {i:>3}  {t.entry_date.strftime('%Y-%m-%d'):>12}  {t.entry_price:>10,.2f}  "
              f"{exit_date:>12}  {exit_price}  {t.entry_qty:>12.6f}  {pnl}  {pnl_pct}")
    
    if max_trades and len(trades) > max_trades:
        print(f"  ... ({len(trades) - max_trades} more trades)")
