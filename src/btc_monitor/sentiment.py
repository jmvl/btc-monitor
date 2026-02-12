"""Sentiment data collection models and interface."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from logging import getLogger
from typing import Dict, List, Optional, Union

import tweepy
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
