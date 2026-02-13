"""Sentiment data collection models and interface."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from logging import getLogger
from typing import Dict, List, Optional, Union

import requests
import tweepy
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator

logger = getLogger(__name__)


class SentimentSource(str, Enum):
    """Valid sentiment data sources."""
    
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS = "news"
    RESEARCH = "research"


class SentimentEntry(BaseModel):
    """Pydantic model for sentiment data entries.
    
    This model validates sentiment data before it's stored in the database.
    Score ranges from -1.0 (bearish) to +1.0 (bullish), with 0.0 being neutral.
    """
    
    source: Union[str, SentimentSource] = Field(..., description="Source of the sentiment data")
    score: float = Field(..., description="Sentiment score from -1.0 (bearish) to 1.0 (bullish)")
    content: Optional[str] = Field(
        None,
        description="Optional text content associated with the sentiment"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the sentiment was collected"
    )
    
    @field_validator("score")
    @classmethod
    def validate_score_range(cls, v: float) -> float:
        """Ensure score is within valid range.
        
        Args:
            v: The score value to validate
            
        Returns:
            The validated score
            
        Raises:
            ValueError: If score is outside [-1.0, 1.0]
        """
        if v < -1.0 or v > 1.0:
            raise ValueError(f"Score must be between -1.0 and 1.0, got {v}")
        return v
    
    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, v: Union[str, SentimentSource]) -> SentimentSource:
        """Ensure source is a valid sentiment source.
        
        Args:
            v: The source value to validate
            
        Returns:
            The validated source as a SentimentSource enum
            
        Raises:
            ValueError: If source is not one of the allowed values
        """
        if isinstance(v, str):
            try:
                return SentimentSource(v.lower())
            except ValueError:
                valid_sources = [s.value for s in SentimentSource]
                raise ValueError(
                    f"Invalid source '{v}'. Must be one of: {valid_sources}"
                )
        return v
    
    def to_sentiment_data(self) -> "SentimentData":
        """Convert to SentimentData ORM model for database storage.
        
        Returns:
            SentimentData instance ready for database insertion
        """
        from btc_monitor.models import SentimentData
        
        return SentimentData(
            timestamp=self.timestamp,
            source=self.source.value,
            score=self.score,
            content=self.content,
        )


class SentimentCollector(ABC):
    """Abstract base class for sentiment data collectors.
    
    Concrete implementations should inherit from this class and implement
    the collect() method to fetch sentiment data from specific sources.
    """
    
    @abstractmethod
    def collect(self) -> list[SentimentEntry]:
        """Collect sentiment data from the source.
        
        This method must be implemented by all concrete collectors.
        
        Returns:
            List of SentimentEntry objects containing the collected data
            
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement collect() method")


class TwitterSentimentCollector(SentimentCollector):
    """Collector for Twitter/X sentiment data about Bitcoin.
    
    Uses the Twitter API to fetch recent tweets mentioning BTC/bitcoin
    and applies keyword-based sentiment analysis to determine bullish/bearish sentiment.
    """
    
    # Keywords for sentiment scoring
    BULLISH_KEYWORDS = [
        "bullish", "moon", "pump", "bull", "rally", "breakout",
        "surge", "skyrocket", "gains", "uptrend", "buy", "hold",
        "hodl", "rocket", "parabolic", "accumulation", "support"
    ]
    
    BEARISH_KEYWORDS = [
        "bearish", "sell", "dump", "crash", "bear", "drop",
        "plunge", "collapse", "losses", "downtrend", "resistance",
        "correction", "bear market", "short", "fud", "panic"
    ]
    
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_token_secret: str,
        bearer_token: str,
        max_tweets: int = 100,
        search_query: str = "BTC bitcoin -RT",  # -RT excludes retweets
    ):
        """Initialize Twitter sentiment collector.
        
        Args:
            consumer_key: Twitter API consumer key
            consumer_secret: Twitter API consumer secret
            access_token: Twitter API access token
            access_token_secret: Twitter API access token secret
            bearer_token: Twitter API bearer token (for API v2)
            max_tweets: Maximum number of tweets to fetch (default: 100)
            search_query: Search query for tweets (default: "BTC bitcoin -RT")
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.bearer_token = bearer_token
        self.max_tweets = max_tweets
        self.search_query = search_query
        
        # Twitter API client (will be initialized in collect())
        self._api: Optional[tweepy.API] = None
    
    def _authenticate(self) -> None:
        """Authenticate with Twitter API using OAuth 1.0a.
        
        Raises:
            ValueError: If API credentials are missing
            tweepy.TweepyException: If authentication fails
        """
        if not all([
            self.consumer_key, self.consumer_secret,
            self.access_token, self.access_token_secret,
        ]):
            raise ValueError(
                "Twitter API credentials are required. "
                "Please provide consumer_key, consumer_secret, "
                "access_token, and access_token_secret."
            )
        
        try:
            # Create OAuth handler
            auth = tweepy.OAuthHandler(
                self.consumer_key,
                self.consumer_secret
            )
            auth.set_access_token(
                self.access_token,
                self.access_token_secret
            )
            
            # Create API client
            self._api = tweepy.API(
                auth,
                wait_on_rate_limit=True,  # Automatically wait when hitting rate limits
                wait_on_rate_limit_notify=True,
            )
            
            # Verify authentication
            self._api.verify_credentials()
            logger.info("Successfully authenticated with Twitter API")
            
        except tweepy.TweepyException as e:
            logger.error(f"Twitter API authentication failed: {e}")
            raise
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text using keyword matching.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score from -1.0 (bearish) to 1.0 (bullish)
        """
        if not text:
            return 0.0
        
        text_lower = text.lower()
        
        # Count bullish and bearish keywords
        bullish_count = sum(
            1 for keyword in self.BULLISH_KEYWORDS
            if keyword in text_lower
        )
        bearish_count = sum(
            1 for keyword in self.BEARISH_KEYWORDS
            if keyword in text_lower
        )
        
        # Calculate sentiment score
        total_keywords = bullish_count + bearish_count
        
        if total_keywords == 0:
            return 0.0  # Neutral if no sentiment keywords found
        
        # Score ranges from -1.0 to 1.0
        score = (bullish_count - bearish_count) / total_keywords
        
        return score
    
    def collect(self) -> list[SentimentEntry]:
        """Collect sentiment data from Twitter.
        
        Fetches recent tweets matching the search query and analyzes
        their sentiment using keyword-based scoring.
        
        Returns:
            List of SentimentEntry objects with sentiment data
            
        Raises:
            ValueError: If API credentials are missing
            tweepy.TweepyException: If API request fails
        """
        entries = []
        
        try:
            # Authenticate with Twitter API
            self._authenticate()
            
            if self._api is None:
                raise RuntimeError("Twitter API client not initialized")
            
        except (ValueError, tweepy.TweepyException) as e:
            # Authentication errors - re-raise
            logger.error(f"Twitter API authentication failed: {e}")
            raise
        
        try:
            # Fetch tweets
            logger.info(f"Fetching up to {self.max_tweets} tweets: '{self.search_query}'")
            tweets = self._api.search_tweets(
                q=self.search_query,
                count=self.max_tweets,
                tweet_mode="extended",  # Get full text (not truncated)
                lang="en",  # English tweets only
            )
            
            logger.info(f"Fetched {len(tweets)} tweets")
            
        except tweepy.TweepyException as e:
            # Search API errors - log and return empty list (graceful degradation)
            logger.error(f"Twitter API search failed: {e}")
            # Return empty list instead of raising to allow system to continue
            return []
        
        # Analyze sentiment for each tweet
        for tweet in tweets:
            try:
                # Get tweet text
                text = tweet.full_text if hasattr(tweet, "full_text") else tweet.text
                
                # Analyze sentiment
                score = self._analyze_sentiment(text)
                
                # Create sentiment entry
                entry = SentimentEntry(
                    source=SentimentSource.TWITTER,
                    score=score,
                    content=text[:500],  # Limit content length
                    timestamp=tweet.created_at,
                )
                entries.append(entry)
                
            except Exception as e:
                logger.warning(f"Error processing tweet {tweet.id}: {e}")
                continue
        
        logger.info(f"Collected {len(entries)} sentiment entries from Twitter")
        
        return entries
    
    def collect_and_save(self, db_path: Optional[str] = None) -> int:
        """Collect sentiment data and save to database.
        
        Args:
            db_path: Optional path to database file. If not provided,
                    uses default database path.
        
        Returns:
            Number of sentiment entries saved to database
            
        Raises:
            tweepy.TweepyException: If Twitter API authentication fails
        """
        from btc_monitor.database import get_session
        from btc_monitor.models import SentimentData
        
        # Collect sentiment data
        entries = self.collect()
        
        if not entries:
            return 0
        
        # Save to database
        session = get_session(db_path)
        try:
            for entry in entries:
                # Convert SentimentEntry to SentimentData ORM model
                sentiment_data = entry.to_sentiment_data()
                session.add(sentiment_data)
            
            session.commit()
            logger.info(f"Saved {len(entries)} sentiment entries to database")
            return len(entries)
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving sentiment data to database: {e}")
            raise
        finally:
            session.close()


class NewsSentimentCollector(SentimentCollector):
    """Collector for news sentiment data about Bitcoin.
    
    Fetches news articles from various sources (NewsAPI, CoinDesk, Cointelegraph)
    and applies keyword-based sentiment analysis to determine bullish/bearish sentiment.
    """
    
    # Keywords for sentiment scoring
    BULLISH_KEYWORDS = [
        "bullish", "rally", "surge", "gains", "uptrend", "breakout",
        "soar", "skyrocket", "rally", "bull market", "positive",
        "optimistic", "strong", "support", "resistance broken",
        "price surge", "momentum", "growth", "expansion", "record high"
    ]
    
    BEARISH_KEYWORDS = [
        "bearish", "crash", "plunge", "drop", "losses", "downtrend",
        "collapse", "bear market", "negative", "pessimistic", "weak",
        "support broken", "resistance", "price drop", "sell-off",
        "decline", "fall", "slump", "correction", "dump"
    ]
    
    # Crypto news sites to scrape (fallback when no API key)
    NEWS_SOURCES = [
        {
            "name": "CoinDesk",
            "url": "https://www.coindesk.com/bitcoin/",
            "headline_selector": "h2.card-headline",
            "link_selector": "a",
        },
        {
            "name": "Cointelegraph",
            "url": "https://cointelegraph.com/tags/bitcoin",
            "headline_selector": "h2.post-card__title",
            "link_selector": "a",
        },
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_articles: int = 50,
        hours_back: int = 24,
    ):
        """Initialize news sentiment collector.
        
        Args:
            api_key: Optional NewsAPI.org API key. If not provided,
                    falls back to web scraping.
            max_articles: Maximum number of articles to fetch (default: 50)
            hours_back: Only fetch articles from this many hours ago (default: 24)
        """
        self.api_key = api_key
        self.max_articles = max_articles
        self.hours_back = hours_back
        self.cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        # NewsAPI base URL
        self.newsapi_url = "https://newsapi.org/v2/everything"
        
        # HTTP session for requests
        self._session: Optional[requests.Session] = None
    
    def _get_session(self) -> requests.Session:
        """Get or create HTTP session.
        
        Returns:
            requests.Session object
        """
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "Mozilla/5.0 (compatible; BTC-Monitor/1.0)"
            })
        return self._session
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text using keyword matching.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score from -1.0 (bearish) to 1.0 (bullish)
        """
        if not text:
            return 0.0
        
        text_lower = text.lower()
        
        # Count bullish and bearish keywords
        bullish_count = sum(
            1 for keyword in self.BULLISH_KEYWORDS
            if keyword in text_lower
        )
        bearish_count = sum(
            1 for keyword in self.BEARISH_KEYWORDS
            if keyword in text_lower
        )
        
        # Calculate sentiment score
        total_keywords = bullish_count + bearish_count
        
        if total_keywords == 0:
            return 0.0  # Neutral if no sentiment keywords found
        
        # Score ranges from -1.0 to 1.0
        score = (bullish_count - bearish_count) / total_keywords
        
        return score
    
    def _fetch_from_newsapi(self) -> List[Dict[str, any]]:
        """Fetch news articles from NewsAPI.
        
        Returns:
            List of article dictionaries with title, description, url, publishedAt
            
        Raises:
            requests.RequestException: If API request fails
        """
        if not self.api_key:
            raise ValueError("NewsAPI key is required for NewsAPI access")
        
        session = self._get_session()
        
        # Build request parameters
        params = {
            "q": "bitcoin OR btc",
            "apiKey": self.api_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(self.max_articles, 100),  # NewsAPI max is 100
            "from": self.cutoff_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        
        logger.info(f"Fetching news from NewsAPI: {params['q']}")
        
        response = session.get(self.newsapi_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "ok":
            raise ValueError(f"NewsAPI error: {data.get('message', 'Unknown error')}")
        
        articles = data.get("articles", [])
        logger.info(f"Fetched {len(articles)} articles from NewsAPI")
        
        return articles
    
    def _scrape_news_site(self, source: Dict[str, str]) -> List[Dict[str, any]]:
        """Scrape news articles from a crypto news site.
        
        Args:
            source: Dictionary with site configuration (url, headline_selector)
            
        Returns:
            List of article dictionaries with title, description, url, publishedAt
        """
        session = self._get_session()
        articles = []
        
        site_name = source["name"]
        url = source["url"]
        headline_selector = source["headline_selector"]
        
        try:
            logger.info(f"Scraping news from {site_name}: {url}")
            
            response = session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find headlines
            headlines = soup.select(headline_selector)
            
            for headline in headlines[:self.max_articles]:
                try:
                    # Get title
                    title = headline.get_text(strip=True)
                    if not title:
                        continue
                    
                    # Get link
                    link_tag = headline.select_one("a")
                    if link_tag:
                        article_url = link_tag.get("href", "")
                        # Handle relative URLs
                        if article_url.startswith("/"):
                            base_url = "/".join(url.split("/")[:3])
                            article_url = f"{base_url}{article_url}"
                    else:
                        article_url = url
                    
                    # Create article dict (scraped sites don't have timestamps easily accessible)
                    article = {
                        "title": title,
                        "description": "",  # Many sites don't show description in listing
                        "url": article_url,
                        "publishedAt": datetime.now(timezone.utc).isoformat(),
                        "source": {"name": site_name},
                    }
                    articles.append(article)
                    
                except Exception as e:
                    logger.warning(f"Error processing headline from {site_name}: {e}")
                    continue
            
            logger.info(f"Scraped {len(articles)} articles from {site_name}")
            
        except requests.RequestException as e:
            logger.error(f"Error scraping {site_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping {site_name}: {e}")
        
        return articles
    
    def _scrape_news_sources(self) -> List[Dict[str, any]]:
        """Scrape news from configured crypto news sites.
        
        Returns:
            List of article dictionaries
        """
        all_articles = []
        
        for source in self.NEWS_SOURCES:
            articles = self._scrape_news_site(source)
            all_articles.extend(articles)
        
        # Limit to max_articles
        all_articles = all_articles[:self.max_articles]
        
        return all_articles
    
    def collect(self) -> list[SentimentEntry]:
        """Collect sentiment data from news sources.
        
        First tries to use NewsAPI if API key is provided.
        Falls back to web scraping crypto news sites if no API key
        or if API request fails.
        
        Returns:
            List of SentimentEntry objects with sentiment data
        """
        entries = []
        articles = []
        
        # Try NewsAPI first if key is provided
        if self.api_key:
            try:
                articles = self._fetch_from_newsapi()
            except (ValueError, requests.RequestException) as e:
                logger.warning(f"NewsAPI request failed: {e}, falling back to web scraping")
                articles = []
        else:
            logger.info("No NewsAPI key provided, using web scraping")
        
        # Fall back to web scraping
        if not articles:
            articles = self._scrape_news_sources()
        
        # Analyze sentiment for each article
        for article in articles:
            try:
                # Combine title and description for analysis
                title = article.get("title", "")
                description = article.get("description", "")
                text = f"{title} {description}".strip()
                
                if not text:
                    continue
                
                # Parse published timestamp
                published_at = article.get("publishedAt")
                try:
                    if isinstance(published_at, str):
                        # Try ISO format
                        timestamp = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    elif isinstance(published_at, datetime):
                        timestamp = published_at
                    else:
                        timestamp = datetime.now(timezone.utc)
                except Exception:
                    timestamp = datetime.now(timezone.utc)
                
                # Check if article is within time window
                if timestamp < self.cutoff_time:
                    continue
                
                # Analyze sentiment
                score = self._analyze_sentiment(text)
                
                # Create sentiment entry
                entry = SentimentEntry(
                    source=SentimentSource.NEWS,
                    score=score,
                    content=text[:500],  # Limit content length
                    timestamp=timestamp,
                )
                entries.append(entry)
                
            except Exception as e:
                logger.warning(f"Error processing article: {e}")
                continue
        
        logger.info(f"Collected {len(entries)} sentiment entries from news")
        
        return entries
    
    def collect_and_save(self, db_path: Optional[str] = None) -> int:
        """Collect sentiment data and save to database.
        
        Args:
            db_path: Optional path to database file. If not provided,
                    uses default database path.
        
        Returns:
            Number of sentiment entries saved to database
        """
        from btc_monitor.database import get_session
        from btc_monitor.models import SentimentData
        
        # Collect sentiment data
        entries = self.collect()
        
        if not entries:
            return 0
        
        # Save to database
        session = get_session(db_path)
        try:
            for entry in entries:
                # Convert SentimentEntry to SentimentData ORM model
                sentiment_data = entry.to_sentiment_data()
                session.add(sentiment_data)
            
            session.commit()
            logger.info(f"Saved {len(entries)} sentiment entries to database")
            return len(entries)
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving sentiment data to database: {e}")
            raise
        finally:
            session.close()
    
    def __del__(self):
        """Clean up HTTP session when collector is destroyed."""
        if self._session:
            self._session.close()


class ResearchCollector(SentimentCollector):
    """Collector for research data from online sources about Bitcoin.
    
    Scrapes research sites (TradingView, analyst tweets, research reports)
    and parses price targets or sentiment keywords to determine bullish/bearish sentiment.
    """
    
    # Keywords for sentiment scoring
    BULLISH_KEYWORDS = [
        "bullish", "rally", "surge", "gains", "uptrend", "breakout",
        "soar", "skyrocket", "bull market", "positive", "optimistic",
        "strong", "strong support", "resistance broken", "price surge",
        "momentum", "growth", "expansion", "record high", "upgrade",
        "outperform", "buy", "overweight", "accumulate", "long",
        "holding above"
    ]
    
    BEARISH_KEYWORDS = [
        "bearish", "crash", "plunge", "drop", "losses", "downtrend",
        "collapse", "bear market", "negative", "pessimistic", "weak",
        "support broken", "strong resistance", "price drop", "sell-off",
        "decline", "fall", "slump", "correction", "dump", "downgrade",
        "underperform", "sell", "reduce", "short", "holding below",
        "struggling at"
    ]
    
    # Research sources to scrape
    RESEARCH_SOURCES = [
        {
            "name": "TradingView",
            "url": "https://www.tradingview.com/symbols/BTCUSD/ideas/",
            "idea_selector": "div.tv-widget-idea__title-row",
            "author_selector": "span.tv-widget-idea__author",
        },
    ]
    
    def __init__(
        self,
        max_items: int = 30,
        hours_back: int = 48,
        current_price: Optional[float] = None,
    ):
        """Initialize research collector.
        
        Args:
            max_items: Maximum number of research items to fetch (default: 30)
            hours_back: Only fetch research from this many hours ago (default: 48)
            current_price: Current BTC price for price target comparison.
                         If not provided, price targets won't be scored.
        """
        self.max_items = max_items
        self.hours_back = hours_back
        self.current_price = current_price
        self.cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        # HTTP session for requests
        self._session: Optional[requests.Session] = None
    
    def _get_session(self) -> requests.Session:
        """Get or create HTTP session.
        
        Returns:
            requests.Session object
        """
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "Mozilla/5.0 (compatible; BTC-Monitor/1.0)"
            })
        return self._session
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text using keyword matching.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score from -1.0 (bearish) to 1.0 (bullish)
        """
        if not text:
            return 0.0
        
        text_lower = text.lower()
        
        # Count bullish and bearish keywords
        bullish_count = sum(
            1 for keyword in self.BULLISH_KEYWORDS
            if keyword in text_lower
        )
        bearish_count = sum(
            1 for keyword in self.BEARISH_KEYWORDS
            if keyword in text_lower
        )
        
        # Calculate sentiment score
        total_keywords = bullish_count + bearish_count
        
        if total_keywords == 0:
            return 0.0  # Neutral if no sentiment keywords found
        
        # Score ranges from -1.0 to 1.0
        score = (bullish_count - bearish_count) / total_keywords
        
        return score
    
    def _extract_price_target(self, text: str) -> Optional[float]:
        """Extract price target from text.
        
        Looks for price targets in formats like:
        - "$100,000"
        - "100k"
        - "0.5M"
        
        Args:
            text: Text to parse
            
        Returns:
            Extracted price target as float, or None if not found
        """
        import re
        
        if not text:
            return None
        
        # Pattern 1: $100,000 or $100000
        dollar_pattern = r'\$\s*([\d,]+(?:\.\d+)?)'
        match = re.search(dollar_pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1).replace(',', '')
            try:
                return float(price_str)
            except ValueError:
                pass
        
        # Pattern 2: 100k, 100K
        k_pattern = r'(\d+(?:\.\d+)?)\s*[kK]\b'
        match = re.search(k_pattern, text)
        if match:
            try:
                return float(match.group(1)) * 1000
            except ValueError:
                pass
        
        # Pattern 3: 1M, 0.5M
        m_pattern = r'(\d+(?:\.\d+)?)\s*[mM]\b'
        match = re.search(m_pattern, text)
        if match:
            try:
                return float(match.group(1)) * 1_000_000
            except ValueError:
                pass
        
        return None
    
    def _score_price_target(self, target: float) -> float:
        """Score price target based on current price.
        
        A target higher than current price is bullish (positive score),
        a target lower is bearish (negative score).
        
        Args:
            target: Price target to score
            
        Returns:
            Sentiment score from -1.0 to 1.0
        """
        if self.current_price is None:
            return 0.0  # Can't score without current price
        
        if target == self.current_price:
            return 0.0
        
        # Calculate percentage difference
        diff = (target - self.current_price) / self.current_price
        
        # Clamp to [-1.0, 1.0] with sigmoid-like curve
        # 10% difference = ~0.5 score, 50%+ difference = ~1.0 score
        import math
        score = 2 / (1 + math.exp(-10 * diff)) - 1
        
        return max(-1.0, min(1.0, score))
    
    def _scrape_research_site(self, source: Dict[str, str]) -> List[Dict[str, any]]:
        """Scrape research from a site.
        
        Args:
            source: Dictionary with site configuration (url, idea_selector, author_selector)
            
        Returns:
            List of research dictionaries with title, author, url, publishedAt
        """
        session = self._get_session()
        items = []
        
        site_name = source["name"]
        url = source["url"]
        idea_selector = source["idea_selector"]
        author_selector = source.get("author_selector", "")
        
        try:
            logger.info(f"Scraping research from {site_name}: {url}")
            
            response = session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find research items
            ideas = soup.select(idea_selector)
            
            for idea in ideas[:self.max_items]:
                try:
                    # Get title
                    title_elem = idea.select_one("a")
                    title = title_elem.get_text(strip=True) if title_elem else ""
                    if not title:
                        continue
                    
                    # Get author if available
                    author = ""
                    if author_selector:
                        author_elem = idea.select_one(author_selector)
                        if author_elem:
                            author = author_elem.get_text(strip=True)
                    
                    # Get link
                    if title_elem:
                        item_url = title_elem.get("href", "")
                        # Handle relative URLs
                        if item_url.startswith("/"):
                            base_url = "/".join(url.split("/")[:3])
                            item_url = f"{base_url}{item_url}"
                    else:
                        item_url = url
                    
                    # Create research dict
                    item = {
                        "title": title,
                        "author": author,
                        "url": item_url,
                        "publishedAt": datetime.now(timezone.utc).isoformat(),
                        "source": {"name": site_name},
                    }
                    items.append(item)
                    
                except Exception as e:
                    logger.warning(f"Error processing research item from {site_name}: {e}")
                    continue
            
            logger.info(f"Scraped {len(items)} research items from {site_name}")
            
        except requests.RequestException as e:
            logger.error(f"Error scraping {site_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping {site_name}: {e}")
        
        return items
    
    def _scrape_research_sources(self) -> List[Dict[str, any]]:
        """Scrape research from configured sources.
        
        Returns:
            List of research dictionaries
        """
        all_items = []
        
        for source in self.RESEARCH_SOURCES:
            items = self._scrape_research_site(source)
            all_items.extend(items)
        
        # Limit to max_items
        all_items = all_items[:self.max_items]
        
        return all_items
    
    def collect(self) -> list[SentimentEntry]:
        """Collect sentiment data from research sources.
        
        Scrapes research sites and analyzes price targets and sentiment keywords
        to determine bullish/bearish sentiment.
        
        Returns:
            List of SentimentEntry objects with sentiment data
        """
        entries = []
        items = []
        
        # Scrape research sources
        items = self._scrape_research_sources()
        
        # Analyze each research item
        for item in items:
            try:
                title = item.get("title", "")
                author = item.get("author", "Unknown")
                
                if not title:
                    continue
                
                # Parse published timestamp
                published_at = item.get("publishedAt")
                try:
                    if isinstance(published_at, str):
                        timestamp = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    elif isinstance(published_at, datetime):
                        timestamp = published_at
                    else:
                        timestamp = datetime.now(timezone.utc)
                except Exception:
                    timestamp = datetime.now(timezone.utc)
                
                # Check if item is within time window
                if timestamp < self.cutoff_time:
                    continue
                
                # Extract and score price target
                price_target = self._extract_price_target(title)
                target_score = 0.0
                if price_target:
                    target_score = self._score_price_target(price_target)
                
                # Analyze sentiment keywords
                keyword_score = self._analyze_sentiment(title)
                
                # Combine scores (price target takes precedence)
                # If we have a price target score, use it (weighted 70%)
                # Otherwise use keyword score (weighted 100%)
                if abs(target_score) > 0.1:
                    # Price target is significant, use it
                    final_score = (0.7 * target_score) + (0.3 * keyword_score)
                else:
                    # No significant price target, use keyword score
                    final_score = keyword_score
                
                # Build content with author
                content_parts = []
                if author and author != "Unknown":
                    content_parts.append(f"By {author}")
                content_parts.append(title)
                content = ". ".join(content_parts)
                
                # Create sentiment entry
                entry = SentimentEntry(
                    source=SentimentSource.RESEARCH,
                    score=final_score,
                    content=content[:500],  # Limit content length
                    timestamp=timestamp,
                )
                entries.append(entry)
                
            except Exception as e:
                logger.warning(f"Error processing research item: {e}")
                continue
        
        logger.info(f"Collected {len(entries)} sentiment entries from research")
        
        return entries
    
    def collect_and_save(self, db_path: Optional[str] = None) -> int:
        """Collect sentiment data and save to database.
        
        Args:
            db_path: Optional path to database file. If not provided,
                    uses default database path.
        
        Returns:
            Number of sentiment entries saved to database
        """
        from btc_monitor.database import get_session
        from btc_monitor.models import SentimentData
        
        # Collect sentiment data
        entries = self.collect()
        
        if not entries:
            return 0
        
        # Save to database
        session = get_session(db_path)
        try:
            for entry in entries:
                # Convert SentimentEntry to SentimentData ORM model
                sentiment_data = entry.to_sentiment_data()
                session.add(sentiment_data)
            
            session.commit()
            logger.info(f"Saved {len(entries)} sentiment entries to database")
            return len(entries)
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving sentiment data to database: {e}")
            raise
        finally:
            session.close()
    
    def __del__(self):
        """Clean up HTTP session when collector is destroyed."""
        if self._session:
            self._session.close()
