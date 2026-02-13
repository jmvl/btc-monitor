# BTC Monitor

A comprehensive Python application that monitors BTC/USD price, calculates technical indicators, collects market sentiment from multiple sources, and provides trend analysis with confidence scores.

## Features

- **Real-time Price Monitoring**: Fetches BTC/USD price data at configurable intervals
- **Technical Indicators**: Calculates RSI, MACD, and moving averages
- **Sentiment Analysis**: Aggregates sentiment from Twitter, News, and online research
- **Trend Analysis**: Combines price data, technical indicators, and sentiment into comprehensive trend analysis
- **Confidence Scoring**: Provides confidence scores for trend predictions
- **CLI Interface**: Multiple commands for monitoring, analysis, status checking, and history viewing
- **Configurable**: YAML-based configuration with environment variable overrides
- **SQLite Database**: Persistent storage for price, indicators, and sentiment data
- **Graceful Shutdown**: Handles SIGINT/SIGTERM signals properly
- **Comprehensive Logging**: Configurable logging with timestamps and levels

## Architecture

```
BTC Monitor
├── Price Data Fetching
│   └── yfinance API (BTC/USD)
├── Technical Indicators
│   ├── RSI (Relative Strength Index)
│   ├── MACD (Moving Average Convergence Divergence)
│   └── Moving Averages (20, 50, 200 periods)
├── Sentiment Collection
│   ├── Twitter/X API
│   ├── News API (NewsAPI.org + web scraping fallback)
│   └── Online Research
├── Trend Analysis Engine
│   ├── Technical Analysis (price + indicators)
│   ├── Sentiment Analysis (aggregated sentiment data)
│   └── Confidence Calculation
├── Database (SQLite)
│   ├── Price History
│   ├── Indicator Data
│   └── Trend Analysis Results
└── CLI Interface
    ├── Monitor (continuous)
    ├── Analyze (single-run)
    ├── Status (current state)
    └── History (past analyses)
```

### Data Flow

1. **Fetch**: Get current BTC/USD price from yfinance
2. **Calculate**: Compute technical indicators (RSI, MACD, MAs)
3. **Collect**: Gather sentiment from Twitter, News, and Research
4. **Analyze**: Combine all data points into trend analysis
5. **Score**: Calculate confidence based on multiple factors
6. **Store**: Save everything to SQLite database
7. **Report**: Display results with CLI or API

## Installation

### Prerequisites

- Python 3.9+
- pip (Python package manager)

### Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in development mode
pip install -e .
```

### Optional Dependencies

For full functionality, you may need:

- **Twitter API**: API keys from https://developer.twitter.com/
- **News API**: API key from https://newsapi.org/
- **CoinMarketCap API**: API key from https://pro.coinmarketcap.com/signup (recommended over yfinance)
- **yfinance**: Fallback price data source (automatic install via pip)
- **requests**: For CoinMarketCap API (automatic install via pip)

## Configuration

### Setup Configuration File

1. Copy the example configuration:
```bash
cp config/config.example.yaml config/config.yaml
```

2. Edit `config/config.yaml` with your settings:
```yaml
# Twitter/X API
twitter:
  consumer_key: "your_consumer_key"
  consumer_secret: "your_consumer_secret"
  access_token: "your_access_token"
  access_token_secret: "your_access_token_secret"
  bearer_token: "your_bearer_token"

# News API
news:
  api_key: "your_newsapi_key"
  max_articles: 50
  hours_back: 24

# Research
research:
  max_items: 30
  hours_back: 48

# CoinMarketCap API (recommended)
coinmarketcap:
  api_key: "your_coinmarketcap_api_key_here"  # Leave empty to use yfinance fallback
  max_retries: 3
  initial_backoff: 1.0
  max_backoff: 60.0
  use_circuit_breaker: true

# Database
database:
  url: "sqlite:///btc_monitor.db"

# Data sources
data_sources:
  update_interval: 300  # seconds (5 minutes)
  symbols:
    - "BTC-USD"

# Analysis
analysis:
  rsi_period: 14
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  moving_averages:
    - 20
    - 50
    - 200

# Logging
logging:
  level: "INFO"
  file: "btc_monitor.log"
```

### Environment Variables

You can override configuration with environment variables (prefix: `BTC_MONITOR_`):

```bash
export BTC_MONITOR_TWITTER__BEARER_TOKEN="your_token"
export BTC_MONITOR_NEWS__API_KEY="your_news_key"
export BTC_MONITOR_DATA_SOURCES__UPDATE_INTERVAL=300
export BTC_MONITOR_COINMARKETCAP__API_KEY="your_api_key_here"
export BTC_MONITOR_LOGGING__LEVEL=DEBUG
```

Note: Use `__` (double underscore) for nested configuration keys.

## Price Data Sources

### Primary: CoinMarketCap API (recommended)
Fetches current BTC/USD price with **OHLCV** data (Open, High, Low, Close, Volume) from CoinMarketCap Pro API.

**Features:**
- 24-hour OHLCV data (high, low, close)
- Circuit breaker for API resilience
- Exponential backoff retry logic
- Request/response time logging
- Full integration with existing database schema

**Configuration:**
```yaml
coinmarketcap:
  api_key: "your_api_key_here"  # Get from https://pro.coinmarketcap.com/signup
  max_retries: 3
  initial_backoff: 1.0
  max_backoff: 60.0
  use_circuit_breaker: true
```

### Fallback: yfinance
When CoinMarketCap API key is not configured, yfinance is used as fallback (only current price, no OHLCV data).

### Multi-source support
The system architecture supports multiple price data sources. Currently, CoinMarketCap is primary source when API key is configured, with yfinance as automatic fallback.

**OHLCV Data Structure:**
- **timestamp**: UTC timestamp
- **open_price**: Opening price for the period
- **high**: Highest price for the period
- **low**: Lowest price for the period
- **close**: Current price at data fetch
- **volume**: Trading volume for the period

This OHLCV format provides more complete price data for technical analysis, especially for volatility calculations and charting.

### Environment Variable
`BTC_MONITOR_COINMARKETCAP__API_KEY` - Override CoinMarketCap API key from environment

## Usage

### Initialize Database

First run (or after fresh install):

```bash
python -m btc_monitor init
```

### Run Continuous Monitoring

Monitor BTC price at configured intervals:

```bash
# Basic monitoring
python -m btc_monitor monitor

# With configuration file
python -m btc_monitor monitor --config config/config.yaml

# Verbose logging
python -m btc_monitor monitor --verbose
```

Press `Ctrl+C` to stop gracefully.

### Single Analysis

Perform one-time analysis (without monitoring loop):

```bash
# Basic analysis
python -m btc_monitor analyze

# With specific configuration
python -m btc_monitor analyze --config config/config.yaml

# JSON output
python -m btc_monitor analyze --json
```

### Check Status

View current monitoring status:

```bash
python -m btc_monitor status
```

### View History

See past trend analyses:

```bash
# Last 10 analyses
python -m btc_monitor history

# Last 50 analyses
python -m btc_monitor history --limit 50

# JSON output
python -m btc_monitor history --json
```

### CLI Help

Get help for any command:

```bash
python -m btc_monitor --help
python -m btc_monitor monitor --help
python -m btc_monitor analyze --help
```

## Technical Indicators

### RSI (Relative Strength Index)

- **Period**: 14 (configurable)
- **Range**: 0-100
- **Interpretation**:
  - >70: Overbought (potential sell signal)
  - <30: Oversold (potential buy signal)

### MACD (Moving Average Convergence Divergence)

- **Fast EMA**: 12 periods
- **Slow EMA**: 26 periods
- **Signal Line**: 9 periods
- **Interpretation**:
  - MACD > Signal: Bullish (upward trend)
  - MACD < Signal: Bearish (downward trend)

### Moving Averages

- **Periods**: 20, 50, 200 (configurable)
- **Interpretation**:
  - Price > 20MA: Short-term uptrend
  - Price > 50MA: Medium-term uptrend
  - Price > 200MA: Long-term uptrend

## Sentiment Sources

### Twitter/X

- **API**: Twitter API v2
- **Data**: Recent tweets with #Bitcoin, $BTC, etc.
- **Sentiment**: NLP-based sentiment analysis

### News

- **Primary**: NewsAPI.org (with API key)
- **Fallback**: Web scraping (without API key)
- **Data**: Recent Bitcoin news articles
- **Sentiment**: Text analysis of headlines and content

### Online Research

- **Data**: Research articles, blog posts, forums
- **Sentiment**: Aggregate sentiment from multiple online sources

## Trend Analysis

The system combines multiple data sources into a comprehensive trend analysis:

### Technical Score

Based on:
- Price movement direction
- RSI levels
- MACD crossovers
- Moving average positioning

### Sentiment Score

Based on:
- Twitter sentiment (weighted)
- News sentiment (weighted)
- Research sentiment (weighted)

### Confidence Score

Overall confidence (0-100) based on:
- Agreement between technical and sentiment signals
- Signal strength
- Data quality
- Historical accuracy

## Database Schema

### Tables

- `prices`: Price history (timestamp, open, high, low, close, volume)
- `indicators`: Calculated indicators (timestamp, rsi, macd, macd_signal, ma20, ma50, ma200)
- `sentiment_entries`: Sentiment data (timestamp, source, sentiment_score)
- `trend_analyses`: Complete analyses (timestamp, trend_direction, technical_score, sentiment_score, confidence)

## Testing

Run all tests:

```bash
pytest
```

Run specific test file:

```bash
pytest tests/test_indicators.py -v
```

Run with coverage:

```bash
pytest --cov=btc_monitor --cov-report=html
```

### Type Checking

```bash
# Manual type checking (avoids mypy config issues)
python typecheck_manual.py

# Full mypy (may have warnings)
mypy src/btc_monitor/
```

## Development

### Project Structure

```
btc-monitor/
├── src/btc_monitor/       # Source code
│   ├── __init__.py
│   ├── main.py           # Main monitoring script
│   ├── cli.py            # CLI interface
│   ├── config.py         # Configuration management
│   ├── database.py       # Database operations
│   ├── fetchers.py       # Price fetching
│   ├── indicators.py     # Technical indicators
│   ├── sentiment.py      # Sentiment collection
│   └── analyzer.py       # Trend analysis
├── tests/                  # Test suite
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_fetchers.py
│   ├── test_indicators.py
│   ├── test_sentiment.py
│   └── test_analyzer.py
├── config/                 # Configuration files
│   ├── config.example.yaml
│   └── config.yaml
├── pyproject.toml         # Project metadata
├── pytest.ini            # pytest configuration
└── mypy.ini             # Type checking configuration
```

### Type Hints

All source files include `.pyi` stub files for type hints:

```python
# models.pyi
class PriceEntry:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
```

### Running in Development

```bash
# Install in development mode
pip install -e .

# Run with verbose logging
python -m btc_monitor monitor --verbose

# Check logs
tail -f btc_monitor.log
```

## Troubleshooting

### Database Locked

If you see "database is locked" errors:
```bash
# Remove lock file
rm btc_monitor.db-wal
```

### API Key Issues

If sentiment collection fails:
1. Verify API keys are correct in `config.yaml`
2. Check API rate limits
3. Use web scraping fallback (omit news.api_key)

### High Memory Usage

Reduce data retention:
```yaml
data_sources:
  update_interval: 600  # Increase to 10 minutes
  max_history_hours: 24  # Keep only 24 hours
```

## License

[Specify your license here]

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run all tests: `pytest`
6. Submit a pull request

## Support

For issues, questions, or contributions:
- GitHub Issues: [repository URL]
- Documentation: [link to docs]
