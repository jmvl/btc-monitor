"""
Main BTC Monitor script.

This script orchestrates all components:
- Fetches BTC/USD price data
- Calculates technical indicators (RSI, MACD, moving averages)
- Collects sentiment from social media, news, and research
- Analyzes trend and calculates confidence score
- Saves results to database
"""

import argparse
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from btc_monitor.config import load_config
from btc_monitor.database import init_db, get_session
from btc_monitor.fetchers import PriceFetcher
from btc_monitor.coinmarketcap import CoinMarketCapFetcher
from btc_monitor.logging import setup_logging
from btc_monitor.indicators import RSI, MACD, MovingAverages
from btc_monitor.sentiment import (
    TwitterSentimentCollector,
    NewsSentimentCollector,
    ResearchCollector,
)
from btc_monitor.analyzer import TrendAnalyzer


# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """
    Handle shutdown signals (SIGINT, SIGTERM).
    """
    global shutdown_requested
    signal_names = {
        signal.SIGINT: "SIGINT",
        signal.SIGTERM: "SIGTERM",
    }
    signal_name = signal_names.get(signum, f"signal {signum}")
    logging.info(f"Received {signal_name}, initiating graceful shutdown...")
    shutdown_requested = True


def setup_logging(config_file: str, log_level: str, log_file: str, error_log_file: str):
    """
    Set up logging configuration.

    Args:
        config_file: Path to configuration file (for context in logs)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        error_log_file: Path to error log file
    """
    from btc_monitor.logging import setup_logging as btc_setup_logging

    btc_setup_logging(
        config=None,
        log_level=log_level,
        log_file=log_file,
        error_log_file=error_log_file,
    )

    logging.info(f"Configuration file: {config_file}")


def run_monitoring_cycle(
    config, session, price_fetcher: PriceFetcher, trend_analyzer: TrendAnalyzer
) -> bool:
    """
    Run a single monitoring cycle.

    Args:
        config: Configuration object
        session: Database session
        price_fetcher: PriceFetcher instance
        trend_analyzer: TrendAnalyzer instance

    Returns:
        True if cycle completed successfully, False otherwise
    """
    try:
        logging.info("=" * 60)
        logging.info("Starting monitoring cycle")

        # Step 1: Fetch current price
        logging.info("Step 1: Fetching current price...")
        price_data = price_fetcher.fetch_and_save_current_price()
        if price_data is None:
            logging.error("Failed to fetch price data")
            return False
        logging.info(f"Current price: ${price_data.price:.2f} (volume: {price_data.volume:,.0f})")

        # Step 2: Calculate technical indicators
        logging.info("Step 2: Calculating technical indicators...")
        try:
            rsi = RSI(period=config.analysis.rsi_period)
            rsi.calculate_and_save(session)
            logging.info(f"RSI calculated with period {config.analysis.rsi_period}")
        except Exception as e:
            logging.error(f"Failed to calculate RSI: {e}")

        try:
            macd = MACD(
                fast=config.analysis.macd_fast,
                slow=config.analysis.macd_slow,
                signal=config.analysis.macd_signal,
            )
            macd.calculate_and_save(session)
            logging.info(
                f"MACD calculated ({config.analysis.macd_fast}/{config.analysis.macd_slow}/{config.analysis.macd_signal})"
            )
        except Exception as e:
            logging.error(f"Failed to calculate MACD: {e}")

        try:
            ma = MovingAverages()
            ma.calculate_and_save(session)
            logging.info(f"Moving averages calculated: {config.analysis.moving_averages}")
        except Exception as e:
            logging.error(f"Failed to calculate moving averages: {e}")

        # Step 3: Collect sentiment
        logging.info("Step 3: Collecting sentiment data...")
        sentiment_collected = False

        # Twitter sentiment
        if config.twitter.bearer_token:
            try:
                twitter_collector = TwitterSentimentCollector(
                    bearer_token=config.twitter.bearer_token,
                    max_tweets=50,  # Default value
                    hours_back=24,  # Default value
                )
                twitter_sentiment = twitter_collector.collect()
                if twitter_sentiment:
                    twitter_collector.collect_and_save(session)
                    logging.info(f"Collected {len(twitter_sentiment)} Twitter sentiment entries")
                    sentiment_collected = True
            except Exception as e:
                logging.error(f"Failed to collect Twitter sentiment: {e}")
        else:
            logging.info("Twitter API key not configured, skipping Twitter sentiment")

        # News sentiment
        try:
            news_collector = NewsSentimentCollector(
                api_key=config.news.api_key,
                max_articles=config.news.max_articles,
                hours_back=config.news.hours_back,
            )
            news_sentiment = news_collector.collect()
            if news_sentiment:
                news_collector.collect_and_save(session)
                logging.info(f"Collected {len(news_sentiment)} news sentiment entries")
                sentiment_collected = True
        except Exception as e:
            logging.error(f"Failed to collect news sentiment: {e}")

        # Research sentiment
        try:
            research_collector = ResearchCollector(
                max_items=config.research.max_items,
                hours_back=config.research.hours_back,
            )
            research_sentiment = research_collector.collect()
            if research_sentiment:
                research_collector.collect_and_save(session)
                logging.info(f"Collected {len(research_sentiment)} research sentiment entries")
                sentiment_collected = True
        except Exception as e:
            logging.error(f"Failed to collect research sentiment: {e}")

        if not sentiment_collected:
            logging.warning("No sentiment data collected in this cycle")

        # Step 4: Analyze trend
        logging.info("Step 4: Analyzing trend...")
        timestamp = datetime.now(timezone.utc)
        trend_analysis = trend_analyzer.analyze(timestamp)

        if trend_analysis:
            logging.info(f"Trend: {trend_analysis.trend.upper()}")
            logging.info(f"Confidence: {trend_analysis.confidence * 100:.1f}%")
            logging.info(f"Indicators: {trend_analysis.indicators_summary}")
        else:
            logging.warning("Trend analysis returned no result")

        logging.info("Monitoring cycle completed successfully")
        logging.info("=" * 60)
        return True

    except Exception as e:
        logging.error(f"Error in monitoring cycle: {e}", exc_info=True)
        return False


def main(
    config_file: Optional[str] = None,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    error_log_file: Optional[str] = None,
    once: bool = False,
) -> int:
    """
    Main entry point for BTC Monitor.

    Args:
        config_file: Path to configuration file
        log_level: Logging level (overrides config)
        log_file: Path to log file (overrides config)
        once: Run once and exit (don't loop)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    global shutdown_requested

    try:
        # Load configuration
        logging.info("Loading configuration...")
        config = load_config(config_file)

        # Override log settings from command line
        if log_level is None:
            log_level = config.log_level
        if log_file is None:
            log_file = config.logging.file
        if error_log_file is None:
            error_log_file = config.logging.error_file

        # Set up logging
        setup_logging(config_file or "config/config.yaml", log_level, log_file, error_log_file)

        # Initialize database
        logging.info("Initializing database...")
        db_path = config.db_path
        init_db(db_path)

        # Create database session
        logging.info("Creating database session...")
        session = get_session()

        # Initialize components
        logging.info("Initializing components...")
        
        # Choose price fetcher based on configuration
        if config.coinmarketcap.api_key:
            price_fetcher = CoinMarketCapFetcher(
                api_key=config.coinmarketcap.api_key,
                db_path=db_path,
            )
            logging.info("Using CoinMarketCap API for price fetching")
        else:
            price_fetcher = PriceFetcher(db_path=db_path)
            logging.info("Using yfinance for price fetching")
        
        trend_analyzer = TrendAnalyzer(
            sentiment_window_hours=24,
            max_data_age_hours=1,
        )

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Main monitoring loop
        logging.info(f"Starting monitoring loop (interval: {config.refresh_interval}s)")
        logging.info(f"Press Ctrl+C to stop")

        cycle_count = 0
        while not shutdown_requested:
            cycle_count += 1
            logging.info(f"Cycle #{cycle_count}")

            # Run monitoring cycle
            success = run_monitoring_cycle(config, session, price_fetcher, trend_analyzer)

            if not success:
                logging.warning("Monitoring cycle failed, continuing...")

            # Exit if --once flag is set
            if once:
                logging.info("Running once, exiting...")
                break

            # Wait for next cycle (unless shutdown requested)
            if not shutdown_requested:
                logging.info(
                    f"Sleeping for {config.refresh_interval} seconds until next cycle..."
                )
                # Sleep in short intervals to respond to shutdown signals quickly
                sleep_time = min(5, config.refresh_interval)
                remaining_sleep = config.refresh_interval
                while remaining_sleep > 0 and not shutdown_requested:
                    import time

                    time.sleep(sleep_time)
                    remaining_sleep -= sleep_time

        logging.info("Shutdown requested, stopping...")

        # Clean up
        session.close()
        logging.info("Database session closed")

        logging.info(f"BTC Monitor stopped after {cycle_count} cycles")
        return 0

    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BTC Monitor - Cryptocurrency price and sentiment analysis"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (overrides config)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (overrides config)",
    )
    parser.add_argument(
        "--error-log-file",
        type=str,
        default=None,
        help="Path to error log file (overrides config)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't loop)",
    )

    args = parser.parse_args()

    sys.exit(main(args.config, args.log_level, args.log_file, args.error_log_file, args.once))
