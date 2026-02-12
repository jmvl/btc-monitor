"""Tests for research sentiment collector."""

import datetime
from typing import List
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from btc_monitor.sentiment import (
    SentimentEntry,
    SentimentSource,
    ResearchCollector,
)


class MockResponse:
    """Mock requests.Response object for testing."""
    
    def __init__(self, json_data: dict = None, status_code: int = 200, text: str = ""):
        self._json_data = json_data or {}
        self.status_code = status_code
        self._text = text
        self.headers = {"Content-Type": "text/html"}
    
    def json(self):
        return self._json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")
    
    @property
    def text(self):
        return self._text


class TestResearchCollector:
    """Test suite for ResearchCollector."""
    
    def test_research_collector_initialization(self):
        """Test that ResearchCollector can be initialized with parameters."""
        collector = ResearchCollector(
            max_items=20,
            hours_back=24,
            current_price=50000.0,
        )
        
        assert collector.max_items == 20
        assert collector.hours_back == 24
        assert collector.current_price == 50000.0
    
    def test_research_collector_default_values(self):
        """Test that ResearchCollector has correct default values."""
        collector = ResearchCollector()
        
        assert collector.max_items == 30
        assert collector.hours_back == 48
        assert collector.current_price is None
    
    def test_research_collector_cutoff_time(self):
        """Test that cutoff_time is calculated correctly."""
        hours_back = 48
        collector = ResearchCollector(hours_back=hours_back)
        
        expected_cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_back)
        
        # Allow 1 second tolerance for test execution time
        time_diff = abs((collector.cutoff_time - expected_cutoff).total_seconds())
        assert time_diff < 1.0
    
    def test_analyze_sentiment_bullish(self):
        """Test sentiment analysis with bullish keywords."""
        collector = ResearchCollector()
        
        # Test single bullish keyword
        score = collector._analyze_sentiment("Bitcoin price surges to new heights")
        assert score > 0
        
        # Test multiple bullish keywords
        score = collector._analyze_sentiment("Bullish rally breakout gains momentum")
        assert score > 0
        
        # Test specific keywords
        assert collector._analyze_sentiment("Strong support levels") > 0
        assert collector._analyze_sentiment("Record high reached") > 0
        assert collector._analyze_sentiment("Upgrade to buy rating") > 0
        assert collector._analyze_sentiment("Outperform expected") > 0
    
    def test_analyze_sentiment_bearish(self):
        """Test sentiment analysis with bearish keywords."""
        collector = ResearchCollector()
        
        # Test single bearish keyword
        score = collector._analyze_sentiment("Bitcoin crashes today")
        assert score < 0
        
        # Test multiple bearish keywords
        score = collector._analyze_sentiment("Bear market crash plunge losses")
        assert score < 0
        
        # Test specific keywords
        assert collector._analyze_sentiment("Support broken") < 0
        assert collector._analyze_sentiment("Decline continues") < 0
        assert collector._analyze_sentiment("Downgrade to sell") < 0
        assert collector._analyze_sentiment("Underperform expected") < 0
    
    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis with neutral text."""
        collector = ResearchCollector()
        
        # Empty text
        assert collector._analyze_sentiment("") == 0.0
        assert collector._analyze_sentiment(None) == 0.0
        
        # Text with no sentiment keywords
        score = collector._analyze_sentiment("Bitcoin price is $50,000")
        assert score == 0.0
        
        # Mixed sentiment (balanced)
        score = collector._analyze_sentiment("Bullish gains but bearish losses")
        # Should be close to 0 since equal counts
        assert -0.1 < score < 0.1
    
    def test_analyze_sentiment_case_insensitive(self):
        """Test that sentiment analysis is case-insensitive."""
        collector = ResearchCollector()
        
        score1 = collector._analyze_sentiment("BULLISH RALLY")
        score2 = collector._analyze_sentiment("bullish rally")
        score3 = collector._analyze_sentiment("BuLlIsH rAlLy")
        
        assert score1 == score2 == score3
    
    def test_extract_price_target_dollar_format(self):
        """Test price target extraction from dollar format."""
        collector = ResearchCollector()
        
        # Simple dollar format
        target = collector._extract_price_target("BTC to $100,000")
        assert target == 100000.0
        
        # Dollar without commas
        target = collector._extract_price_target("Target: $50000")
        assert target == 50000.0
        
        # Dollar with decimal
        target = collector._extract_price_target("Price: $98,500.50")
        assert target == 98500.5
    
    def test_extract_price_target_k_format(self):
        """Test price target extraction from K format."""
        collector = ResearchCollector()
        
        # K format
        target = collector._extract_price_target("BTC to 100k")
        assert target == 100000.0
        
        # K with decimal
        target = collector._extract_price_target("Target: 98.5k")
        assert target == 98500.0
    
    def test_extract_price_target_m_format(self):
        """Test price target extraction from M format."""
        collector = ResearchCollector()
        
        # M format
        target = collector._extract_price_target("BTC to 1M")
        assert target == 1_000_000.0
        
        # M with decimal
        target = collector._extract_price_target("Target: 0.1M")
        assert target == 100_000.0
    
    def test_extract_price_target_no_target(self):
        """Test price target extraction when no target present."""
        collector = ResearchCollector()
        
        # No price target
        target = collector._extract_price_target("Bitcoin is doing well today")
        assert target is None
        
        # Invalid format
        target = collector._extract_price_target("Price: ABC")
        assert target is None
        
        # Empty text
        target = collector._extract_price_target("")
        assert target is None
        target = collector._extract_price_target(None)
        assert target is None
    
    def test_score_price_target_bullish(self):
        """Test price target scoring for bullish targets."""
        current_price = 50000.0
        collector = ResearchCollector(current_price=current_price)
        
        # 10% above current price
        score = collector._score_price_target(55000.0)
        assert score > 0
        assert score < 1.0
        
        # 50% above current price
        score = collector._score_price_target(75000.0)
        assert score > 0
        assert score < 1.0
        
        # 100% above current price
        score = collector._score_price_target(100000.0)
        assert score > 0.9  # Should be very bullish
    
    def test_score_price_target_bearish(self):
        """Test price target scoring for bearish targets."""
        current_price = 50000.0
        collector = ResearchCollector(current_price=current_price)
        
        # 10% below current price
        score = collector._score_price_target(45000.0)
        assert score < 0
        assert score > -1.0
        
        # 50% below current price
        score = collector._score_price_target(25000.0)
        assert score < 0
        assert score > -1.0
        
        # 90% below current price
        score = collector._score_price_target(5000.0)
        assert score < -0.9  # Should be very bearish
    
    def test_score_price_target_neutral(self):
        """Test price target scoring for neutral targets."""
        current_price = 50000.0
        collector = ResearchCollector(current_price=current_price)
        
        # Same as current price
        score = collector._score_price_target(50000.0)
        assert score == 0.0
    
    def test_score_price_target_no_current_price(self):
        """Test price target scoring when current_price is not set."""
        collector = ResearchCollector(current_price=None)
        
        # Should return 0.0 when no current price
        score = collector._score_price_target(100000.0)
        assert score == 0.0
    
    def test_http_session_creation(self):
        """Test HTTP session creation and reuse."""
        collector = ResearchCollector()
        
        session1 = collector._get_session()
        session2 = collector._get_session()
        
        assert session1 is session2  # Should be same instance
        assert "User-Agent" in session1.headers
    
    def test_bullish_keywords_list(self):
        """Test that bullish keywords are defined."""
        assert hasattr(ResearchCollector, "BULLISH_KEYWORDS")
        assert len(ResearchCollector.BULLISH_KEYWORDS) > 0
        
        # Check some expected keywords
        assert "bullish" in ResearchCollector.BULLISH_KEYWORDS
        assert "rally" in ResearchCollector.BULLISH_KEYWORDS
        assert "upgrade" in ResearchCollector.BULLISH_KEYWORDS
        assert "buy" in ResearchCollector.BULLISH_KEYWORDS
    
    def test_bearish_keywords_list(self):
        """Test that bearish keywords are defined."""
        assert hasattr(ResearchCollector, "BEARISH_KEYWORDS")
        assert len(ResearchCollector.BEARISH_KEYWORDS) > 0
        
        # Check some expected keywords
        assert "bearish" in ResearchCollector.BEARISH_KEYWORDS
        assert "crash" in ResearchCollector.BEARISH_KEYWORDS
        assert "downgrade" in ResearchCollector.BEARISH_KEYWORDS
        assert "sell" in ResearchCollector.BEARISH_KEYWORDS
    
    def test_research_sources_configuration(self):
        """Test that research sources are configured."""
        assert hasattr(ResearchCollector, "RESEARCH_SOURCES")
        assert len(ResearchCollector.RESEARCH_SOURCES) > 0
        
        # Check required fields
        source = ResearchCollector.RESEARCH_SOURCES[0]
        assert "name" in source
        assert "url" in source
        assert "idea_selector" in source
    
    @patch("btc_monitor.sentiment.requests.Session.get")
    def test_scrape_research_site_success(self, mock_get):
        """Test successful scraping of a research site."""
        # Mock HTML response
        html = """
        <div class="tv-widget-idea__title-row">
            <a href="/idea/btc-bullish-123">BTC targets $100,000</a>
            <span class="tv-widget-idea__author">AnalystOne</span>
        </div>
        <div class="tv-widget-idea__title-row">
            <a href="/idea/btc-bearish-456">BTC bearish outlook</a>
            <span class="tv-widget-idea__author">AnalystTwo</span>
        </div>
        """
        mock_get.return_value = MockResponse(text=html)
        
        collector = ResearchCollector(max_items=10)
        source = {
            "name": "Test Site",
            "url": "https://example.com",
            "idea_selector": "div.tv-widget-idea__title-row",
            "author_selector": "span.tv-widget-idea__author",
        }
        
        items = collector._scrape_research_site(source)
        
        assert len(items) == 2
        assert items[0]["title"] == "BTC targets $100,000"
        assert items[0]["author"] == "AnalystOne"
        assert items[1]["title"] == "BTC bearish outlook"
        assert items[1]["author"] == "AnalystTwo"
    
    @patch("btc_monitor.sentiment.requests.Session.get")
    def test_scrape_research_site_http_error(self, mock_get):
        """Test scraping with HTTP error."""
        mock_get.side_effect = requests.HTTPError("500 Internal Server Error")
        
        collector = ResearchCollector()
        source = {
            "name": "Test Site",
            "url": "https://example.com",
            "idea_selector": "div.test",
        }
        
        items = collector._scrape_research_site(source)
        
        # Should return empty list on error
        assert len(items) == 0
    
    @patch("btc_monitor.sentiment.requests.Session.get")
    def test_scrape_research_site_respects_max_items(self, mock_get):
        """Test that scraping respects max_items limit."""
        # Generate many items
        html = "\n".join([
            f'<div class="test"><a href="/idea-{i}">BTC target {i}</a></div>'
            for i in range(20)
        ])
        mock_get.return_value = MockResponse(text=html)
        
        collector = ResearchCollector(max_items=5)
        source = {
            "name": "Test Site",
            "url": "https://example.com",
            "idea_selector": "div.test",
        }
        
        items = collector._scrape_research_site(source)
        
        assert len(items) == 5
    
    @patch("btc_monitor.sentiment.requests.Session.get")
    def test_scrape_research_site_relative_urls(self, mock_get):
        """Test that relative URLs are handled correctly."""
        html = """
        <div class="test">
            <a href="/relative-path">BTC analysis</a>
        </div>
        """
        mock_get.return_value = MockResponse(text=html)
        
        collector = ResearchCollector()
        source = {
            "name": "Test Site",
            "url": "https://example.com/bitcoin",
            "idea_selector": "div.test",
        }
        
        items = collector._scrape_research_site(source)
        
        assert len(items) == 1
        assert items[0]["url"].startswith("https://example.com")
    
    @patch("btc_monitor.sentiment.ResearchCollector.RESEARCH_SOURCES", new=[
        {"name": "Source 1", "url": "https://example1.com", "idea_selector": "div.test"},
        {"name": "Source 2", "url": "https://example2.com", "idea_selector": "div.test"},
    ])
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_site")
    def test_scrape_research_sources_multiple(self, mock_scrape):
        """Test scraping multiple research sources."""
        mock_scrape.side_effect = [
            [{"title": "Item 1", "author": "Author 1"}],
            [{"title": "Item 2", "author": "Author 2"}],
        ]
        
        collector = ResearchCollector(max_items=10)
        items = collector._scrape_research_sources()
        
        assert len(items) == 2
        assert items[0]["title"] == "Item 1"
        assert items[1]["title"] == "Item 2"
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_site")
    def test_scrape_research_sources_respects_limit(self, mock_scrape):
        """Test that _scrape_research_sources respects max_items across all sources."""
        # Return more items than limit
        mock_scrape.side_effect = [
            [{"title": f"Item {i}", "author": f"Author {i}"} for i in range(20)],
            [{"title": f"Item {i}", "author": f"Author {i}"} for i in range(20)],
        ]
        
        collector = ResearchCollector(max_items=10)
        items = collector._scrape_research_sources()
        
        # Should be limited to max_items
        assert len(items) == 10
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_with_price_target(self, mock_scrape):
        """Test collect() with price target analysis."""
        mock_scrape.return_value = [
            {
                "title": "BTC targets $100,000 in Q4",
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            {
                "title": "Bitcoin could drop to $30,000",
                "author": "Analyst Two",
                "url": "https://example.com/2",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ]
        
        collector = ResearchCollector(current_price=50000.0)
        entries = collector.collect()
        
        assert len(entries) == 2
        assert all(entry.source == SentimentSource.RESEARCH for entry in entries)
        
        # First entry should be bullish ($100k > $50k)
        assert entries[0].score > 0
        assert "Analyst One" in entries[0].content
        
        # Second entry should be bearish ($30k < $50k)
        assert entries[1].score < 0
        assert "Analyst Two" in entries[1].content
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_with_keywords_only(self, mock_scrape):
        """Test collect() with keyword sentiment (no price targets)."""
        mock_scrape.return_value = [
            {
                "title": "Bullish rally expected for Bitcoin",
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            {
                "title": "Bearish outlook continues",
                "author": "Analyst Two",
                "url": "https://example.com/2",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ]
        
        collector = ResearchCollector(current_price=50000.0)
        entries = collector.collect()
        
        assert len(entries) == 2
        assert all(entry.source == SentimentSource.RESEARCH for entry in entries)
        
        # First entry should be bullish (keywords)
        assert entries[0].score > 0
        
        # Second entry should be bearish (keywords)
        assert entries[1].score < 0
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_filters_by_timestamp(self, mock_scrape):
        """Test that collect() filters items by timestamp."""
        old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
        recent_time = datetime.datetime.now(datetime.timezone.utc)
        
        mock_scrape.return_value = [
            {
                "title": "Old research",
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": old_time.isoformat(),
            },
            {
                "title": "Recent research",
                "author": "Analyst Two",
                "url": "https://example.com/2",
                "publishedAt": recent_time.isoformat(),
            },
        ]
        
        collector = ResearchCollector(hours_back=24)
        entries = collector.collect()
        
        # Only recent item should be included
        assert len(entries) == 1
        assert entries[0].content == "By Analyst Two. Recent research"
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_empty_title(self, mock_scrape):
        """Test that collect() skips items with empty titles."""
        mock_scrape.return_value = [
            {
                "title": "",
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            {
                "title": "Valid research",
                "author": "Analyst Two",
                "url": "https://example.com/2",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ]
        
        collector = ResearchCollector()
        entries = collector.collect()
        
        # Only valid item should be included
        assert len(entries) == 1
        assert entries[0].content == "By Analyst Two. Valid research"
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_content_length_limit(self, mock_scrape):
        """Test that collect() limits content length."""
        long_title = "BTC " * 200  # Long title
        mock_scrape.return_value = [
            {
                "title": long_title,
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ]
        
        collector = ResearchCollector()
        entries = collector.collect()
        
        assert len(entries) == 1
        assert len(entries[0].content) <= 500
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_handles_processing_errors(self, mock_scrape):
        """Test that collect() handles processing errors gracefully."""
        # Mix of valid and invalid items
        mock_scrape.return_value = [
            {
                "title": "Valid research",
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            {
                "title": None,  # Invalid title
                "author": "Analyst Two",
                "url": "https://example.com/2",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ]
        
        collector = ResearchCollector()
        entries = collector.collect()
        
        # Should skip invalid item and process valid one
        assert len(entries) == 1
        assert entries[0].content == "By Analyst One. Valid research"
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_no_current_price(self, mock_scrape):
        """Test collect() when current_price is not set."""
        mock_scrape.return_value = [
            {
                "title": "BTC targets $100,000",
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ]
        
        collector = ResearchCollector(current_price=None)
        entries = collector.collect()
        
        # Should fall back to keyword analysis
        assert len(entries) == 1
        # Score should be based on keywords only, not price target
        # (since current_price is None, price target scoring returns 0.0)
        # But "targets" might have some weak bullish sentiment
        assert -1.0 <= entries[0].score <= 1.0
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_no_items(self, mock_scrape):
        """Test collect() when no items are scraped."""
        mock_scrape.return_value = []
        
        collector = ResearchCollector()
        entries = collector.collect()
        
        assert len(entries) == 0
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_and_save(self, mock_scrape, tmp_path):
        """Test collect_and_save() database integration."""
        mock_scrape.return_value = [
            {
                "title": "BTC targets $100,000",
                "author": "Analyst One",
                "url": "https://example.com/1",
                "publishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        ]
        
        collector = ResearchCollector(current_price=50000.0)
        
        # Create temporary database
        db_path = tmp_path / "test.db"
        
        # Initialize database
        from btc_monitor.database import init_db
        init_db(str(db_path))
        
        # Collect and save
        count = collector.collect_and_save(str(db_path))
        
        assert count == 1
        
        # Verify data was saved
        from btc_monitor.database import get_session
        from btc_monitor.models import SentimentData
        
        session = get_session(str(db_path))
        try:
            sentiments = session.query(SentimentData).all()
            assert len(sentiments) == 1
            assert sentiments[0].source == "research"
            assert sentiments[0].score > 0  # Bullish price target
            assert "Analyst One" in sentiments[0].content
        finally:
            session.close()
    
    @patch("btc_monitor.sentiment.ResearchCollector._scrape_research_sources")
    def test_collect_and_save_empty_results(self, mock_scrape, tmp_path):
        """Test collect_and_save() with empty results."""
        mock_scrape.return_value = []
        
        collector = ResearchCollector()
        
        db_path = tmp_path / "test.db"
        count = collector.collect_and_save(str(db_path))
        
        assert count == 0
    
    @patch("btc_monitor.sentiment.requests.Session")
    def test_session_cleanup_on_deletion(self, mock_session_class):
        """Test that HTTP session is cleaned up on deletion."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        collector = ResearchCollector()
        collector._get_session()  # Create session
        
        # Delete collector
        del collector
        
        # Verify session was closed
        mock_session.close.assert_called_once()
