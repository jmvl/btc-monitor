"""
Tests for configuration management system.
"""
import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from btc_monitor.config import (
    Config,
    TwitterConfig,
    NewsConfig,
    ResearchConfig,
    DatabaseConfig,
    DataSourcesConfig,
    AnalysisConfig,
    LoggingConfig,
    load_config,
)


class TestTwitterConfig:
    """Tests for TwitterConfig."""

    def test_default_values(self):
        """Test TwitterConfig with default values."""
        config = TwitterConfig()
        assert config.consumer_key == ""
        assert config.consumer_secret == ""
        assert config.access_token == ""
        assert config.access_token_secret == ""
        assert config.bearer_token == ""

    def test_custom_values(self):
        """Test TwitterConfig with custom values."""
        config = TwitterConfig(
            consumer_key="test_key",
            consumer_secret="test_secret",
            access_token="test_token",
            access_token_secret="test_token_secret",
            bearer_token="test_bearer",
        )
        assert config.consumer_key == "test_key"
        assert config.bearer_token == "test_bearer"


class TestNewsConfig:
    """Tests for NewsConfig."""

    def test_default_values(self):
        """Test NewsConfig with default values."""
        config = NewsConfig()
        assert config.api_key == ""
        assert config.max_articles == 50
        assert config.hours_back == 24

    def test_custom_values(self):
        """Test NewsConfig with custom values."""
        config = NewsConfig(api_key="test_key", max_articles=25, hours_back=12)
        assert config.api_key == "test_key"
        assert config.max_articles == 25
        assert config.hours_back == 12

    def test_max_articles_validation(self):
        """Test NewsConfig max_articles validation."""
        # Valid values
        NewsConfig(max_articles=1)
        NewsConfig(max_articles=100)
        # Invalid: too low
        with pytest.raises(ValidationError):
            NewsConfig(max_articles=0)
        # Invalid: too high
        with pytest.raises(ValidationError):
            NewsConfig(max_articles=101)

    def test_hours_back_validation(self):
        """Test NewsConfig hours_back validation."""
        # Valid values
        NewsConfig(hours_back=1)
        NewsConfig(hours_back=168)
        # Invalid: too low
        with pytest.raises(ValidationError):
            NewsConfig(hours_back=0)
        # Invalid: too high
        with pytest.raises(ValidationError):
            NewsConfig(hours_back=169)


class TestResearchConfig:
    """Tests for ResearchConfig."""

    def test_default_values(self):
        """Test ResearchConfig with default values."""
        config = ResearchConfig()
        assert config.max_items == 30
        assert config.hours_back == 48

    def test_custom_values(self):
        """Test ResearchConfig with custom values."""
        config = ResearchConfig(max_items=15, hours_back=24)
        assert config.max_items == 15
        assert config.hours_back == 24

    def test_max_items_validation(self):
        """Test ResearchConfig max_items validation."""
        # Valid values
        ResearchConfig(max_items=1)
        ResearchConfig(max_items=100)
        # Invalid: too low
        with pytest.raises(ValidationError):
            ResearchConfig(max_items=0)
        # Invalid: too high
        with pytest.raises(ValidationError):
            ResearchConfig(max_items=101)

    def test_hours_back_validation(self):
        """Test ResearchConfig hours_back validation."""
        # Valid values
        ResearchConfig(hours_back=1)
        ResearchConfig(hours_back=336)
        # Invalid: too low
        with pytest.raises(ValidationError):
            ResearchConfig(hours_back=0)
        # Invalid: too high
        with pytest.raises(ValidationError):
            ResearchConfig(hours_back=337)


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_default_value(self):
        """Test DatabaseConfig with default value."""
        config = DatabaseConfig()
        assert config.url == "sqlite:///btc_monitor.db"

    def test_custom_value(self):
        """Test DatabaseConfig with custom value."""
        config = DatabaseConfig(url="postgresql://user:pass@localhost/db")
        assert config.url == "postgresql://user:pass@localhost/db"


class TestDataSourcesConfig:
    """Tests for DataSourcesConfig."""

    def test_default_values(self):
        """Test DataSourcesConfig with default values."""
        config = DataSourcesConfig()
        assert config.update_interval == 300
        assert config.symbols == ["BTC-USD"]

    def test_custom_values(self):
        """Test DataSourcesConfig with custom values."""
        config = DataSourcesConfig(update_interval=600, symbols=["BTC-USD", "ETH-USD"])
        assert config.update_interval == 600
        assert config.symbols == ["BTC-USD", "ETH-USD"]

    def test_update_interval_validation(self):
        """Test DataSourcesConfig update_interval validation."""
        # Valid values
        DataSourcesConfig(update_interval=1)
        DataSourcesConfig(update_interval=3600)
        # Invalid: too low
        with pytest.raises(ValidationError):
            DataSourcesConfig(update_interval=0)
        # Invalid: too high
        with pytest.raises(ValidationError):
            DataSourcesConfig(update_interval=3601)

    def test_symbols_validation(self):
        """Test DataSourcesConfig symbols validation."""
        # Valid
        DataSourcesConfig(symbols=["BTC-USD"])
        DataSourcesConfig(symbols=["BTC-USD", "ETH-USD"])
        # Invalid: empty list
        with pytest.raises(ValidationError, match="At least one symbol must be specified"):
            DataSourcesConfig(symbols=[])


class TestAnalysisConfig:
    """Tests for AnalysisConfig."""

    def test_default_values(self):
        """Test AnalysisConfig with default values."""
        config = AnalysisConfig()
        assert config.rsi_period == 14
        assert config.macd_fast == 12
        assert config.macd_slow == 26
        assert config.macd_signal == 9
        assert config.moving_averages == [20, 50, 200]

    def test_custom_values(self):
        """Test AnalysisConfig with custom values."""
        config = AnalysisConfig(
            rsi_period=10,
            macd_fast=5,
            macd_slow=20,
            macd_signal=7,
            moving_averages=[10, 30, 60, 120],
        )
        assert config.rsi_period == 10
        assert config.macd_fast == 5
        assert config.macd_slow == 20
        assert config.macd_signal == 7
        assert config.moving_averages == [10, 30, 60, 120]

    def test_rsi_period_validation(self):
        """Test AnalysisConfig rsi_period validation."""
        # Valid
        AnalysisConfig(rsi_period=2)
        AnalysisConfig(rsi_period=50)
        # Invalid: too low
        with pytest.raises(ValidationError):
            AnalysisConfig(rsi_period=1)
        # Invalid: too high
        with pytest.raises(ValidationError):
            AnalysisConfig(rsi_period=51)

    def test_macd_validation(self):
        """Test AnalysisConfig MACD parameter validation."""
        # Valid
        AnalysisConfig(macd_fast=5, macd_slow=20)
        # Invalid: slow not greater than fast
        with pytest.raises(ValidationError, match="slow period must be greater than fast period"):
            AnalysisConfig(macd_fast=20, macd_slow=10)
        # Invalid: equal
        with pytest.raises(ValidationError, match="slow period must be greater than fast period"):
            AnalysisConfig(macd_fast=10, macd_slow=10)

    def test_moving_averages_validation(self):
        """Test AnalysisConfig moving_averages validation."""
        # Valid
        AnalysisConfig(moving_averages=[10])
        AnalysisConfig(moving_averages=[10, 20, 30])
        # Invalid: empty list
        with pytest.raises(ValidationError, match="At least one moving average period"):
            AnalysisConfig(moving_averages=[])
        # Invalid: negative value
        with pytest.raises(ValidationError, match="All moving average periods must be positive"):
            AnalysisConfig(moving_averages=[10, -20])
        # Valid: sorting happens automatically
        config = AnalysisConfig(moving_averages=[50, 20, 200])
        assert config.moving_averages == [20, 50, 200]


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_values(self):
        """Test LoggingConfig with default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file == "btc_monitor.log"

    def test_custom_values(self):
        """Test LoggingConfig with custom values."""
        config = LoggingConfig(level="DEBUG", file="custom.log")
        assert config.level == "DEBUG"
        assert config.file == "custom.log"

    def test_level_validation(self):
        """Test LoggingConfig level validation."""
        # Valid values (case-insensitive)
        LoggingConfig(level="DEBUG")
        LoggingConfig(level="info")
        LoggingConfig(level="WaRnInG")
        LoggingConfig(level="ERROR")
        LoggingConfig(level="CRITICAL")
        # Invalid level
        with pytest.raises(ValidationError, match="Log level must be one of"):
            LoggingConfig(level="TRACE")
        # Converted to uppercase
        config = LoggingConfig(level="debug")
        assert config.level == "DEBUG"


class TestConfig:
    """Tests for Config class."""

    def test_default_values(self):
        """Test Config with all default values."""
        config = Config()
        assert isinstance(config.twitter, TwitterConfig)
        assert isinstance(config.news, NewsConfig)
        assert isinstance(config.research, ResearchConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.data_sources, DataSourcesConfig)
        assert isinstance(config.analysis, AnalysisConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_convenience_properties(self):
        """Test convenience properties."""
        config = Config(
            twitter=TwitterConfig(bearer_token="test_twitter_key"),
            news=NewsConfig(api_key="test_news_key"),
            data_sources=DataSourcesConfig(update_interval=600),
            logging=LoggingConfig(level="DEBUG"),
        )
        assert config.twitter_api_key == "test_twitter_key"
        assert config.news_api_key == "test_news_key"
        assert config.refresh_interval == 600
        assert config.rsi_overbought == 70.0
        assert config.rsi_oversold == 30.0
        assert config.db_path == "btc_monitor.db"
        assert config.log_level == "DEBUG"

    def test_rsi_thresholds_are_constant(self):
        """Test that RSI thresholds are constant values."""
        config = Config()
        assert config.rsi_overbought == 70.0
        assert config.rsi_oversold == 30.0

    def test_db_path_from_url(self):
        """Test db_path extraction from database URL."""
        # SQLite URL
        config = Config(database=DatabaseConfig(url="sqlite:///custom.db"))
        assert config.db_path == "custom.db"
        # Non-SQLite URL (return as-is)
        config = Config(database=DatabaseConfig(url="postgresql://localhost/db"))
        assert config.db_path == "postgresql://localhost/db"

    def test_from_yaml_file_not_found(self):
        """Test from_yaml with non-existent file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            Config.from_yaml("nonexistent.yaml")

    def test_from_yaml_invalid_yaml(self):
        """Test from_yaml with invalid YAML syntax."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:\n  - broken")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid YAML format"):
                Config.from_yaml(temp_path)
        finally:
            os.unlink(temp_path)

    def test_from_yaml_empty_file(self):
        """Test from_yaml with empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Configuration file is empty"):
                Config.from_yaml(temp_path)
        finally:
            os.unlink(temp_path)

    def test_from_yaml_valid_config(self):
        """Test from_yaml with valid configuration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
twitter:
  bearer_token: "test_bearer"
news:
  api_key: "test_news_key"
  max_articles: 25
data_sources:
  update_interval: 600
  symbols:
    - "BTC-USD"
    - "ETH-USD"
logging:
  level: "DEBUG"
""")
            f.flush()
            temp_path = f.name

        try:
            config = Config.from_yaml(temp_path)
            assert config.twitter_api_key == "test_bearer"
            assert config.news_api_key == "test_news_key"
            assert config.news.max_articles == 25
            assert config.refresh_interval == 600
            assert config.data_sources.symbols == ["BTC-USD", "ETH-USD"]
            assert config.log_level == "DEBUG"
        finally:
            os.unlink(temp_path)

    def test_from_yaml_invalid_values(self):
        """Test from_yaml with invalid configuration values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
news:
  max_articles: 200  # Too high
""")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ValidationError):
                Config.from_yaml(temp_path)
        finally:
            os.unlink(temp_path)

    def test_save_yaml(self):
        """Test save_yaml functionality."""
        config = Config(
            twitter=TwitterConfig(bearer_token="test_bearer"),
            news=NewsConfig(api_key="test_news"),
            logging=LoggingConfig(level="DEBUG"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "saved_config.yaml"
            config.save_yaml(temp_path)

            # Verify file was created
            assert temp_path.exists()

            # Load and verify
            loaded_config = Config.from_yaml(temp_path)
            assert loaded_config.twitter_api_key == "test_bearer"
            assert loaded_config.news_api_key == "test_news"
            assert loaded_config.log_level == "DEBUG"

    def test_environment_variable_override(self):
        """Test environment variable overrides."""
        # Set environment variable
        # Format: BTC_MONITOR_<SECTION>__<FIELD>
        os.environ["BTC_MONITOR_NEWS__API_KEY"] = "env_api_key"
        os.environ["BTC_MONITOR_LOGGING__LEVEL"] = "WARNING"

        try:
            # Config should pick up env vars even with default values
            config = Config()
            assert config.news_api_key == "env_api_key"
            assert config.log_level == "WARNING"
        finally:
            # Clean up
            del os.environ["BTC_MONITOR_NEWS__API_KEY"]
            del os.environ["BTC_MONITOR_LOGGING__LEVEL"]

    def test_environment_variable_nested_override(self):
        """Test nested environment variable overrides."""
        os.environ["BTC_MONITOR_TWITTER__BEARER_TOKEN"] = "env_twitter_key"
        os.environ["BTC_MONITOR_DATA_SOURCES__UPDATE_INTERVAL"] = "900"

        try:
            config = Config()
            assert config.twitter_api_key == "env_twitter_key"
            assert config.refresh_interval == 900
        finally:
            del os.environ["BTC_MONITOR_TWITTER__BEARER_TOKEN"]
            del os.environ["BTC_MONITOR_DATA_SOURCES__UPDATE_INTERVAL"]

    def test_from_yaml_values_override_defaults_but_not_env_vars_when_explicit(self):
        """Test that from_yaml uses YAML values over defaults."""
        # Create YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
news:
  api_key: "yaml_api_key"
logging:
  level: "INFO"
""")
            f.flush()
            temp_path = f.name

        try:
            config = Config.from_yaml(temp_path)
            # YAML values should be used (not defaults)
            assert config.news_api_key == "yaml_api_key"
            assert config.log_level == "INFO"
        finally:
            os.unlink(temp_path)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_default_path(self):
        """Test load_config with default path (config/config.yaml)."""
        # The project's config.yaml should exist
        config = load_config("config/config.yaml")
        assert isinstance(config, Config)

    def test_load_config_custom_path(self):
        """Test load_config with custom path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
twitter:
  bearer_token: "test"
""")
            f.flush()
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config.twitter_api_key == "test"
        finally:
            os.unlink(temp_path)

    def test_load_config_file_not_found(self):
        """Test load_config with non-existent file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config("nonexistent_config.yaml")

    def test_load_config_invalid_values(self):
        """Test load_config with invalid configuration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
data_sources:
  symbols: []  # Invalid: empty list
""")
            f.flush()
            temp_path = f.name

        try:
            with pytest.raises(ValidationError):
                load_config(temp_path)
        finally:
            os.unlink(temp_path)


class TestConfigLoadingWithRealFile:
    """Tests using the actual config.yaml file."""

    def test_load_project_config(self):
        """Test loading the project's actual config.yaml file."""
        config = load_config("config/config.yaml")
        assert isinstance(config, Config)
        assert isinstance(config.twitter, TwitterConfig)
        assert isinstance(config.news, NewsConfig)
        assert isinstance(config.research, ResearchConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.data_sources, DataSourcesConfig)
        assert isinstance(config.analysis, AnalysisConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_config_example_file(self):
        """Test that config.example.yaml can be loaded (may have placeholder values)."""
        # The example file should be valid YAML even if values are placeholders
        config = Config.from_yaml("config/config.example.yaml")
        assert isinstance(config, Config)
        # Check that it contains the expected structure
        assert config.twitter.consumer_key == "your_consumer_key_here"
        assert config.news.api_key == "your_newsapi_key_here"
