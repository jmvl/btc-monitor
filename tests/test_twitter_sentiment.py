"""Tests for Twitter sentiment collector."""

import datetime
from typing import List
from unittest.mock import Mock, MagicMock, patch

import pytest
import tweepy

from btc_monitor.sentiment import (
    SentimentEntry,
    SentimentSource,
    TwitterSentimentCollector,
)


class MockTweet:
    """Mock Tweet object for testing."""
    
    def __init__(
        self,
        id: int,
        text: str,
        created_at: datetime.datetime,
    ):
        self.id = id
        self.text = text
        self.full_text = text
        self.created_at = created_at


class TestTwitterSentimentCollector:
    """Test suite for TwitterSentimentCollector."""
    
    def test_twitter_collector_initialization(self):
        """Test that TwitterSentimentCollector can be initialized with credentials."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
            max_tweets=50,
            search_query="bitcoin",
        )
        
        assert collector.consumer_key == "test_key"
        assert collector.consumer_secret == "test_secret"
        assert collector.access_token == "test_token"
        assert collector.access_token_secret == "test_token_secret"
        assert collector.bearer_token == "test_bearer"
        assert collector.max_tweets == 50
        assert collector.search_query == "bitcoin"
    
    def test_twitter_collector_default_values(self):
        """Test that TwitterSentimentCollector has correct default values."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        assert collector.max_tweets == 100
        assert collector.search_query == "BTC bitcoin -RT"
    
    def test_analyze_sentiment_bullish(self):
        """Test sentiment analysis with bullish keywords."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Test single bullish keyword
        score = collector._analyze_sentiment("Bitcoin is going to the moon!")
        assert score > 0
        
        # Test multiple bullish keywords
        score = collector._analyze_sentiment("Bullish pump rally breakout gains!")
        assert score > 0
    
    def test_analyze_sentiment_bearish(self):
        """Test sentiment analysis with bearish keywords."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Test single bearish keyword
        score = collector._analyze_sentiment("Bitcoin is going to crash!")
        assert score < 0
        
        # Test multiple bearish keywords
        score = collector._analyze_sentiment("Bearish sell dump crash losses!")
        assert score < 0
    
    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis with no sentiment keywords."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Test no keywords
        score = collector._analyze_sentiment("Bitcoin price is currently $50000")
        assert score == 0.0
    
    def test_analyze_sentiment_mixed(self):
        """Test sentiment analysis with mixed bullish and bearish keywords."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Equal bullish and bearish keywords (1 bullish, 1 bearish)
        score = collector._analyze_sentiment("Bullish and bearish")
        assert score == 0.0
        
        # More bullish than bearish (2 bullish, 1 bearish)
        score = collector._analyze_sentiment("Bullish pump rally but bearish")
        assert score > 0
        
        # More bearish than bullish (1 bullish, 3 bearish)
        score = collector._analyze_sentiment("Bearish sell dump crash but bullish")
        assert score < 0
    
    def test_analyze_sentiment_empty_text(self):
        """Test sentiment analysis with empty text."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Empty string
        score = collector._analyze_sentiment("")
        assert score == 0.0
        
        # None (should be handled)
        score = collector._analyze_sentiment(None)  # type: ignore
        assert score == 0.0
    
    def test_analyze_sentiment_case_insensitive(self):
        """Test that sentiment analysis is case-insensitive."""
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Uppercase
        score1 = collector._analyze_sentiment("BITCOIN IS BULLISH MOON")
        # Lowercase
        score2 = collector._analyze_sentiment("bitcoin is bullish moon")
        # Mixed case
        score3 = collector._analyze_sentiment("Bitcoin is Bullish Moon")
        
        assert score1 == score2 == score3
        assert score1 > 0
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_authenticates(self, mock_oauth_handler, mock_api):
        """Test that collect() authenticates with Twitter API."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.return_value = []
        mock_api.return_value = mock_api_instance
        
        # Create collector and collect
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        entries = collector.collect()
        
        # Verify authentication
        mock_oauth_handler.assert_called_once_with("test_key", "test_secret")
        mock_auth.set_access_token.assert_called_once_with("test_token", "test_token_secret")
        mock_api.assert_called_once()
        mock_api_instance.verify_credentials.assert_called_once()
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_fetches_tweets(self, mock_oauth_handler, mock_api):
        """Test that collect() fetches tweets with correct query."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        # Create mock tweets
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_tweets = [
            MockTweet(id=1, text="Bitcoin is bullish", created_at=now),
            MockTweet(id=2, text="BTC is going to moon", created_at=now),
        ]
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.return_value = mock_tweets
        mock_api.return_value = mock_api_instance
        
        # Create collector and collect
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
            max_tweets=50,
            search_query="bitcoin crypto",
        )
        
        entries = collector.collect()
        
        # Verify search_tweets was called correctly
        mock_api_instance.search_tweets.assert_called_once()
        call_args = mock_api_instance.search_tweets.call_args
        
        assert call_args[1]["count"] == 50
        assert call_args[1]["q"] == "bitcoin crypto"
        assert call_args[1]["lang"] == "en"
        assert call_args[1]["tweet_mode"] == "extended"
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_creates_sentiment_entries(self, mock_oauth_handler, mock_api):
        """Test that collect() creates SentimentEntry objects."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_tweets = [
            MockTweet(
                id=1,
                text="Bitcoin is going to the moon! 🚀",
                created_at=now,
            ),
            MockTweet(
                id=2,
                text="BTC crash imminent! Sell now!",
                created_at=now,
            ),
        ]
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.return_value = mock_tweets
        mock_api.return_value = mock_api_instance
        
        # Create collector and collect
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        entries: List[SentimentEntry] = collector.collect()
        
        # Verify entries
        assert len(entries) == 2
        
        # First entry (bullish)
        assert entries[0].source == SentimentSource.TWITTER
        assert entries[0].score > 0
        assert "moon" in entries[0].content.lower() or entries[0].content == "Bitcoin is going to the moon! 🚀"
        assert entries[0].timestamp == now
        
        # Second entry (bearish)
        assert entries[1].source == SentimentSource.TWITTER
        assert entries[1].score < 0
        assert "crash" in entries[1].content.lower() or "sell" in entries[1].content.lower()
        assert entries[1].timestamp == now
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_content_length_limit(self, mock_oauth_handler, mock_api):
        """Test that long tweet content is truncated to 500 characters."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        now = datetime.datetime.now(datetime.timezone.utc)
        long_text = "Bitcoin " * 1000  # Very long text
        
        mock_tweets = [
            MockTweet(id=1, text=long_text, created_at=now),
        ]
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.return_value = mock_tweets
        mock_api.return_value = mock_api_instance
        
        # Create collector and collect
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        entries = collector.collect()
        
        # Verify content is truncated
        assert len(entries) == 1
        assert len(entries[0].content) <= 500
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_handles_api_error(self, mock_oauth_handler, mock_api):
        """Test that collect() handles Twitter API errors gracefully."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.side_effect = tweepy.TweepyException("API Error")
        mock_api.return_value = mock_api_instance
        
        # Create collector and collect
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Should raise the exception (not return empty list)
        with pytest.raises(tweepy.TweepyException):
            collector.collect()
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_handles_search_error(self, mock_oauth_handler, mock_api):
        """Test that collect() handles search API errors gracefully."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.side_effect = tweepy.TweepyException("Search Error")
        mock_api.return_value = mock_api_instance
        
        # Create collector and collect
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        # Should return empty list on search error (graceful degradation)
        entries = collector.collect()
        assert entries == []
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_handles_missing_credentials(self, mock_oauth_handler, mock_api):
        """Test that collect() raises ValueError for missing credentials."""
        # Create collector with missing credentials
        collector = TwitterSentimentCollector(
            consumer_key="",  # Empty
            consumer_secret="",  # Empty
            access_token="",  # Empty
            access_token_secret="",  # Empty
            bearer_token="test_bearer",
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Twitter API credentials are required"):
            collector.collect()
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_and_save(self, mock_oauth_handler, mock_api, tmp_path):
        """Test that collect_and_save() saves sentiment data to database."""
        from btc_monitor.database import init_db
        from btc_monitor.models import SentimentData
        
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_tweets = [
            MockTweet(id=1, text="Bitcoin bullish", created_at=now),
        ]
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.return_value = mock_tweets
        mock_api.return_value = mock_api_instance
        
        # Setup database
        db_path = tmp_path / "test.db"
        init_db(db_path)
        
        # Create collector and collect_and_save
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        count = collector.collect_and_save(str(db_path))
        
        # Verify count
        assert count == 1
        
        # Verify database
        from btc_monitor.database import get_session
        session = get_session(str(db_path))
        try:
            sentiment_records = session.query(SentimentData).all()
            assert len(sentiment_records) == 1
            
            record = sentiment_records[0]
            assert record.source == "twitter"
            assert record.score > 0
            assert record.content is not None
            # SQLite doesn't preserve timezone, so compare datetime without tz
            assert record.timestamp.replace(tzinfo=None) == now.replace(tzinfo=None)
        finally:
            session.close()
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_and_save_empty_results(self, mock_oauth_handler, mock_api, tmp_path):
        """Test that collect_and_save() handles empty results correctly."""
        from btc_monitor.database import init_db
        
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.return_value = []  # No tweets
        mock_api.return_value = mock_api_instance
        
        # Setup database
        db_path = tmp_path / "test.db"
        init_db(db_path)
        
        # Create collector and collect_and_save
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        count = collector.collect_and_save(str(db_path))
        
        # Verify count is 0
        assert count == 0
    
    def test_bullish_keywords(self):
        """Test that BULLISH_KEYWORDS contains expected keywords."""
        expected_keywords = [
            "bullish", "moon", "pump", "bull", "rally", "breakout",
            "surge", "skyrocket", "gains", "uptrend", "buy", "hold",
            "hodl", "rocket", "parabolic", "accumulation", "support"
        ]
        
        for keyword in expected_keywords:
            assert keyword in TwitterSentimentCollector.BULLISH_KEYWORDS
    
    def test_bearish_keywords(self):
        """Test that BEARISH_KEYWORDS contains expected keywords."""
        expected_keywords = [
            "bearish", "sell", "dump", "crash", "bear", "drop",
            "plunge", "collapse", "losses", "downtrend", "resistance",
            "correction", "bear market", "short", "fud", "panic"
        ]
        
        for keyword in expected_keywords:
            assert keyword in TwitterSentimentCollector.BEARISH_KEYWORDS
    
    @patch("btc_monitor.sentiment.tweepy.API")
    @patch("btc_monitor.sentiment.tweepy.OAuthHandler")
    def test_collect_processes_full_text(self, mock_oauth_handler, mock_api):
        """Test that collect() uses full_text attribute when available."""
        # Setup mocks
        mock_auth = MagicMock()
        mock_oauth_handler.return_value = mock_auth
        
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Create mock tweet with full_text
        mock_tweet = MockTweet(id=1, text="Bitcoin bullish", created_at=now)
        
        mock_api_instance = MagicMock()
        mock_api_instance.verify_credentials.return_value = True
        mock_api_instance.search_tweets.return_value = [mock_tweet]
        mock_api.return_value = mock_api_instance
        
        # Create collector and collect
        collector = TwitterSentimentCollector(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        
        entries = collector.collect()
        
        # Verify entry was created
        assert len(entries) == 1
        assert entries[0].score > 0
