"""
Tests for the main BTC Monitor script.
"""

import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from btc_monitor.main import (
    setup_logging,
    signal_handler,
    run_monitoring_cycle,
    main as main_entry,
)
from btc_monitor.config import Config


class TestSignalHandler:
    """Tests for signal handling."""

    def test_signal_handler_sets_shutdown_flag(self):
        """Test that signal handler sets the shutdown flag."""
        from btc_monitor import main

        # Ensure shutdown flag is False initially
        main.shutdown_requested = False

        # Simulate SIGINT
        signal_handler(signal.SIGINT, None)

        # Verify flag is set
        assert main.shutdown_requested is True

    def test_signal_handler_handles_sigterm(self):
        """Test that signal handler handles SIGTERM."""
        from btc_monitor import main

        main.shutdown_requested = False
        signal_handler(signal.SIGTERM, None)

        assert main.shutdown_requested is True


class TestSetupLogging:
    """Tests for logging setup."""

    @patch("btc_monitor.main.logging.basicConfig")
    def test_setup_logging_configures_handlers(self, mock_config):
        """Test that setup_logging configures logging with file and console handlers."""
        setup_logging("config/config.yaml", "INFO", "btc_monitor.log")

        # Verify basicConfig was called
        assert mock_config.called
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs["level"] == logging.INFO
        assert len(call_kwargs["handlers"]) == 2  # Console and file

    @patch("btc_monitor.main.logging.basicConfig")
    def test_setup_logging_uppercases_log_level(self, mock_config):
        """Test that setup_logging uppercases the log level."""
        setup_logging("config/config.yaml", "debug", "btc_monitor.log")

        call_kwargs = mock_config.call_args[1]
        assert call_kwargs["level"] == logging.DEBUG

    @patch("btc_monitor.main.logging.basicConfig")
    def test_setup_logging_uses_custom_log_format(self, mock_config):
        """Test that setup_logging uses custom format."""
        setup_logging("config/config.yaml", "INFO", "btc_monitor.log")

        call_kwargs = mock_config.call_args[1]
        assert "%(asctime)s" in call_kwargs["format"]
        assert "%(levelname)s" in call_kwargs["format"]


class TestRunMonitoringCycle:
    """Tests for the monitoring cycle."""

    def test_run_monitoring_cycle_fetches_price(self):
        """Test that monitoring cycle fetches price."""
        # Create mock objects
        config = Mock()
        config.analysis.rsi_period = 14
        config.analysis.macd_fast = 12
        config.analysis.macd_slow = 26
        config.analysis.macd_signal = 9
        config.analysis.moving_averages = [20, 50, 200]
        config.twitter.bearer_token = ""
        config.news.api_key = ""
        config.news.max_articles = 50
        config.news.hours_back = 24
        config.research.max_items = 30
        config.research.hours_back = 48

        session = Mock()
        price_fetcher = Mock()
        price_fetcher.fetch_and_save_current_price.return_value = Mock(
            price=50000.0, volume=1000000.0
        )

        trend_analyzer = Mock()
        trend_analyzer.analyze.return_value = Mock(
            trend="bullish",
            confidence=0.75,
            indicators_summary="RSI: 55, MACD: bullish",
        )

        # Run cycle
        result = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

        # Verify price was fetched
        price_fetcher.fetch_and_save_current_price.assert_called_once()
        assert result is True

    def test_run_monitoring_cycle_handles_price_fetch_failure(self):
        """Test that monitoring cycle handles price fetch failure."""
        config = Mock()
        config.analysis.rsi_period = 14
        config.analysis.macd_fast = 12
        config.analysis.macd_slow = 26
        config.analysis.macd_signal = 9
        config.analysis.moving_averages = [20, 50, 200]
        config.twitter.bearer_token = ""
        config.news.api_key = ""
        config.news.max_articles = 50
        config.news.hours_back = 24
        config.research.max_items = 30
        config.research.hours_back = 48

        session = Mock()
        price_fetcher = Mock()
        price_fetcher.fetch_and_save_current_price.return_value = None

        trend_analyzer = Mock()

        # Run cycle
        result = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

        # Verify failure was handled
        assert result is False

    def test_run_monitoring_cycle_calculates_indicators(self):
        """Test that monitoring cycle calculates indicators."""
        config = Mock()
        config.analysis.rsi_period = 14
        config.analysis.macd_fast = 12
        config.analysis.macd_slow = 26
        config.analysis.macd_signal = 9
        config.analysis.moving_averages = [20, 50, 200]
        config.twitter.bearer_token = ""
        config.news.api_key = ""
        config.news.max_articles = 50
        config.news.hours_back = 24
        config.research.max_items = 30
        config.research.hours_back = 48

        session = Mock()
        price_fetcher = Mock()
        price_fetcher.fetch_and_save_current_price.return_value = Mock(
            price=50000.0, volume=1000000.0
        )

        trend_analyzer = Mock()
        trend_analyzer.analyze.return_value = Mock(
            trend="bullish",
            confidence=0.75,
            indicators_summary="RSI: 55, MACD: bullish",
        )

        # Mock indicator classes
        with patch("btc_monitor.main.RSI") as mock_rsi_class, patch(
            "btc_monitor.main.MACD"
        ) as mock_macd_class, patch("btc_monitor.main.MovingAverages") as mock_ma_class:
            mock_rsi = Mock()
            mock_macd = Mock()
            mock_ma = Mock()
            mock_rsi_class.return_value = mock_rsi
            mock_macd_class.return_value = mock_macd
            mock_ma_class.return_value = mock_ma

            # Run cycle
            result = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

            # Verify indicators were calculated
            mock_rsi_class.assert_called_once_with(period=14)
            mock_rsi.calculate_and_save.assert_called_once_with(session)
            mock_macd_class.assert_called_once_with(fast=12, slow=26, signal=9)
            mock_macd.calculate_and_save.assert_called_once_with(session)
            mock_ma_class.assert_called_once_with()
            mock_ma.calculate_and_save.assert_called_once_with(session)

    def test_run_monitoring_cycle_handles_indicator_calculation_failure(self):
        """Test that monitoring cycle continues when indicator calculation fails."""
        config = Mock()
        config.analysis.rsi_period = 14
        config.analysis.macd_fast = 12
        config.analysis.macd_slow = 26
        config.analysis.macd_signal = 9
        config.analysis.moving_averages = [20, 50, 200]
        config.twitter.bearer_token = ""
        config.news.api_key = ""
        config.news.max_articles = 50
        config.news.hours_back = 24
        config.research.max_items = 30
        config.research.hours_back = 48

        session = Mock()
        price_fetcher = Mock()
        price_fetcher.fetch_and_save_current_price.return_value = Mock(
            price=50000.0, volume=1000000.0
        )

        trend_analyzer = Mock()
        trend_analyzer.analyze.return_value = Mock(
            trend="bullish",
            confidence=0.75,
            indicators_summary="RSI: 55, MACD: bullish",
        )

        # Mock RSI to raise exception
        with patch("btc_monitor.main.RSI") as mock_rsi_class, patch(
            "btc_monitor.main.MACD"
        ) as mock_macd_class, patch("btc_monitor.main.MovingAverages") as mock_ma_class:
            mock_rsi = Mock()
            mock_rsi.calculate_and_save.side_effect = Exception("RSI failed")
            mock_rsi_class.return_value = mock_rsi
            mock_macd_class.return_value = Mock()
            mock_ma_class.return_value = Mock()

            # Run cycle
            result = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

            # Should still succeed despite RSI failure
            assert result is True

    def test_run_monitoring_cycle_collects_sentiment(self):
        """Test that monitoring cycle collects sentiment."""
        config = Mock()
        config.analysis.rsi_period = 14
        config.analysis.macd_fast = 12
        config.analysis.macd_slow = 26
        config.analysis.macd_signal = 9
        config.analysis.moving_averages = [20, 50, 200]
        config.twitter.bearer_token = ""
        config.news.api_key = ""
        config.news.max_articles = 50
        config.news.hours_back = 24
        config.research.max_items = 30
        config.research.hours_back = 48

        session = Mock()
        price_fetcher = Mock()
        price_fetcher.fetch_and_save_current_price.return_value = Mock(
            price=50000.0, volume=1000000.0
        )

        trend_analyzer = Mock()
        trend_analyzer.analyze.return_value = Mock(
            trend="bullish",
            confidence=0.75,
            indicators_summary="RSI: 55, MACD: bullish",
        )

        # Mock sentiment collectors
        with patch(
            "btc_monitor.main.NewsSentimentCollector"
        ) as mock_news_class, patch(
            "btc_monitor.main.ResearchCollector"
        ) as mock_research_class, patch(
            "btc_monitor.main.TwitterSentimentCollector"
        ), patch(
            "btc_monitor.main.RSI"
        ), patch(
            "btc_monitor.main.MACD"
        ), patch(
            "btc_monitor.main.MovingAverages"
        ):
            mock_news_collector = Mock()
            mock_news_collector.collect.return_value = [
                Mock(),
                Mock(),
            ]  # 2 entries
            mock_news_class.return_value = mock_news_collector

            mock_research_collector = Mock()
            mock_research_collector.collect.return_value = [
                Mock(),
            ]  # 1 entry
            mock_research_class.return_value = mock_research_collector

            # Run cycle
            result = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

            # Verify sentiment was collected
            mock_news_collector.collect.assert_called_once()
            mock_news_collector.collect_and_save.assert_called_once_with(session)
            mock_research_collector.collect.assert_called_once()
            mock_research_collector.collect_and_save.assert_called_once_with(session)
            assert result is True

    def test_run_monitoring_cycle_analyzes_trend(self):
        """Test that monitoring cycle analyzes trend."""
        config = Mock()
        config.analysis.rsi_period = 14
        config.analysis.macd_fast = 12
        config.analysis.macd_slow = 26
        config.analysis.macd_signal = 9
        config.analysis.moving_averages = [20, 50, 200]
        config.twitter.bearer_token = ""
        config.news.api_key = ""
        config.news.max_articles = 50
        config.news.hours_back = 24
        config.research.max_items = 30
        config.research.hours_back = 48

        session = Mock()
        price_fetcher = Mock()
        price_fetcher.fetch_and_save_current_price.return_value = Mock(
            price=50000.0, volume=1000000.0
        )

        trend_analyzer = Mock()
        trend_analyzer.analyze.return_value = Mock(
            trend="bullish",
            confidence=0.75,
            indicators_summary="RSI: 55, MACD: bullish",
        )

        with patch("btc_monitor.main.RSI"), patch(
            "btc_monitor.main.MACD"
        ), patch("btc_monitor.main.MovingAverages"), patch(
            "btc_monitor.main.NewsSentimentCollector"
        ), patch("btc_monitor.main.ResearchCollector"), patch(
            "btc_monitor.main.TwitterSentimentCollector"
        ):
            # Run cycle
            result = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

            # Verify trend was analyzed
            trend_analyzer.analyze.assert_called_once()
            assert result is True

    def test_run_monitoring_cycle_handles_trend_analysis_failure(self):
        """Test that monitoring cycle handles trend analysis returning None."""
        config = Mock()
        config.analysis.rsi_period = 14
        config.analysis.macd_fast = 12
        config.analysis.macd_slow = 26
        config.analysis.macd_signal = 9
        config.analysis.moving_averages = [20, 50, 200]
        config.twitter.bearer_token = ""
        config.news.api_key = ""
        config.news.max_articles = 50
        config.news.hours_back = 24
        config.research.max_items = 30
        config.research.hours_back = 48

        session = Mock()
        price_fetcher = Mock()
        price_fetcher.fetch_and_save_current_price.return_value = Mock(
            price=50000.0, volume=1000000.0
        )

        trend_analyzer = Mock()
        trend_analyzer.analyze.return_value = None

        with patch("btc_monitor.main.RSI"), patch(
            "btc_monitor.main.MACD"
        ), patch("btc_monitor.main.MovingAverages"), patch(
            "btc_monitor.main.NewsSentimentCollector"
        ), patch("btc_monitor.main.ResearchCollector"), patch(
            "btc_monitor.main.TwitterSentimentCollector"
        ):
            # Run cycle
            result = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

            # Should still succeed despite trend analysis returning None
            assert result is True


class TestMainFunction:
    """Tests for the main entry point function."""

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.init_db")
    @patch("btc_monitor.main.get_session")
    @patch("btc_monitor.main.PriceFetcher")
    @patch("btc_monitor.main.TrendAnalyzer")
    @patch("btc_monitor.main.load_config")
    @patch("btc_monitor.main.signal")
    def test_main_loads_config(
        self,
        mock_signal,
        mock_load_config,
        mock_trend_analyzer,
        mock_price_fetcher,
        mock_get_session,
        mock_init_db,
        mock_setup_logging,
    ):
        """Test that main loads configuration."""
        # Setup mocks
        config = Mock()
        config.log_level = "INFO"
        config.logging.file = "btc_monitor.log"
        config.db_path = "btc_monitor.db"
        config.data_sources.symbols = ["BTC-USD"]
        config.rsi_overbought = 70.0
        config.rsi_oversold = 30.0
        config.refresh_interval = 300
        mock_load_config.return_value = config

        session = Mock()
        mock_get_session.return_value = session
        mock_price_fetcher.return_value = Mock()
        mock_trend_analyzer.return_value = Mock()

        # Run main with --once flag
        with patch("btc_monitor.main.shutdown_requested", False):
            exit_code = main_entry(once=True)

        # Verify config was loaded
        mock_load_config.assert_called_once()

        # Verify successful exit
        assert exit_code == 0

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.init_db")
    @patch("btc_monitor.main.get_session")
    @patch("btc_monitor.main.PriceFetcher")
    @patch("btc_monitor.main.TrendAnalyzer")
    @patch("btc_monitor.main.load_config")
    @patch("btc_monitor.main.signal")
    def test_main_initializes_database(
        self,
        mock_signal,
        mock_load_config,
        mock_trend_analyzer,
        mock_price_fetcher,
        mock_get_session,
        mock_init_db,
        mock_setup_logging,
    ):
        """Test that main initializes database."""
        config = Mock()
        config.log_level = "INFO"
        config.logging.file = "btc_monitor.log"
        config.db_path = "btc_monitor.db"
        config.data_sources.symbols = ["BTC-USD"]
        config.rsi_overbought = 70.0
        config.rsi_oversold = 30.0
        config.refresh_interval = 300
        mock_load_config.return_value = config

        session = Mock()
        mock_get_session.return_value = session
        mock_price_fetcher.return_value = Mock()
        mock_trend_analyzer.return_value = Mock()

        with patch("btc_monitor.main.shutdown_requested", False):
            exit_code = main_entry(once=True)

        # Verify database was initialized
        mock_init_db.assert_called_once_with("btc_monitor.db")
        assert exit_code == 0

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.init_db")
    @patch("btc_monitor.main.get_session")
    @patch("btc_monitor.main.PriceFetcher")
    @patch("btc_monitor.main.TrendAnalyzer")
    @patch("btc_monitor.main.load_config")
    @patch("btc_monitor.main.signal")
    @patch("btc_monitor.main.run_monitoring_cycle")
    def test_main_runs_monitoring_cycle(
        self,
        mock_run_cycle,
        mock_signal,
        mock_load_config,
        mock_trend_analyzer,
        mock_price_fetcher,
        mock_get_session,
        mock_init_db,
        mock_setup_logging,
    ):
        """Test that main runs monitoring cycle."""
        config = Mock()
        config.log_level = "INFO"
        config.logging.file = "btc_monitor.log"
        config.db_path = "btc_monitor.db"
        config.data_sources.symbols = ["BTC-USD"]
        config.rsi_overbought = 70.0
        config.rsi_oversold = 30.0
        config.refresh_interval = 300
        mock_load_config.return_value = config

        session = Mock()
        mock_get_session.return_value = session
        mock_price_fetcher.return_value = Mock()
        mock_trend_analyzer.return_value = Mock()
        mock_run_cycle.return_value = True

        with patch("btc_monitor.main.shutdown_requested", False):
            exit_code = main_entry(once=True)

        # Verify monitoring cycle was run
        mock_run_cycle.assert_called_once()
        assert exit_code == 0

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.init_db")
    @patch("btc_monitor.main.get_session")
    @patch("btc_monitor.main.PriceFetcher")
    @patch("btc_monitor.main.TrendAnalyzer")
    @patch("btc_monitor.main.load_config")
    @patch("btc_monitor.main.signal")
    def test_main_handles_shutdown_signal(
        self,
        mock_signal,
        mock_load_config,
        mock_trend_analyzer,
        mock_price_fetcher,
        mock_get_session,
        mock_init_db,
        mock_setup_logging,
    ):
        """Test that main handles shutdown signal gracefully."""
        config = Mock()
        config.log_level = "INFO"
        config.logging.file = "btc_monitor.log"
        config.db_path = "btc_monitor.db"
        config.data_sources.symbols = ["BTC-USD"]
        config.rsi_overbought = 70.0
        config.rsi_oversold = 30.0
        config.refresh_interval = 1  # Short interval for testing
        mock_load_config.return_value = config

        session = Mock()
        mock_get_session.return_value = session
        mock_price_fetcher.return_value = Mock()
        mock_trend_analyzer.return_value = Mock()

        # Simulate shutdown after first cycle
        cycle_count = [0]

        def mock_signal_handler(sig, frame):
            from btc_monitor import main as main_module
            main_module.shutdown_requested = True

        mock_signal.signal.side_effect = mock_signal_handler

        with patch("btc_monitor.main.run_monitoring_cycle") as mock_run_cycle:
            mock_run_cycle.return_value = True

            # Reset shutdown flag
            with patch("btc_monitor.main.shutdown_requested", False):
                # Trigger shutdown after cycle
                exit_code = main_entry(once=True)

        # Verify session was closed
        session.close.assert_called_once()
        assert exit_code == 0

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.load_config")
    def test_main_handles_config_load_error(
        self, mock_load_config, mock_setup_logging
    ):
        """Test that main handles configuration load errors."""
        mock_load_config.side_effect = FileNotFoundError("Config not found")

        exit_code = main_entry()

        # Verify error exit
        assert exit_code == 1

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.init_db")
    @patch("btc_monitor.main.load_config")
    def test_main_handles_database_error(
        self, mock_load_config, mock_init_db, mock_setup_logging
    ):
        """Test that main handles database errors."""
        config = Mock()
        config.log_level = "INFO"
        config.logging.file = "btc_monitor.log"
        config.db_path = "btc_monitor.db"
        config.data_sources.symbols = ["BTC-USD"]
        config.rsi_overbought = 70.0
        config.rsi_oversold = 30.0
        config.refresh_interval = 300
        mock_load_config.return_value = config

        mock_init_db.side_effect = Exception("Database error")

        exit_code = main_entry()

        # Verify error exit
        assert exit_code == 1

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.init_db")
    @patch("btc_monitor.main.get_session")
    @patch("btc_monitor.main.PriceFetcher")
    @patch("btc_monitor.main.TrendAnalyzer")
    @patch("btc_monitor.main.load_config")
    @patch("btc_monitor.main.signal")
    def test_main_respects_custom_log_level(
        self,
        mock_signal,
        mock_load_config,
        mock_trend_analyzer,
        mock_price_fetcher,
        mock_get_session,
        mock_init_db,
        mock_setup_logging,
    ):
        """Test that main respects custom log level from command line."""
        config = Mock()
        config.log_level = "INFO"  # Default in config
        config.logging.file = "btc_monitor.log"
        config.db_path = "btc_monitor.db"
        config.data_sources.symbols = ["BTC-USD"]
        config.rsi_overbought = 70.0
        config.rsi_oversold = 30.0
        config.refresh_interval = 300
        mock_load_config.return_value = config

        session = Mock()
        mock_get_session.return_value = session
        mock_price_fetcher.return_value = Mock()
        mock_trend_analyzer.return_value = Mock()

        # Run with custom log level
        with patch("btc_monitor.main.shutdown_requested", False):
            exit_code = main_entry(log_level="DEBUG", once=True)

        # Verify custom log level was used
        mock_setup_logging.assert_called_once()
        call_args = mock_setup_logging.call_args[0]
        assert call_args[1] == "DEBUG"  # Custom log level

        assert exit_code == 0

    @patch("btc_monitor.main.setup_logging")
    @patch("btc_monitor.main.init_db")
    @patch("btc_monitor.main.get_session")
    @patch("btc_monitor.main.PriceFetcher")
    @patch("btc_monitor.main.TrendAnalyzer")
    @patch("btc_monitor.main.load_config")
    @patch("btc_monitor.main.signal")
    def test_main_sets_up_signal_handlers(
        self,
        mock_signal,
        mock_load_config,
        mock_trend_analyzer,
        mock_price_fetcher,
        mock_get_session,
        mock_init_db,
        mock_setup_logging,
    ):
        """Test that main sets up signal handlers."""
        config = Mock()
        config.log_level = "INFO"
        config.logging.file = "btc_monitor.log"
        config.db_path = "btc_monitor.db"
        config.data_sources.symbols = ["BTC-USD"]
        config.rsi_overbought = 70.0
        config.rsi_oversold = 30.0
        config.refresh_interval = 300
        mock_load_config.return_value = config

        session = Mock()
        mock_get_session.return_value = session
        mock_price_fetcher.return_value = Mock()
        mock_trend_analyzer.return_value = Mock()

        with patch("btc_monitor.main.shutdown_requested", False):
            exit_code = main_entry(once=True)

        # Verify signal handlers were registered
        assert mock_signal.signal.call_count >= 2  # SIGINT and SIGTERM
        assert exit_code == 0


class TestMainEntryPoints:
    """Tests for different entry points."""

    def test_root_main_imports_and_runs(self):
        """Test that root main.py can be imported and called."""
        # This test verifies the structure is correct
        # Actual execution is tested in integration tests
        root_main = Path(__file__).parent.parent / "main.py"
        assert root_main.exists(), "Root main.py should exist"

    def test_package_main_imports_and_runs(self):
        """Test that package __main__.py can be imported."""
        from btc_monitor import __main__

        # Verify the main function is accessible
        assert hasattr(__main__, "main")

    def test_pyproject_console_script_entry(self):
        """Test that console script entry point is configured."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml should exist"

        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that the console script entry point is defined
        assert "btc-monitor" in content
        assert "btc_monitor.main:main" in content


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_main_script_structure(self):
        """Test that main script has all required components."""
        from btc_monitor.main import (
            signal_handler,
            setup_logging,
            run_monitoring_cycle,
            main as main_entry,
        )

        # Verify all main functions exist
        assert callable(signal_handler)
        assert callable(setup_logging)
        assert callable(run_monitoring_cycle)
        assert callable(main_entry)

    def test_shutdown_flag_is_module_level(self):
        """Test that shutdown_requested is a module-level variable."""
        import btc_monitor.main as main_module

        assert hasattr(main_module, "shutdown_requested")
        assert isinstance(main_module.shutdown_requested, bool)
