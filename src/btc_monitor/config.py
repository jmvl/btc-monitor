"""
Configuration management for BTC Monitor.

This module provides a Pydantic-based configuration system with:
- YAML file loading
- Environment variable overrides for sensitive data
- Validation and type checking
"""
from typing import Optional, Union
from pathlib import Path
import os

from pydantic import BaseModel, Field, ValidationInfo, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class TwitterConfig(BaseModel):
    """Twitter/X API configuration."""
    consumer_key: str = ""
    consumer_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    bearer_token: str = ""


class NewsConfig(BaseModel):
    """News API configuration."""
    api_key: str = ""
    max_articles: int = Field(default=50, ge=1, le=100)
    hours_back: int = Field(default=24, ge=1, le=168)  # Max 1 week


class ResearchConfig(BaseModel):
    """Research data collection configuration."""
    max_items: int = Field(default=30, ge=1, le=100)
    hours_back: int = Field(default=48, ge=1, le=336)  # Max 2 weeks


class DatabaseConfig(BaseModel):
    """Database configuration."""
    url: str = "sqlite:///btc_monitor.db"


class DataSourcesConfig(BaseModel):
    """Data sources configuration."""
    update_interval: int = Field(default=300, ge=1, le=3600)  # Max 1 hour
    symbols: list[str] = Field(default_factory=lambda: ["BTC-USD"])

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        """Validate that symbols list is not empty."""
        if not v:
            raise ValueError("At least one symbol must be specified")
        return v


class AnalysisConfig(BaseModel):
    """Technical analysis configuration."""
    rsi_period: int = Field(default=14, ge=2, le=50)
    macd_fast: int = Field(default=12, ge=1, le=50)
    macd_slow: int = Field(default=26, ge=1, le=100)
    macd_signal: int = Field(default=9, ge=1, le=50)
    moving_averages: list[int] = Field(default_factory=lambda: [20, 50, 200])

    @field_validator("moving_averages")
    @classmethod
    def validate_moving_averages(cls, v: list[int]) -> list[int]:
        """Validate moving averages list."""
        if not v:
            raise ValueError("At least one moving average period must be specified")
        if any(ma < 1 for ma in v):
            raise ValueError("All moving average periods must be positive")
        return sorted(v)  # Keep them sorted

    @field_validator("macd_slow")
    @classmethod
    def validate_macd_slow(cls, v: int, info: ValidationInfo) -> int:
        """Ensure slow period is greater than fast period."""
        if "macd_fast" in info.data and v <= info.data["macd_fast"]:
            raise ValueError("MACD slow period must be greater than fast period")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    file: str = "btc_monitor.log"
    error_file: str = "error.log"

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()


class Config(BaseSettings):
    """
    Main configuration class for BTC Monitor.

    Loads configuration from YAML file and supports environment variable overrides.
    Environment variables should be prefixed with BTC_MONITOR_ (e.g., BTC_MONITOR_TWITTER_API_KEY).
    """

    # Configuration sections
    twitter: TwitterConfig = Field(default_factory=TwitterConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    model_config = SettingsConfigDict(
        env_prefix="BTC_MONITOR_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Convenience properties for backward compatibility
    @property
    def twitter_api_key(self) -> str:
        """Get Twitter API bearer token (used as API key)."""
        return self.twitter.bearer_token

    @property
    def news_api_key(self) -> str:
        """Get News API key."""
        return self.news.api_key

    @property
    def refresh_interval(self) -> int:
        """Get data refresh interval in seconds."""
        return self.data_sources.update_interval

    @property
    def rsi_overbought(self) -> float:
        """Get RSI overbought threshold."""
        return 70.0

    @property
    def rsi_oversold(self) -> float:
        """Get RSI oversold threshold."""
        return 30.0

    @property
    def db_path(self) -> str:
        """Get database path from database URL."""
        if self.database.url.startswith("sqlite:///"):
            return self.database.url.replace("sqlite:///", "")
        return self.database.url

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self.logging.level

    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> "Config":
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
        try:
            import yaml
        except ImportError as e:
            raise ImportError(
                "PyYAML is required to load configuration from YAML. "
                "Install it with: pip install pyyaml"
            ) from e

        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {config_path}: {e}") from e

        if config_data is None:
            raise ValueError(f"Configuration file is empty: {config_path}")

        try:
            # Use model_validate to properly load from YAML with env var support
            # The env vars from BaseSettings will be merged with YAML data
            return cls.model_validate(config_data)
        except ValidationError as e:
            # Reraise with helpful message
            raise e

    def save_yaml(self, config_path: Union[str, Path]) -> None:
        """
        Save configuration to a YAML file.

        Args:
            config_path: Path where to save the YAML configuration file.

        Raises:
            ValueError: If PyYAML is not installed.
        """
        try:
            import yaml
        except ImportError as e:
            raise ImportError(
                "PyYAML is required to save configuration to YAML. "
                "Install it with: pip install pyyaml"
            ) from e

        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.model_dump(mode="json", exclude_none=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )


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
    if config_path is None:
        # Try to find config.yaml in common locations
        for search_path in [
            "config/config.yaml",
            "config.yaml",
            "/etc/btc_monitor/config.yaml",
        ]:
            if Path(search_path).exists():
                config_path = search_path
                break
        else:
            raise FileNotFoundError(
                "Configuration file not found. "
                "Please provide a config path or place config.yaml in config/ directory."
            )

    return Config.from_yaml(config_path)
