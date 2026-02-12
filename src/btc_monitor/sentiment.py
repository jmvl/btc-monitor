"""Sentiment data collection models and interface."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


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
