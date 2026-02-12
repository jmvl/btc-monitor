"""Type stubs for sentiment module."""

from abc import ABC
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel
from sqlalchemy.orm import Session


class SentimentSource(str, Enum):
    """Valid sentiment data sources."""
    
    TWITTER: str = "twitter"
    REDDIT: str = "reddit"
    NEWS: str = "news"
    RESEARCH: str = "research"


class SentimentEntry(BaseModel):
    """Pydantic model for sentiment data entries."""
    
    source: Union[str, SentimentSource]
    score: float
    content: Optional[str]
    timestamp: datetime
    
    def to_sentiment_data(self) -> "SentimentData":
        """Convert to SentimentData ORM model for database storage."""
        ...


class SentimentCollector(ABC):
    """Abstract base class for sentiment data collectors."""
    
    @staticmethod
    def collect(self) -> List[SentimentEntry]:
        """Collect sentiment data from the source."""
        ...


class TwitterSentimentCollector(SentimentCollector):
    """Collector for Twitter/X sentiment data about Bitcoin."""
    
    BULLISH_KEYWORDS: List[str]
    BEARISH_KEYWORDS: List[str]
    
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_token_secret: str,
        bearer_token: str,
        max_tweets: int = 100,
        search_query: str = "BTC bitcoin -RT",
    ) -> None:
        """Initialize Twitter sentiment collector."""
        ...
    
    def _authenticate(self) -> None:
        """Authenticate with Twitter API using OAuth 1.0a."""
        ...
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text using keyword matching."""
        ...
    
    def collect(self) -> List[SentimentEntry]:
        """Collect sentiment data from Twitter."""
        ...
    
    def collect_and_save(self, db_path: Optional[str] = None) -> int:
        """Collect sentiment data and save to database."""
        ...


class NewsSentimentCollector(SentimentCollector):
    """Collector for news sentiment data about Bitcoin."""
    
    BULLISH_KEYWORDS: List[str]
    BEARISH_KEYWORDS: List[str]
    NEWS_SOURCES: List[Dict[str, str]]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_articles: int = 50,
        hours_back: int = 24,
    ) -> None:
        """Initialize news sentiment collector."""
        ...
    
    def _get_session(self) -> Any:
        """Get or create HTTP session."""
        ...
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text using keyword matching."""
        ...
    
    def _fetch_from_newsapi(self) -> List[Dict[str, Any]]:
        """Fetch news articles from NewsAPI."""
        ...
    
    def _scrape_news_site(self, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """Scrape news articles from a crypto news site."""
        ...
    
    def _scrape_news_sources(self) -> List[Dict[str, Any]]:
        """Scrape news from configured crypto news sites."""
        ...
    
    def collect(self) -> List[SentimentEntry]:
        """Collect sentiment data from news sources."""
        ...
    
    def collect_and_save(self, db_path: Optional[str] = None) -> int:
        """Collect sentiment data and save to database."""
        ...
    
    def __del__(self) -> None:
        """Clean up HTTP session when collector is destroyed."""
        ...
