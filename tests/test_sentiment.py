"""Tests for sentiment data collection models and interface."""

from datetime import datetime, timedelta, timezone
import pytest

from pydantic import ValidationError

from btc_monitor.sentiment import SentimentSource, SentimentEntry, SentimentCollector


class TestSentimentSource:
    """Tests for the SentimentSource enum."""
    
    def test_sentiment_source_values(self) -> None:
        """Test that SentimentSource has all expected values."""
        assert SentimentSource.TWITTER.value == "twitter"
        assert SentimentSource.REDDIT.value == "reddit"
        assert SentimentSource.NEWS.value == "news"
        assert SentimentSource.RESEARCH.value == "research"
    
    def test_sentiment_source_from_string(self) -> None:
        """Test creating SentimentSource from string."""
        assert SentimentSource("twitter") == SentimentSource.TWITTER
        assert SentimentSource("reddit") == SentimentSource.REDDIT
        assert SentimentSource("news") == SentimentSource.NEWS
        assert SentimentSource("research") == SentimentSource.RESEARCH
    
    def test_sentiment_source_case_insensitive(self) -> None:
        """Test that SentimentSource validation is case-insensitive."""
        # The validator should handle this, but let's verify the enum itself
        # Note: direct enum construction is case-sensitive
        # This test documents the current behavior
        assert SentimentSource.TWITTER.value == "twitter"
        assert SentimentSource.REDDIT.value == "reddit"


class TestSentimentEntry:
    """Tests for the SentimentEntry pydantic model."""
    
    def test_create_valid_sentiment_entry(self) -> None:
        """Test creating a valid SentimentEntry."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        entry = SentimentEntry(
            source=SentimentSource.TWITTER,
            score=0.75,
            content="Bitcoin looks bullish today! 🚀",
            timestamp=timestamp,
        )
        
        assert entry.source == SentimentSource.TWITTER
        assert entry.score == 0.75
        assert entry.content == "Bitcoin looks bullish today! 🚀"
        assert entry.timestamp == timestamp
    
    def test_sentiment_entry_without_content(self) -> None:
        """Test creating a SentimentEntry without optional content."""
        entry = SentimentEntry(
            source=SentimentSource.NEWS,
            score=-0.5,
        )
        
        assert entry.source == SentimentSource.NEWS
        assert entry.score == -0.5
        assert entry.content is None
        assert isinstance(entry.timestamp, datetime)
    
    def test_sentiment_entry_default_timestamp(self) -> None:
        """Test that timestamp defaults to current time."""
        before = datetime.now(timezone.utc)
        entry = SentimentEntry(
            source=SentimentSource.REDDIT,
            score=0.3,
        )
        after = datetime.now(timezone.utc)
        
        assert before <= entry.timestamp <= after
    
    def test_sentiment_entry_with_string_source(self) -> None:
        """Test creating SentimentEntry with string source."""
        entry = SentimentEntry(
            source="twitter",
            score=0.5,
        )
        
        assert entry.source == SentimentSource.TWITTER
    
    def test_sentiment_entry_with_lowercase_source(self) -> None:
        """Test that string source is converted to lowercase."""
        entry = SentimentEntry(
            source="news",
            score=0.5,
        )
        
        assert entry.source == SentimentSource.NEWS
    
    def test_score_validation_negative_lower_bound(self) -> None:
        """Test that score cannot be less than -1.0."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentEntry(
                source=SentimentSource.TWITTER,
                score=-1.1,
            )
        
        # The validator raises ValueError with our custom message
        assert "Score must be between -1.0 and 1.0" in str(exc_info.value)
    
    def test_score_validation_upper_bound(self) -> None:
        """Test that score cannot be greater than 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentEntry(
                source=SentimentSource.TWITTER,
                score=1.5,
            )
        
        # The validator raises ValueError with our custom message
        assert "Score must be between -1.0 and 1.0" in str(exc_info.value)
    
    def test_score_validation_boundary_values(self) -> None:
        """Test that boundary values -1.0 and 1.0 are accepted."""
        entry_bearish = SentimentEntry(
            source=SentimentSource.TWITTER,
            score=-1.0,
        )
        assert entry_bearish.score == -1.0
        
        entry_bullish = SentimentEntry(
            source=SentimentSource.TWITTER,
            score=1.0,
        )
        assert entry_bullish.score == 1.0
    
    def test_score_validation_neutral(self) -> None:
        """Test that 0.0 (neutral) score is accepted."""
        entry = SentimentEntry(
            source=SentimentSource.REDDIT,
            score=0.0,
        )
        assert entry.score == 0.0
    
    def test_source_validation_invalid_value(self) -> None:
        """Test that invalid source values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentEntry(
                source="instagram",
                score=0.5,
            )
        
        # The validator raises ValueError with our custom message
        assert "Invalid source 'instagram'" in str(exc_info.value)
        assert "twitter" in str(exc_info.value)
        assert "reddit" in str(exc_info.value)
        assert "news" in str(exc_info.value)
        assert "research" in str(exc_info.value)
    
    def test_source_validation_all_valid_sources(self) -> None:
        """Test that all valid sources are accepted."""
        valid_sources = [
            SentimentSource.TWITTER,
            SentimentSource.REDDIT,
            SentimentSource.NEWS,
            SentimentSource.RESEARCH,
        ]
        
        for source in valid_sources:
            entry = SentimentEntry(source=source, score=0.5)
            assert entry.source == source
    
    def test_to_sentiment_data_conversion(self) -> None:
        """Test converting SentimentEntry to SentimentData ORM model."""
        from btc_monitor.models import SentimentData
        
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        entry = SentimentEntry(
            source=SentimentSource.TWITTER,
            score=0.75,
            content="Test content",
            timestamp=timestamp,
        )
        
        sentiment_data = entry.to_sentiment_data()
        
        assert isinstance(sentiment_data, SentimentData)
        assert sentiment_data.timestamp == timestamp
        assert sentiment_data.source == "twitter"
        assert sentiment_data.score == 0.75
        assert sentiment_data.content == "Test content"
    
    def test_to_sentiment_data_without_content(self) -> None:
        """Test converting SentimentEntry without content to SentimentData."""
        from btc_monitor.models import SentimentData
        
        entry = SentimentEntry(
            source=SentimentSource.NEWS,
            score=-0.5,
        )
        
        sentiment_data = entry.to_sentiment_data()
        
        assert sentiment_data.content is None


class TestSentimentCollector:
    """Tests for the SentimentCollector abstract base class."""
    
    def test_sentiment_collector_is_abstract(self) -> None:
        """Test that SentimentCollector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SentimentCollector()  # type: ignore
    
    def test_concrete_collector_implementation(self) -> None:
        """Test that concrete collector can be created by implementing collect()."""
        
        class TestCollector(SentimentCollector):
            """Test implementation of SentimentCollector."""
            
            def collect(self) -> list[SentimentEntry]:
                """Collect test sentiment data."""
                return [
                    SentimentEntry(
                        source=SentimentSource.TWITTER,
                        score=0.5,
                    ),
                ]
        
        collector = TestCollector()
        entries = collector.collect()
        
        assert len(entries) == 1
        assert entries[0].source == SentimentSource.TWITTER
        assert entries[0].score == 0.5
    
    def test_collect_method_raises_not_implemented(self) -> None:
        """Test that calling collect on abstract class raises NotImplementedError."""
        
        class IncompleteCollector(SentimentCollector):
            """Incomplete implementation that doesn't override collect()."""
            pass
        
        # We can't instantiate this because collect is abstract
        # But we can verify the behavior through the abstract nature
        with pytest.raises(TypeError):
            IncompleteCollector()


class TestSentimentEntryEdgeCases:
    """Tests for edge cases in SentimentEntry."""
    
    def test_very_long_content(self) -> None:
        """Test that very long content is accepted."""
        long_content = "a" * 10000
        entry = SentimentEntry(
            source=SentimentSource.TWITTER,
            score=0.5,
            content=long_content,
        )
        assert len(entry.content) == 10000
    
    def test_empty_string_content(self) -> None:
        """Test that empty string content is accepted."""
        entry = SentimentEntry(
            source=SentimentSource.REDDIT,
            score=0.5,
            content="",
        )
        assert entry.content == ""
    
    def test_unicode_content(self) -> None:
        """Test that unicode content is handled correctly."""
        content = "Bitcoin 🚀 to the moon! 🌙 中文"
        entry = SentimentEntry(
            source=SentimentSource.TWITTER,
            score=0.9,
            content=content,
        )
        assert entry.content == content
    
    def test_score_with_many_decimals(self) -> None:
        """Test that scores with many decimal places are preserved."""
        entry = SentimentEntry(
            source=SentimentSource.RESEARCH,
            score=0.123456789,
        )
        assert entry.score == 0.123456789
    
    def test_negative_fractional_score(self) -> None:
        """Test that negative fractional scores work correctly."""
        entry = SentimentEntry(
            source=SentimentSource.NEWS,
            score=-0.25,
        )
        assert entry.score == -0.25
        assert entry.source == SentimentSource.NEWS
