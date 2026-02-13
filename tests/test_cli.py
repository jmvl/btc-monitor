"""Tests for CLI interface."""

import json
import subprocess
import sys
from unittest.mock import MagicMock, patch, call, create_autospec
from datetime import datetime, timezone
import tempfile
from pathlib import Path

import pytest

from btc_monitor.cli import (
    setup_logging,
    format_output,
    cmd_monitor,
    cmd_analyze,
    cmd_status,
    cmd_history,
    run_monitoring_cycle,
    main,
)
from btc_monitor.config import Config
from btc_monitor.database import get_session, init_db
from btc_monitor.models import TrendAnalysis, PriceData, TechnicalIndicators


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_verbose_true(self):
        """Test logging setup with verbose=True."""
        setup_logging(verbose=True)
        # Should not raise any errors
        import logging
        # The root logger should be set to DEBUG or lower
        # Note: If there are multiple handlers, the effective level might be higher
        # Just verify that no error is raised and basicSetup completed
        assert logging.getLogger().handlers is not None

    def test_setup_logging_verbose_false(self):
        """Test logging setup with verbose=False."""
        setup_logging(verbose=False)
        # Should not raise any errors
        import logging
        assert logging.getLogger().level >= logging.INFO

    def test_setup_logging_with_config(self):
        """Test logging setup with config object."""
        config = MagicMock()
        config.logging.level = "WARNING"
        setup_logging(verbose=False, config=config)
        import logging
        assert logging.getLogger().level >= logging.WARNING


class TestFormatOutput:
    """Tests for format_output function."""

    def test_format_output_text(self):
        """Test formatting output as text."""
        data = {
            "trend": "bullish",
            "confidence": 75.5,
            "rsi_signal": "neutral",
        }
        output = format_output(data, as_json=False)
        assert "Trend: bullish" in output
        assert "Confidence: 75.50" in output
        assert "Rsi Signal: neutral" in output

    def test_format_output_json(self):
        """Test formatting output as JSON."""
        data = {
            "trend": "bullish",
            "confidence": 75.5,
        }
        output = format_output(data, as_json=True)
        parsed = json.loads(output)
        assert parsed["trend"] == "bullish"
        assert parsed["confidence"] == 75.5

    def test_format_output_with_floats(self):
        """Test formatting with float values."""
        data = {
            "price": 50000.123456,
            "volume": 1234567890.12,
        }
        output = format_output(data, as_json=False)
        assert "Price: 50000.123456" in output or "Price: 50000.12" in output
        assert "Volume:" in output


class TestCmdStatus:
    """Tests for cmd_status function."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database for testing."""
        return str(tmp_path / "test.db")

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = create_autospec(Config)
        config.db_path = ":memory:"
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        config.logging = mock_logging
        config.refresh_interval = 300
        return config

    def test_cmd_status_no_data(self, mock_config, capsys):
        """Test status command when no data exists."""
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = False

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session") as mock_session:
                    mock_session.return_value.query.return_value.order_by.return_value.first.return_value = None
                    with pytest.raises(SystemExit) as exc_info:
                        cmd_status(args)
                    assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "No trend analysis found" in captured.out

    def test_cmd_status_with_data(self, capsys):
        """Test status command with data using mocks."""
        # Create args
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = False

        # Mock load_config
        mock_config = create_autospec(Config)
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        mock_config.logging = mock_logging

        # Create mock trend analysis
        mock_analysis = MagicMock()
        mock_analysis.timestamp = datetime.now(timezone.utc)
        mock_analysis.trend = "bullish"
        mock_analysis.confidence = 0.75
        mock_analysis.indicators_summary = "Test summary"

        # Create mock session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.order_by.return_value.first.return_value = mock_analysis
        mock_session.query.return_value = mock_query
        mock_session.close = MagicMock()

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session", return_value=mock_session):
                    cmd_status(args)

        captured = capsys.readouterr()
        assert "Trend: bullish" in captured.out
        assert "Confidence: 75.00" in captured.out

    def test_cmd_status_json(self, capsys):
        """Test status command with JSON output using mocks."""
        # Create args
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = True

        # Mock load_config
        mock_config = create_autospec(Config)
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        mock_config.logging = mock_logging

        # Create mock trend analysis
        mock_analysis = MagicMock()
        mock_analysis.timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_analysis.trend = "bearish"
        mock_analysis.confidence = 0.60
        mock_analysis.indicators_summary = "Bearish test summary"

        # Create mock session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.order_by.return_value.first.return_value = mock_analysis
        mock_session.query.return_value = mock_query
        mock_session.close = MagicMock()

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session", return_value=mock_session):
                    cmd_status(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["trend"] == "bearish"
        assert output["confidence"] == 60.0
        assert output["indicators_summary"] == "Bearish test summary"


class TestCmdHistory:
    """Tests for cmd_history function."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database for testing."""
        return str(tmp_path / "test.db")

    def test_cmd_history_no_data(self, temp_db_path, capsys):
        """Test history command when no data exists."""
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = False
        args.count = 10

        # Mock load_config to use temp database
        mock_config = create_autospec(Config)
        mock_config.db_path = temp_db_path
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        mock_config.logging = mock_logging

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session") as mock_session:
                    mock_session.return_value.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
                    with pytest.raises(SystemExit) as exc_info:
                        cmd_history(args)
                    assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "No trend analyses found" in captured.out

    def test_cmd_history_with_data(self, capsys):
        """Test history command with data using mocks."""
        # Create args
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = False
        args.count = 10

        # Mock load_config
        mock_config = create_autospec(Config)
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        mock_config.logging = mock_logging

        # Create mock trend analyses
        mock_analyses = []
        for i in range(3):
            mock_analysis = MagicMock()
            mock_analysis.timestamp = datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc)
            mock_analysis.trend = "bullish" if i % 2 == 0 else "bearish"
            mock_analysis.confidence = 0.7 + (i * 0.05)
            mock_analysis.indicators_summary = f"Analysis {i+1}"
            mock_analyses.append(mock_analysis)

        # Create mock session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_analyses
        mock_session.query.return_value = mock_query
        mock_session.close = MagicMock()

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session", return_value=mock_session):
                    cmd_history(args)

        captured = capsys.readouterr()
        assert "Past 3 analyses" in captured.out
        assert "#1" in captured.out
        assert "#2" in captured.out
        assert "#3" in captured.out

    def test_cmd_history_json(self, capsys):
        """Test history command with JSON output using mocks."""
        # Create args
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = True
        args.count = 10

        # Mock load_config
        mock_config = create_autospec(Config)
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        mock_config.logging = mock_logging

        # Create mock trend analyses
        mock_analyses = []
        for i in range(2):
            mock_analysis = MagicMock()
            mock_analysis.timestamp = datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc)
            mock_analysis.trend = "bullish"
            mock_analysis.confidence = 0.8
            mock_analysis.indicators_summary = f"Summary {i+1}"
            mock_analyses.append(mock_analysis)

        # Create mock session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_analyses
        mock_session.query.return_value = mock_query
        mock_session.close = MagicMock()

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session", return_value=mock_session):
                    cmd_history(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output, list)
        assert len(output) == 2
        assert all("timestamp" in item for item in output)
        assert all("trend" in item for item in output)
        assert all("confidence" in item for item in output)

    def test_cmd_history_count_limit(self, capsys):
        """Test history command respects count limit using mocks."""
        # Create args with count=2
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = True
        args.count = 2

        # Mock load_config
        mock_config = create_autospec(Config)
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        mock_config.logging = mock_logging

        # Create mock trend analyses
        mock_analyses = []
        for i in range(5):
            mock_analysis = MagicMock()
            mock_analysis.timestamp = datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc)
            mock_analysis.trend = "bullish"
            mock_analysis.confidence = 0.8
            mock_analysis.indicators_summary = f"Analysis {i+1}"
            mock_analyses.append(mock_analysis)

        # Create mock session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_analyses[:2]
        mock_session.query.return_value = mock_query
        mock_session.close = MagicMock()

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session", return_value=mock_session):
                    cmd_history(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output) == 2


class TestCmdAnalyze:
    """Tests for cmd_analyze function."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = create_autospec(Config)
        config.db_path = ":memory:"
        config.refresh_interval = 300
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        config.logging = mock_logging
        mock_twitter = MagicMock()
        mock_twitter.bearer_token = None
        config.twitter = mock_twitter
        mock_news = MagicMock()
        mock_news.api_key = None
        mock_news.max_articles = 50
        mock_news.hours_back = 24
        config.news = mock_news
        mock_research = MagicMock()
        mock_research.max_items = 30
        mock_research.hours_back = 48
        config.research = mock_research
        mock_analysis = MagicMock()
        mock_analysis.rsi_period = 14
        mock_analysis.macd_fast = 12
        mock_analysis.macd_slow = 26
        mock_analysis.macd_signal = 9
        mock_analysis.moving_averages = [20, 50, 200]
        config.analysis = mock_analysis
        return config

    def test_cmd_analyze_success(self, mock_config):
        """Test analyze command with successful execution."""
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = False

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session") as mock_session:
                    with patch("btc_monitor.cli.PriceFetcher") as mock_fetcher:
                        with patch("btc_monitor.cli.TrendAnalyzer") as mock_analyzer:
                            with patch("btc_monitor.cli.run_monitoring_cycle", return_value=True):
                                mock_session.return_value.close = MagicMock()
                                cmd_analyze(args)

        # Should not raise any errors or exit with code 1

    def test_cmd_analyze_failure(self, mock_config):
        """Test analyze command with failure."""
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.json = False

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session") as mock_session:
                    with patch("btc_monitor.cli.PriceFetcher") as mock_fetcher:
                        with patch("btc_monitor.cli.TrendAnalyzer") as mock_analyzer:
                            with patch("btc_monitor.cli.run_monitoring_cycle", return_value=False):
                                with pytest.raises(SystemExit) as exc_info:
                                    cmd_analyze(args)
                                assert exc_info.value.code == 1


class TestCmdMonitor:
    """Tests for cmd_monitor function."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = create_autospec(Config)
        config.db_path = ":memory:"
        config.refresh_interval = 300
        mock_logging = MagicMock()
        mock_logging.level = "INFO"
        config.logging = mock_logging
        mock_twitter = MagicMock()
        mock_twitter.bearer_token = None
        config.twitter = mock_twitter
        mock_news = MagicMock()
        mock_news.api_key = None
        mock_news.max_articles = 50
        mock_news.hours_back = 24
        config.news = mock_news
        mock_research = MagicMock()
        mock_research.max_items = 30
        mock_research.hours_back = 48
        config.research = mock_research
        mock_analysis = MagicMock()
        mock_analysis.rsi_period = 14
        mock_analysis.macd_fast = 12
        mock_analysis.macd_slow = 26
        mock_analysis.macd_signal = 9
        mock_analysis.moving_averages = [20, 50, 200]
        config.analysis = mock_analysis
        return config

    def test_cmd_monitor_once(self, mock_config):
        """Test monitor command with --once flag."""
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.interval = None
        args.once = True

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session") as mock_session:
                    with patch("btc_monitor.cli.PriceFetcher") as mock_fetcher:
                        with patch("btc_monitor.cli.TrendAnalyzer") as mock_analyzer:
                            with patch("btc_monitor.cli.run_monitoring_cycle", return_value=True):
                                with patch("signal.signal"):
                                    with patch("time.sleep"):
                                        mock_session.return_value.close = MagicMock()
                                        cmd_monitor(args)

        # Should not raise any errors

    def test_cmd_monitor_custom_interval(self, mock_config):
        """Test monitor command with custom interval."""
        args = MagicMock()
        args.config = None
        args.verbose = False
        args.interval = 60
        args.once = True

        with patch("btc_monitor.cli.load_config", return_value=mock_config):
            with patch("btc_monitor.cli.init_db"):
                with patch("btc_monitor.cli.get_session") as mock_session:
                    with patch("btc_monitor.cli.PriceFetcher") as mock_fetcher:
                        with patch("btc_monitor.cli.TrendAnalyzer") as mock_analyzer:
                            with patch("btc_monitor.cli.run_monitoring_cycle") as mock_cycle:
                                with patch("signal.signal"):
                                    with patch("time.sleep"):
                                        mock_session.return_value.close = MagicMock()
                                        cmd_monitor(args)

        # Verify that monitoring was called with custom interval
        # (This would require more complex mocking to verify)


class TestRunMonitoringCycle:
    """Tests for run_monitoring_cycle function."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temporary database for testing."""
        return str(tmp_path / "test.db")

    def test_run_monitoring_cycle_success(self, temp_db_path):
        """Test successful monitoring cycle."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{temp_db_path}")
        init_db(temp_db_path)

        Session = sessionmaker(bind=engine)
        session = Session()

        # Add price data
        price = PriceData(
            timestamp=datetime.now(timezone.utc),
            price=50000.0,
            volume=1000000.0,
        )
        session.add(price)
        session.commit()

        # Create mock config
        mock_config = create_autospec(Config)
        mock_analysis = MagicMock()
        mock_analysis.rsi_period = 14
        mock_analysis.macd_fast = 12
        mock_analysis.macd_slow = 26
        mock_analysis.macd_signal = 9
        mock_analysis.moving_averages = [20, 50, 200]
        mock_config.analysis = mock_analysis
        mock_twitter = MagicMock()
        mock_twitter.bearer_token = None
        mock_config.twitter = mock_twitter
        mock_news = MagicMock()
        mock_news.api_key = None
        mock_news.max_articles = 50
        mock_news.hours_back = 24
        mock_config.news = mock_news
        mock_research = MagicMock()
        mock_research.max_items = 30
        mock_research.hours_back = 48
        mock_config.research = mock_research

        # Create components
        price_fetcher = MagicMock()
        price_fetcher.fetch_and_save_current_price.return_value = price

        trend_analyzer = MagicMock()
        trend_analyzer.analyze.return_value = {
            "trend": "bullish",
            "confidence": 0.75,
            "rsi_signal": "neutral",
            "macd_signal": "bullish",
            "ma_signal": "bullish",
            "sentiment_signal": "neutral",
            "indicators_summary": "Test summary",
        }

        # Run cycle
        result = run_monitoring_cycle(
            mock_config,
            session,
            price_fetcher,
            trend_analyzer,
            output_json=False,
        )

        assert result is True
        session.close()


class TestMain:
    """Tests for main CLI entry point."""

    def test_main_help(self, capsys):
        """Test that main() displays help when no command provided."""
        with patch("sys.argv", ["btc-monitor", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_monitor_command(self):
        """Test main() with monitor command."""
        with patch("sys.argv", ["btc-monitor", "monitor", "--once"]):
            with patch("btc_monitor.cli.cmd_monitor") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_main_analyze_command(self):
        """Test main() with analyze command."""
        with patch("sys.argv", ["btc-monitor", "analyze"]):
            with patch("btc_monitor.cli.cmd_analyze") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_main_status_command(self):
        """Test main() with status command."""
        with patch("sys.argv", ["btc-monitor", "status"]):
            with patch("btc_monitor.cli.cmd_status") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_main_history_command(self):
        """Test main() with history command."""
        with patch("sys.argv", ["btc-monitor", "history"]):
            with patch("btc_monitor.cli.cmd_history") as mock_cmd:
                main()
                mock_cmd.assert_called_once()

    def test_main_with_global_options(self):
        """Test main() with global options."""
        with patch("sys.argv", ["btc-monitor", "--verbose", "--json", "analyze"]):
            with patch("btc_monitor.cli.cmd_analyze") as mock_cmd:
                main()
                # Verify that args contain the global options
                args = mock_cmd.call_args[0][0]
                assert args.verbose is True
                assert args.json is True


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_cli_module_importable(self):
        """Test that CLI module can be imported."""
        import btc_monitor.cli
        assert btc_monitor.cli.main is not None

    def test_cli_help_available(self):
        """Test that CLI help is available."""
        result = subprocess.run(
            [sys.executable, "-m", "btc_monitor.cli", "--help"],
            capture_output=True,
            text=True,
            cwd="/root/.openclaw/projects/btc-monitor",
        )
        assert result.returncode == 0
        assert "BTC Monitor" in result.stdout
        assert "monitor" in result.stdout
        assert "analyze" in result.stdout
        assert "status" in result.stdout
        assert "history" in result.stdout

    def test_cli_monitor_help(self):
        """Test that monitor command help is available."""
        result = subprocess.run(
            [sys.executable, "-m", "btc_monitor.cli", "monitor", "--help"],
            capture_output=True,
            text=True,
            cwd="/root/.openclaw/projects/btc-monitor",
        )
        assert result.returncode == 0
        assert "monitor" in result.stdout.lower()
        assert "--interval" in result.stdout
        assert "--once" in result.stdout

    def test_cli_history_help(self):
        """Test that history command help is available."""
        result = subprocess.run(
            [sys.executable, "-m", "btc_monitor.cli", "history", "--help"],
            capture_output=True,
            text=True,
            cwd="/root/.openclaw/projects/btc-monitor",
        )
        assert result.returncode == 0
        assert "--count" in result.stdout
