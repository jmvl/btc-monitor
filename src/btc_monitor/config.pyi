"""
Configuration management for BTC Monitor.

This module provides a Pydantic-based configuration system with:
- YAML file loading
- Environment variable overrides for sensitive data
- Validation and type checking
"""
from typing import Optional, Union, TYPE_CHECKING
from pathlib import Path
from pydantic import ValidationError

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic_settings import BaseSettings


class TwitterConfig(BaseModel):
    """Twitter/X API configuration."""
    consumer_key: str
    consumer_secret: str
    access_token: str
    access_token_secret: str
    bearer_token: str


class NewsConfig(BaseModel):
    """News API configuration."""
    api_key: str
    max_articles: int
    hours_back: int


class ResearchConfig(BaseModel):
    """Research data collection configuration."""
    max_items: int
    hours_back: int


class DatabaseConfig(BaseModel):
    """Database configuration."""
    url: str


class DataSourcesConfig(BaseModel):
    """Data sources configuration."""
    update_interval: int
    symbols: list[str]


class AnalysisConfig(BaseModel):
    """Technical analysis configuration."""
    rsi_period: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    moving_averages: list[int]


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str
    file: str


class Config:
    """
    Main configuration class for BTC Monitor.

    Loads configuration from YAML file and supports environment variable overrides.
    Environment variables should be prefixed with BTC_MONITOR_ (e.g., BTC_MONITOR_TWITTER_API_KEY).
    """

    # Configuration sections
    twitter: TwitterConfig
    news: NewsConfig
    research: ResearchConfig
    database: DatabaseConfig
    data_sources: DataSourcesConfig
    analysis: AnalysisConfig
    logging: LoggingConfig

    # Convenience properties for backward compatibility
    @property
    def twitter_api_key(self) -> str: ...

    @property
    def news_api_key(self) -> str: ...

    @property
    def refresh_interval(self) -> int: ...

    @property
    def rsi_overbought(self) -> float: ...

    @property
    def rsi_oversold(self) -> float: ...

    @property
    def db_path(self) -> str: ...

    @property
    def log_level(self) -> str: ...

    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> Config:
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            Config instance loaded from the file.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValidationError: If the configuration data is invalid.
            ValueError: If the YAML format is invalid.
        """
        ...

    def save_yaml(self, config_path: Union[str, Path]) -> None:
        """
        Save configuration to a YAML file.

        Args:
            config_path: Path where to save the YAML configuration file.

        Raises:
            ValueError: If PyYAML is not installed.
        """
        ...


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the configuration file. If None, looks for config/config.yaml
                    in the current directory.

    Returns:
        Loaded Config instance.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValidationError: If the configuration data is invalid.
    """
    ...
