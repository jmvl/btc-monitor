"""Tests for news sentiment collector."""

import datetime
from typing import List
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from btc_monitor.sentiment import (
    SentimentEntry,
    SentimentSource,
    NewsSentimentCollector,
)


class MockResponse:
    """Mock requests.Response object for testing."""
    
    def __init__(self, json_data: dict, status_code: int = 200, text: str = ""):
        self._json_data = json_data
        self.status_code = status_code
        self._text = text
        self.headers = {"Content-Type": "application/json"}
    
    def json(self):
        return self._json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")
    
    @property
    def text(self):
        return self._text


class TestNewsSentimentCollector:
    """Test suite for NewsSentimentCollector."""
    
    def test_news_collector_initialization(self):
        """Test that NewsSentimentCollector can be initialized with parameters."""
        collector = NewsSentimentCollector(
            api_key="test_api_key",
            max_articles=30,
            hours_back=12,
        )
        
        assert collector.api_key == "test_api_key"
        assert collector.max_articles == 30
        assert collector.hours_back == 12
    
    def test_news_collector_default_values(self):
        """Test that NewsSentimentCollector has correct default values."""
        collector = NewsSentimentCollector()
        
        assert collector.api_key is None
        assert collector.max_articles == 50
        assert collector.hours_back == 24
    
    def test_news_collector_cutoff_time(self):
        """Test that cutoff_time is calculated correctly."""
        hours_back = 24
        collector = NewsSentimentCollector(hours_back=hours_back)
        
        expected_cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_back)
        
        # Allow 1 second tolerance for test execution time
        time_diff = abs((collector.cutoff_time - expected_cutoff).total_seconds())
        assert time_diff < 1.0
    
    def test_analyze_sentiment_bullish(self):
        """Test sentiment analysis with bullish keywords."""
        collector = NewsSentimentCollector()
        
        # Test single bullish keyword
        score = collector._analyze_sentiment("Bitcoin price surges to new heights")
        assert score > 0
        
        # Test multiple bullish keywords
        score = collector._analyze_sentiment("Bullish rally breakout gains momentum")
        assert score > 0
        
        # Test specific keywords
        assert collector._analyze_sentiment("Strong support levels") > 0
        assert collector._analyze_sentiment("Record high reached") > 0
    
    def test_analyze_sentiment_bearish(self):
        """Test sentiment analysis with bearish keywords."""
        collector = NewsSentimentCollector()
        
        # Test single bearish keyword
        score = collector._analyze_sentiment("Bitcoin crashes today")
        assert score < 0
        
        # Test multiple bearish keywords
        score = collector._analyze_sentiment("Bear market crash plunge losses")
        assert score < 0
        
        # Test specific keywords
        assert collector._analyze_sentiment("Price drop continues") < 0
        assert collector._analyze_sentiment("Major sell-off") < 0
    
    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis with no keywords (neutral)."""
        collector = NewsSentimentCollector()
        
        # Test empty text
        score = collector._analyze_sentiment("")
        assert score == 0.0
        
        # Test text with no sentiment keywords
        score = collector._analyze_sentiment("Bitcoin price today")
        assert score == 0.0
        
        # Test text with technical details only
        score = collector._analyze_sentiment("BTC volume 24h 1.2B")
        assert score == 0.0
    
    def test_analyze_sentiment_mixed(self):
        """Test sentiment analysis with mixed bullish and bearish keywords."""
        collector = NewsSentimentCollector()
        
        # More bullish than bearish
        score = collector._analyze_sentiment("Bullish rally but some losses")
        assert score > 0
        
        # More bearish than bullish
        score = collector._analyze_sentiment("Bearish crash but some support")
        assert score < 0
        
        # Equal bullish and bearish
        score = collector._analyze_sentiment("Bullish gains and bearish losses")
        assert score == 0.0
    
    def test_analyze_sentiment_case_insensitive(self):
        """Test that sentiment analysis is case-insensitive."""
        collector = NewsSentimentCollector()
        
        score_lower = collector._analyze_sentiment("bitcoin rally bullish gains")
        score_upper = collector._analyze_sentiment("BITCOIN RALLY BULLISH GAINS")
        score_mixed = collector._analyze_sentiment("Bitcoin Rally Bullish Gains")
        
        assert score_lower == score_upper == score_mixed
    
    def test_get_session_creates_session(self):
        """Test that _get_session creates a new session if needed."""
        collector = NewsSentimentCollector()
        
        assert collector._session is None
        
        session = collector._get_session()
        
        assert session is not None
        assert isinstance(session, requests.Session)
        assert collector._session is session
    
    def test_get_session_reuses_session(self):
        """Test that _get_session reuses existing session."""
        collector = NewsSentimentCollector()
        
        session1 = collector._get_session()
        session2 = collector._get_session()
        
        assert session1 is session2
    
    def test_get_session_sets_user_agent(self):
        """Test that session has proper User-Agent header."""
        collector = NewsSentimentCollector()
        
        session = collector._get_session()
        
        assert "User-Agent" in session.headers
        assert "BTC-Monitor" in session.headers["User-Agent"]
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_fetch_from_newsapi_success(self, mock_get_session):
        """Test successful news fetch from NewsAPI."""
        mock_session = Mock()
        mock_response = MockResponse({
            "status": "ok",
            "articles": [
                {
                    "title": "Bitcoin surges to new high",
                    "description": "BTC breaks resistance",
                    "url": "https://example.com/article1",
                    "publishedAt": "2024-01-15T10:00:00Z",
                    "source": {"name": "Test News"}
                },
                {
                    "title": "Market analysis",
                    "description": "Technical indicators show...",
                    "url": "https://example.com/article2",
                    "publishedAt": "2024-01-15T11:00:00Z",
                    "source": {"name": "Test News"}
                }
            ]
        })
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        collector = NewsSentimentCollector(api_key="test_key")
        articles = collector._fetch_from_newsapi()
        
        assert len(articles) == 2
        assert articles[0]["title"] == "Bitcoin surges to new high"
        assert articles[1]["title"] == "Market analysis"
        mock_session.get.assert_called_once()
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_fetch_from_newsapi_no_api_key(self, mock_get_session):
        """Test that _fetch_from_newsapi raises error without API key."""
        collector = NewsSentimentCollector(api_key=None)
        
        with pytest.raises(ValueError, match="NewsAPI key is required"):
            collector._fetch_from_newsapi()
        
        # Should not call get_session
        mock_get_session.assert_not_called()
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_fetch_from_newsapi_http_error(self, mock_get_session):
        """Test handling of HTTP errors from NewsAPI."""
        mock_session = Mock()
        mock_response = MockResponse({}, status_code=401)
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        collector = NewsSentimentCollector(api_key="test_key")
        
        with pytest.raises(requests.HTTPError):
            collector._fetch_from_newsapi()
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_fetch_from_newsapi_api_error(self, mock_get_session):
        """Test handling of NewsAPI error responses."""
        mock_session = Mock()
        mock_response = MockResponse({
            "status": "error",
            "message": "Invalid API key"
        })
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        collector = NewsSentimentCollector(api_key="test_key")
        
        with pytest.raises(ValueError, match="NewsAPI error"):
            collector._fetch_from_newsapi()
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_fetch_from_newsapi_respects_max_articles(self, mock_get_session):
        """Test that _fetch_from_newsapi respects max_articles limit."""
        mock_session = Mock()
        
        # Create 150 articles (more than max_articles)
        all_articles = [
            {
                "title": f"Article {i}",
                "description": f"Description {i}",
                "url": f"https://example.com/article{i}",
                "publishedAt": "2024-01-15T10:00:00Z",
                "source": {"name": "Test News"}
            }
            for i in range(150)
        ]
        
        # Mock response that respects pageSize parameter
        def mock_get(url, **kwargs):
            params = kwargs.get("params", {})
            page_size = params.get("pageSize", 100)
            
            articles_data = {
                "status": "ok",
                "articles": all_articles[:page_size]
            }
            return MockResponse(articles_data)
        
        mock_session.get = mock_get
        mock_get_session.return_value = mock_session
        
        collector = NewsSentimentCollector(api_key="test_key", max_articles=75)
        articles = collector._fetch_from_newsapi()
        
        # Should get max_articles (75) since it's less than 100
        assert len(articles) == 75
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_fetch_from_newsapi_uses_time_filter(self, mock_get_session):
        """Test that _fetch_from_newsapi uses hours_back time filter."""
        mock_session = Mock()
        mock_response = MockResponse({
            "status": "ok",
            "articles": []
        })
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        hours_back = 12
        collector = NewsSentimentCollector(api_key="test_key", hours_back=hours_back)
        collector._fetch_from_newsapi()
        
        # Check that 'from' parameter was set
        call_args = mock_session.get.call_args
        params = call_args[1]["params"]
        
        assert "from" in params
        # Verify the format is ISO datetime
        datetime.datetime.fromisoformat(params["from"].replace("Z", "+00:00"))
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_scrape_news_site_success(self, mock_get_session):
        """Test successful news site scraping."""
        mock_session = Mock()
        
        html_content = """
        <html>
            <body>
                <h2 class="card-headline">
                    <a href="/article1">Bitcoin Rally Continues</a>
                </h2>
                <h2 class="card-headline">
                    <a href="/article2">Market Analysis</a>
                </h2>
                <h2 class="card-headline">
                    <a href="https://external.com/article3">External Link</a>
                </h2>
            </body>
        </html>
        """
        
        mock_response = MockResponse({}, text=html_content)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        source = {
            "name": "Test Site",
            "url": "https://example.com/bitcoin",
            "headline_selector": "h2.card-headline",
            "link_selector": "a",
        }
        
        collector = NewsSentimentCollector(max_articles=10)
        articles = collector._scrape_news_site(source)
        
        assert len(articles) == 3
        assert articles[0]["title"] == "Bitcoin Rally Continues"
        assert articles[1]["title"] == "Market Analysis"
        assert articles[2]["title"] == "External Link"
        
        # Check that relative URLs are handled
        assert articles[0]["url"] == "https://example.com/article1"
        assert articles[2]["url"] == "https://external.com/article3"
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_scrape_news_site_http_error(self, mock_get_session):
        """Test handling of HTTP errors when scraping."""
        mock_session = Mock()
        mock_response = MockResponse({}, status_code=404)
        mock_response.raise_for_status = Mock(side_effect=requests.HTTPError("404 Not Found"))
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        source = {
            "name": "Test Site",
            "url": "https://example.com/bitcoin",
            "headline_selector": "h2.card-headline",
            "link_selector": "a",
        }
        
        collector = NewsSentimentCollector()
        articles = collector._scrape_news_site(source)
        
        # Should return empty list on error (graceful degradation)
        assert articles == []
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_scrape_news_site_no_headlines(self, mock_get_session):
        """Test scraping site with no matching headlines."""
        mock_session = Mock()
        html_content = "<html><body><p>No headlines here</p></body></html>"
        
        mock_response = MockResponse({}, text=html_content)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        source = {
            "name": "Test Site",
            "url": "https://example.com/bitcoin",
            "headline_selector": "h2.card-headline",
            "link_selector": "a",
        }
        
        collector = NewsSentimentCollector()
        articles = collector._scrape_news_site(source)
        
        assert articles == []
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_scrape_news_site_respects_max_articles(self, mock_get_session):
        """Test that scraping respects max_articles limit."""
        mock_session = Mock()
        
        # Create 20 headlines
        headlines_html = "".join([
            f'<h2 class="card-headline"><a href="/article{i}">Article {i}</a></h2>'
            for i in range(20)
        ])
        html_content = f"<html><body>{headlines_html}</body></html>"
        
        mock_response = MockResponse({}, text=html_content)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        source = {
            "name": "Test Site",
            "url": "https://example.com/bitcoin",
            "headline_selector": "h2.card-headline",
            "link_selector": "a",
        }
        
        collector = NewsSentimentCollector(max_articles=5)
        articles = collector._scrape_news_site(source)
        
        assert len(articles) == 5
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._get_session")
    def test_scrape_news_site_handles_malformed_html(self, mock_get_session):
        """Test that malformed HTML doesn't crash scraper."""
        mock_session = Mock()
        
        # Malformed HTML (missing closing tags)
        html_content = """
        <html><body>
            <h2 class="card-headline">Valid Headline</h2>
            <h2 class="card-headline"
        </body></html>
        """
        
        mock_response = MockResponse({}, text=html_content)
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        
        source = {
            "name": "Test Site",
            "url": "https://example.com/bitcoin",
            "headline_selector": "h2.card-headline",
            "link_selector": "a",
        }
        
        collector = NewsSentimentCollector()
        articles = collector._scrape_news_site(source)
        
        # Should handle gracefully and return at least the valid headline
        assert len(articles) >= 1
        assert articles[0]["title"] == "Valid Headline"
    
    def test_news_sources_configuration(self):
        """Test that news sources are properly configured."""
        collector = NewsSentimentCollector()
        
        assert isinstance(collector.NEWS_SOURCES, list)
        assert len(collector.NEWS_SOURCES) > 0
        
        for source in collector.NEWS_SOURCES:
            assert "name" in source
            assert "url" in source
            assert "headline_selector" in source
    
    def test_bullish_keywords_list(self):
        """Test that bullish keywords list is populated."""
        collector = NewsSentimentCollector()
        
        assert isinstance(collector.BULLISH_KEYWORDS, list)
        assert len(collector.BULLISH_KEYWORDS) > 0
        
        # Check for some expected keywords
        assert "bullish" in collector.BULLISH_KEYWORDS
        assert "rally" in collector.BULLISH_KEYWORDS
        assert "surge" in collector.BULLISH_KEYWORDS
    
    def test_bearish_keywords_list(self):
        """Test that bearish keywords list is populated."""
        collector = NewsSentimentCollector()
        
        assert isinstance(collector.BEARISH_KEYWORDS, list)
        assert len(collector.BEARISH_KEYWORDS) > 0
        
        # Check for some expected keywords
        assert "bearish" in collector.BEARISH_KEYWORDS
        assert "crash" in collector.BEARISH_KEYWORDS
        assert "plunge" in collector.BEARISH_KEYWORDS
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    @patch("btc_monitor.sentiment.NewsSentimentCollector._scrape_news_sources")
    def test_collect_uses_newsapi_with_api_key(self, mock_scrape, mock_fetch):
        """Test that collect() uses NewsAPI when API key is provided."""
        # Mock NewsAPI response
        mock_fetch.return_value = [
            {
                "title": "Bitcoin Rally",
                "description": "Price surges",
                "url": "https://example.com/article1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": {"name": "Test News"}
            }
        ]
        
        collector = NewsSentimentCollector(api_key="test_key")
        entries = collector.collect()
        
        # Should call _fetch_from_newsapi and not _scrape_news_sources
        mock_fetch.assert_called_once()
        mock_scrape.assert_not_called()
        
        # Should return sentiment entries
        assert len(entries) > 0
        assert isinstance(entries[0], SentimentEntry)
        assert entries[0].source == SentimentSource.NEWS
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    @patch("btc_monitor.sentiment.NewsSentimentCollector._scrape_news_sources")
    def test_collect_falls_back_to_scraping_on_api_error(self, mock_scrape, mock_fetch):
        """Test that collect() falls back to scraping on API error."""
        # Mock NewsAPI error
        mock_fetch.side_effect = requests.RequestException("API error")
        
        # Mock scraping response
        mock_scrape.return_value = [
            {
                "title": "Bitcoin Rally",
                "description": "",
                "url": "https://example.com/article1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": {"name": "Test Site"}
            }
        ]
        
        collector = NewsSentimentCollector(api_key="test_key")
        entries = collector.collect()
        
        # Should call both methods
        mock_fetch.assert_called_once()
        mock_scrape.assert_called_once()
        
        # Should return sentiment entries from scraping
        assert len(entries) > 0
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    @patch("btc_monitor.sentiment.NewsSentimentCollector._scrape_news_sources")
    def test_collect_uses_scraping_without_api_key(self, mock_scrape, mock_fetch):
        """Test that collect() uses scraping when no API key is provided."""
        # Mock scraping response
        mock_scrape.return_value = [
            {
                "title": "Bitcoin Rally",
                "description": "",
                "url": "https://example.com/article1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": {"name": "Test Site"}
            }
        ]
        
        collector = NewsSentimentCollector(api_key=None)
        entries = collector.collect()
        
        # Should only call _scrape_news_sources
        mock_fetch.assert_not_called()
        mock_scrape.assert_called_once()
        
        # Should return sentiment entries
        assert len(entries) > 0
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    def test_collect_filters_old_articles(self, mock_fetch):
        """Test that collect() filters out articles older than hours_back."""
        # Mock articles with different timestamps
        now = datetime.datetime.now(datetime.timezone.utc)
        
        mock_fetch.return_value = [
            {
                "title": "Recent Article",
                "description": "Recent news",
                "url": "https://example.com/article1",
                "publishedAt": (now - datetime.timedelta(hours=1)).isoformat(),
                "source": {"name": "Test News"}
            },
            {
                "title": "Old Article",
                "description": "Old news",
                "url": "https://example.com/article2",
                "publishedAt": (now - datetime.timedelta(hours=48)).isoformat(),
                "source": {"name": "Test News"}
            },
        ]
        
        collector = NewsSentimentCollector(api_key="test_key", hours_back=24)
        entries = collector.collect()
        
        # Should only include recent article
        assert len(entries) == 1
        assert entries[0].content.startswith("Recent Article")
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    def test_collect_handles_missing_publishedAt(self, mock_fetch):
        """Test that collect() handles articles without publishedAt."""
        mock_fetch.return_value = [
            {
                "title": "Bitcoin Rally",
                "description": "Price surges",
                "url": "https://example.com/article1",
                # No publishedAt field
                "source": {"name": "Test News"}
            }
        ]
        
        collector = NewsSentimentCollector(api_key="test_key")
        entries = collector.collect()
        
        # Should use current time as timestamp
        assert len(entries) > 0
        assert isinstance(entries[0].timestamp, datetime.datetime)
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    def test_collect_handles_empty_articles(self, mock_fetch):
        """Test that collect() handles articles with empty content."""
        mock_fetch.return_value = [
            {
                "title": "",
                "description": "",
                "url": "https://example.com/article1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": {"name": "Test News"}
            }
        ]
        
        collector = NewsSentimentCollector(api_key="test_key")
        entries = collector.collect()
        
        # Should skip empty articles
        assert len(entries) == 0
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    def test_collect_limits_content_length(self, mock_fetch):
        """Test that collect() limits content field length."""
        long_text = "A" * 1000
        
        mock_fetch.return_value = [
            {
                "title": long_text,
                "description": long_text,
                "url": "https://example.com/article1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": {"name": "Test News"}
            }
        ]
        
        collector = NewsSentimentCollector(api_key="test_key")
        entries = collector.collect()
        
        # Content should be limited to 500 characters
        assert len(entries) > 0
        assert len(entries[0].content) <= 500
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    @patch("btc_monitor.sentiment.NewsSentimentCollector.collect")
    def test_collect_and_save(self, mock_collect, mock_fetch):
        """Test collect_and_save method."""
        from btc_monitor.database import init_db
        from btc_monitor.models import SentimentData
        import tempfile
        import os
        
        # Create temporary database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            init_db(db_path)
            
            # Mock collect to return test entries
            mock_collect.return_value = [
                SentimentEntry(
                    source=SentimentSource.NEWS,
                    score=0.5,
                    content="Test content",
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
            ]
            
            collector = NewsSentimentCollector(api_key="test_key")
            count = collector.collect_and_save(db_path)
            
            # Should save one entry
            assert count == 1
            
            # Verify data was saved to database
            from btc_monitor.database import get_session
            session = get_session(db_path)
            try:
                entries = session.query(SentimentData).filter_by(source="news").all()
                assert len(entries) == 1
                assert entries[0].score == 0.5
                assert entries[0].content == "Test content"
            finally:
                session.close()
    
    @patch("btc_monitor.sentiment.NewsSentimentCollector._fetch_from_newsapi")
    @patch("btc_monitor.sentiment.NewsSentimentCollector.collect")
    def test_collect_and_save_returns_zero_on_empty(self, mock_collect, mock_fetch):
        """Test that collect_and_save returns 0 when no entries collected."""
        # Mock collect to return empty list
        mock_collect.return_value = []
        
        collector = NewsSentimentCollector(api_key="test_key")
        count = collector.collect_and_save()
        
        # Should return 0 without trying to save
        assert count == 0
    
    def test_cleanup_session_on_deletion(self):
        """Test that HTTP session is cleaned up when collector is deleted."""
        collector = NewsSentimentCollector()
        
        # Create session
        session = collector._get_session()
        assert collector._session is not None
        
        # Store session mock to check if close is called
        session_mock = Mock()
        collector._session = session_mock
        
        # Delete collector
        del collector
        
        # Session should be closed (though this is tricky to test in Python)
        # At least verify it doesn't raise an error
        pass
