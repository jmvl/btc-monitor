# BTC Monitor - System Architecture

## Overview

BTC Monitor is a Python-based cryptocurrency monitoring system that combines technical analysis with sentiment analysis to provide comprehensive BTC/USD market monitoring and trend prediction.

## Design Principles

1. **Modularity**: Each component is independent and can be tested in isolation
2. **Extensibility**: Easy to add new indicators, sentiment sources, or analysis methods
3. **Configurability**: YAML-based configuration with environment variable overrides
4. **Persistence**: SQLite database for all data and analyses
5. **Graceful Degradation**: System continues if some sentiment sources fail
6. **Type Safety**: Full type hints with `.pyi` stub files

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLI Interface                          │
│  (monitor | analyze | status | history | help)             │
└────────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
┌────────▼────────┐  ┌───▼──────────┐  ┌──▼─────────────┐
│  Main Script   │  │   Config      │  │   Database     │
│  (monitor.py) │  │  (config.py) │  │ (database.py)  │
└────────┬────────┘  └───────────────┘  └────────┬────────┘
         │                                 │
         │                    ┌────────────┼────────────┐
         │                    │            │            │
┌────────▼────────┐  ┌────▼────────┐  ┌─────▼──────┐  ┌──▼───────────┐
│  Price Fetcher │  │  Indicators  │  │  Sentiment   │  │  Analyzer    │
│  (fetchers.py) │  │(indicators)  │  │ (sentiment) │  │  (analyzer)  │
└────────┬────────┘  └─────────────┘  └─────┬──────┘  └──────┬──────┘
         │                                 │                │
         │                    ┌────────────┼────────────┐
         │                    │            │            │
    ┌───▼────────┐     ┌────▼────────┐  ┌────▼──────┐  ┌──▼────────┐
    │  yfinance    │     │  RSI, MACD, │  │ Twitter   │  │  Trend    │
    │  API        │     │  MAs        │  │ News      │  │  Engine   │
    └────────────┘     └──────────────┘  │ Research  │  └───────────┘
                                      └───────────┘
```

## Modules

### 1. CLI Module (`cli.py`)

**Purpose**: Command-line interface for user interaction

**Commands**:
- `monitor`: Continuous monitoring loop
- `analyze`: Single-run analysis
- `status`: Display current system state
- `history`: View past analyses

**Key Functions**:
```python
def cmd_monitor(args)      # Run continuous monitoring
def cmd_analyze(args)      # Single analysis
def cmd_status(args)       # Show status
def cmd_history(args)      # Show history
def setup_logging(verbose)  # Configure logging
def format_output(data, json)  # Format output
```

### 2. Main Script (`main.py`)

**Purpose**: Orchestrate monitoring loop and coordinate all components

**Flow**:
1. Initialize logging
2. Load configuration
3. Setup signal handlers (SIGINT, SIGTERM)
4. Initialize database
5. Create components (fetcher, indicators, sentiment, analyzer)
6. Enter monitoring loop:
   - Fetch price
   - Calculate indicators
   - Collect sentiment
   - Analyze trend
   - Save to database
   - Sleep for configured interval
7. Handle graceful shutdown

**Key Functions**:
```python
def signal_handler(signum, frame)     # Handle shutdown signals
def setup_logging(config, level, file) # Setup logging
def main_loop(config)                # Main monitoring loop
def graceful_shutdown()                # Cleanup and exit
```

### 3. Configuration Module (`config.py`)

**Purpose**: Load and validate configuration

**Features**:
- YAML file loading
- Environment variable overrides (prefix: `BTC_MONITOR_`)
- Pydantic validation
- Type-safe access via `@property` methods

**Configuration Structure**:
```python
class TwitterConfig(BaseModel):
    consumer_key: str
    consumer_secret: str
    access_token: str
    access_token_secret: str
    bearer_token: str

class NewsConfig(BaseModel):
    api_key: str
    max_articles: int
    hours_back: int

class DatabaseConfig(BaseModel):
    url: str  # SQLite connection string

class DataSourcesConfig(BaseModel):
    update_interval: int
    symbols: list[str]

class AnalysisConfig(BaseModel):
    rsi_period: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    moving_averages: list[int]

class LoggingConfig(BaseModel):
    level: str
    file: str

class Config(BaseSettings):
    twitter: TwitterConfig
    news: NewsConfig
    research: ResearchConfig
    database: DatabaseConfig
    data_sources: DataSourcesConfig
    analysis: AnalysisConfig
    logging: LoggingConfig
```

**Environment Variable Mapping**:
```
BTC_MONITOR_TWITTER__BEARER_TOKEN   → config.twitter.bearer_token
BTC_MONITOR_NEWS__API_KEY          → config.news.api_key
BTC_MONITOR_DATA_SOURCES__UPDATE_INTERVAL → config.data_sources.update_interval
```

### 4. Database Module (`database.py`)

**Purpose**: SQLite database operations and models

**Models**:
```python
class PriceEntry(Base):
    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int

class IndicatorEntry(Base):
    timestamp: datetime
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    ma20: float | None
    ma50: float | None
    ma200: float | None

class SentimentEntry(Base):
    timestamp: datetime
    source: str  # 'twitter', 'news', 'research'
    sentiment_score: float  # -1.0 to 1.0
    confidence: float | None
    raw_data: str | None

class TrendAnalysis(Base):
    timestamp: datetime
    trend_direction: str  # 'up', 'down', 'sideways'
    technical_score: float
    sentiment_score: float
    confidence: float  # 0 to 100
    signals: str | None  # JSON of all signals
```

**Key Functions**:
```python
def init_db()                          # Initialize database schema
def get_session()                        # Get database session
def save_price(price_data)               # Save price entry
def save_indicators(indicator_data)        # Save indicator entry
def save_sentiment(sentiment_data)        # Save sentiment entry
def save_analysis(analysis_data)          # Save trend analysis
def get_latest_price(symbol)             # Get latest price
def get_historical_prices(symbol, hours)  # Get price history
def get_latest_analysis()                 # Get latest analysis
```

### 5. Price Fetcher Module (`fetchers.py`)

**Purpose**: Fetch BTC/USD price data

**Data Source**: yfinance API

**Key Functions**:
```python
class PriceFetcher:
    def __init__(self, symbol: str)
    def fetch_current_price() -> PriceEntry
    def fetch_historical_data(hours: int) -> list[PriceEntry]
    def is_market_open() -> bool
```

**Data Returned**:
```python
{
    'timestamp': datetime(2026, 2, 13, 10, 0, 0),
    'symbol': 'BTC-USD',
    'open': 95000.00,
    'high': 96000.00,
    'low': 94000.00,
    'close': 95500.00,
    'volume': 15000000
}
```

### 6. Indicators Module (`indicators.py`)

**Purpose**: Calculate technical indicators

**Classes**:

#### RSI (Relative Strength Index)
```python
class RSI:
    def __init__(self, period: int = 14)
    def calculate(self, prices: list[float]) -> float
    def update(self, new_price: float) -> float
```

**Formula**:
```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss (over period)
```

**Interpretation**:
- >70: Overbought (sell signal)
- <30: Oversold (buy signal)
- 30-70: Neutral

#### MACD (Moving Average Convergence Divergence)
```python
class MACD:
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9)
    def calculate(self, prices: list[float]) -> dict
    def update(self, new_price: float) -> dict
```

**Formulas**:
```
MACD Line = EMA(fast) - EMA(slow)
Signal Line = EMA(MACD, signal)
Histogram = MACD - Signal
```

**Interpretation**:
- MACD > Signal: Bullish
- MACD < Signal: Bearish
- Crossover above: Buy signal
- Crossover below: Sell signal

#### Moving Averages
```python
class MovingAverages:
    def __init__(self, periods: list[int] = [20, 50, 200])
    def calculate(self, prices: list[float]) -> dict
    def update(self, new_price: float) -> dict
```

**Formulas**:
```
SMA = Sum(prices) / Count(prices)
EMA = (Price * K) + (Previous_EMA * (1 - K))
K = 2 / (period + 1)
```

**Interpretation**:
- Price > MA(20): Short-term uptrend
- Price > MA(50): Medium-term uptrend
- Price > MA(200): Long-term uptrend

### 7. Sentiment Module (`sentiment.py`)

**Purpose**: Collect and analyze market sentiment

**Base Class**:
```python
class SentimentCollector(ABC):
    @abstractmethod
    def collect(self) -> list[SentimentEntry]
```

#### Twitter Sentiment Collector
```python
class TwitterSentimentCollector(SentimentCollector):
    def __init__(self, config: TwitterConfig)
    def collect(self) -> list[SentimentEntry]
```

**Data Source**: Twitter API v2

**Search Query**: `#Bitcoin OR $BTC OR cryptocurrency`

**Sentiment Analysis**:
- NLP-based sentiment scoring
- Keywords: bullish, bearish, uptrend, downtrend, crash, moon
- Emoji analysis (🚀, 📉, 💎, etc.)
- Weights: verified users > recent tweets

#### News Sentiment Collector
```python
class NewsSentimentCollector(SentimentCollector):
    def __init__(self, config: NewsConfig)
    def collect(self) -> list[SentimentEntry]
```

**Data Sources**:
1. NewsAPI.org (if API key provided)
2. Web scraping fallback (coindesk, cointelegraph, etc.)

**Sentiment Analysis**:
- Headline sentiment
- Article content sentiment
- Publication weighting (major news > blogs)

#### Research Collector
```python
class ResearchCollector(SentimentCollector):
    def __init__(self, config: ResearchConfig)
    def collect(self) -> list[SentimentEntry]
```

**Data Sources**:
- Research articles
- Forum discussions (Reddit, Bitcointalk)
- Blog posts

**Sentiment Analysis**:
- Aggregate sentiment from multiple sources
- Weight by source credibility
- Filter for relevance

### 8. Analyzer Module (`analyzer.py`)

**Purpose**: Combine technical and sentiment data into trend analysis

**Key Functions**:
```python
class TrendAnalyzer:
    def __init__(self, config: AnalysisConfig)
    def analyze(
        self,
        price_data: PriceEntry,
        indicators: IndicatorEntry,
        sentiment_data: list[SentimentEntry]
    ) -> TrendAnalysis
```

**Analysis Logic**:

#### Technical Score
```
technical_score = (
    price_movement_weight * price_direction +
    rsi_weight * rsi_position +
    macd_weight * macd_signal +
    ma_weight * ma_position
)
```

#### Sentiment Score
```
sentiment_score = (
    twitter_weight * avg_twitter_sentiment +
    news_weight * avg_news_sentiment +
    research_weight * avg_research_sentiment
)
```

#### Confidence Score
```
confidence = (
    agreement_weight * abs(technical - sentiment) +
    signal_strength_weight * signal_strength +
    data_quality_weight * data_quality
)
```

#### Trend Direction
```
if technical > 0.5 and sentiment > 0.5:
    trend = "up"
elif technical < 0.5 and sentiment < 0.5:
    trend = "down"
else:
    trend = "sideways"
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Monitoring Loop (Every N seconds)                  │
└────────────────────────────┬────────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
    ┌───────▼────────┐    ┌─────────▼──────────┐
    │  Fetch Price    │    │  Database Query     │
    │  (yfinance)     │    │  (latest data)     │
    └──────┬─────────┘    └─────────┬──────────┘
           │                         │
    ┌──────▼────────────┐  ┌───────▼────────┐
    │  Calc Indicators  │  │  Get Sentiment   │
    │  (RSI, MACD, MA)│  │  (from DB/API)  │
    └──────┬────────────┘  └───────┬────────┘
           │                         │
    ┌──────▼────────────┐  ┌───────▼────────┐
    │  Collect Sent.    │  │  Combine Data   │
    │  (Twitter/News)   │  │  (All sources)  │
    └──────┬────────────┘  └───────┬────────┘
           │                         │
    ┌──────▼─────────────────────────────▼───────────┐
    │  Analyze Trend                          │
    │  (Technical + Sentiment + Confidence)    │
    └──────┬─────────────────────────────┘
           │
    ┌──────▼──────────┐
    │  Save to DB     │
    │  (all results)   │
    └──────┬──────────┘
           │
    ┌──────▼────────┐
    │  Log & Display│
    │  (output)      │
    └──────┴────────┘
```

## Error Handling

### Price Fetching Errors
- **Network timeout**: Retry 3 times with exponential backoff
- **API rate limit**: Wait and retry
- **Market closed**: Use last known price

### Indicator Calculation Errors
- **Insufficient data**: Wait for more data points
- **Invalid values**: Skip and log warning

### Sentiment Collection Errors
- **API auth failure**: Skip source, use others
- **Rate limit**: Wait and retry
- **Parse errors**: Log and skip entry

### Database Errors
- **Lock timeout**: Retry with longer timeout
- **Connection error**: Reconnect and retry
- **Corruption**: Backup and recreate

## Performance Considerations

### Database Optimization
- Indexes on `timestamp` and `symbol` columns
- Prune old data (configurable retention)
- WAL mode for concurrent access

### Caching
- Price data cached for 1 minute
- Sentiment data cached for 15 minutes
- Indicator calculation results cached

### Resource Limits
- Max sentiment entries per source (configurable)
- Max historical data points (configurable)
- Max concurrent API requests (limited to 3)

## Security Considerations

### API Keys
- Never log API keys
- Use environment variables for sensitive data
- Never commit keys to git

### Data Privacy
- Only store public sentiment data
- No personal user data
- Anonymize data before analysis

### Input Validation
- Pydantic validation for all config
- Type checking on all inputs
- Sanitization of user-provided data

## Testing Strategy

### Unit Tests
- Each module tested independently
- Mock external APIs (yfinance, Twitter, News)
- Edge cases and error conditions

### Integration Tests
- Test component interactions
- Database operations
- End-to-end workflows

### Type Checking
- Full type hints on all functions
- `.pyi` stub files for modules
- mypy strict mode

## Future Enhancements

### Planned Features
1. **Real-time Notifications**: Email/Telegram alerts on trend changes
2. **Web Dashboard**: Visual interface for monitoring
3. **API Server**: REST API for external integration
4. **More Indicators**: Bollinger Bands, Stochastic, Fibonacci
5. **Machine Learning**: ML models for trend prediction
6. **Multi-Coin Support**: ETH, SOL, ADA, etc.
7. **Trading Signals**: Buy/sell recommendations based on analysis

### Potential Optimizations
1. **Async I/O**: Use `asyncio` for concurrent API calls
2. **Redis Cache**: Replace in-memory caching with Redis
3. **TimescaleDB**: Replace SQLite for time-series data
4. **Message Queue**: RabbitMQ/Kafka for distributed processing
