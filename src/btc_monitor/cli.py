"""CLI interface for BTC Monitor.

This module provides a command-line interface for the BTC Monitor application.
Users can run continuous monitoring, perform single analyses, check status, and view history.
"""

import argparse
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from types import FrameType
from typing import Any, Optional

from btc_monitor.config import load_config, Config
from btc_monitor.database import init_db, get_session
from btc_monitor.fetchers import PriceFetcher
from btc_monitor.indicators import RSI, MACD, MovingAverages
from btc_monitor.sentiment import (
    TwitterSentimentCollector,
    NewsSentimentCollector,
    ResearchCollector,
)
from btc_monitor.analyzer import TrendAnalyzer


def setup_logging(verbose: bool, config: Optional["Config"] = None) -> None:
    """
    Set up logging configuration.

    Args:
        verbose: Enable debug logging if True
        config: Configuration object (for log file path)
    """
    from btc_monitor.logging import setup_logging as btc_setup_logging

    log_level = "DEBUG" if verbose else "INFO"
    if config:
        log_level = config.logging.level

    log_file = config.logging.file if config else "btc_monitor.log"
    error_log_file = config.logging.error_file if config else "error.log"

    # Set up logging with the new module
    btc_setup_logging(
        config=config,
        log_level=log_level,
        log_file=log_file,
        error_log_file=error_log_file,
    )


def format_output(data: dict[str, Any], as_json: bool = False) -> str:
    """
    Format output data as text or JSON.

    Args:
        data: Dictionary containing output data
        as_json: If True, format as JSON; otherwise as readable text

    Returns:
        Formatted output string
    """
    if as_json:
        return json.dumps(data, indent=2, default=str)

    # Format as readable text
    lines = []
    for key, value in data.items():
        if isinstance(value, (int, float)):
            if key.endswith("_score") or key.endswith("_confidence") or key == "confidence":
                lines.append(f"{key.replace('_', ' ').title()}: {value:.2f}")
            else:
                lines.append(f"{key.replace('_', ' ').title()}: {value}")
        else:
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
    return "\n".join(lines)


def cmd_monitor(args: argparse.Namespace) -> None:
    """
    Run continuous monitoring.

    Args:
        args: Parsed command-line arguments
    """
    import signal
    import time

    # Load configuration
    config = load_config(args.config)

    # Set up logging
    setup_logging(args.verbose, config)

    # Initialize database
    db_path = config.db_path
    init_db(db_path)

    # Create database session
    session = get_session()

    # Initialize components
    price_fetcher = PriceFetcher(db_path=db_path)
    trend_analyzer = TrendAnalyzer(
        sentiment_window_hours=24,
        max_data_age_hours=1,
    )

    # Set up interval (command-line option overrides config)
    interval = args.interval if args.interval else config.refresh_interval

    # Set up signal handlers for graceful shutdown
    shutdown_requested = False

    def signal_handler(signum: int, frame: Optional[FrameType]) -> None:
        nonlocal shutdown_requested
        # Convert int signal number to Signals enum
        try:
            signal_enum = signal.Signals(signum)
        except ValueError:
            signal_enum = None

        signal_name: Optional[str]
        if signal_enum:
            signal_names = {
                signal.SIGINT: "SIGINT",
                signal.SIGTERM: "SIGTERM",
            }
            signal_name = signal_names.get(signal_enum, f"signal {signum}")
        else:
            signal_name = f"signal {signum}"

        logging.info(f"Received {signal_name}, initiating graceful shutdown...")
        shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Main monitoring loop
    logging.info(f"Starting monitoring loop (interval: {interval}s)")
    logging.info(f"Press Ctrl+C to stop")

    cycle_count = 0
    while not shutdown_requested:
        cycle_count += 1
        logging.info(f"Cycle #{cycle_count}")

        try:
            # Run monitoring cycle
            run_monitoring_cycle(
                config,
                session,
                price_fetcher,
                trend_analyzer,
                args.json if cycle_count == 1 else False,
            )
        except Exception as e:
            logging.error(f"Error in monitoring cycle: {e}", exc_info=True)

        # Exit if --once flag is set
        if args.once:
            logging.info("Running once, exiting...")
            break

        # Wait for next cycle (unless shutdown requested)
        if not shutdown_requested:
            logging.info(f"Sleeping for {interval} seconds until next cycle...")
            # Sleep in short intervals to respond to shutdown signals quickly
            sleep_time = min(5, interval)
            remaining_sleep = interval
            while remaining_sleep > 0 and not shutdown_requested:
                time.sleep(sleep_time)
                remaining_sleep -= sleep_time

    logging.info("Shutdown requested, stopping...")

    # Clean up
    session.close()
    logging.info("Database session closed")

    logging.info(f"BTC Monitor stopped after {cycle_count} cycles")


def run_monitoring_cycle(
    config: Config,
    session: Any,
    price_fetcher: PriceFetcher,
    trend_analyzer: TrendAnalyzer,
    output_json: bool = False,
) -> bool:
    """
    Run a single monitoring cycle.

    Args:
        config: Configuration object
        session: Database session
        price_fetcher: PriceFetcher instance
        trend_analyzer: TrendAnalyzer instance
        output_json: If True, output results as JSON

    Returns:
        True if cycle completed successfully, False otherwise
    """
    try:
        logging.info("=" * 60)
        logging.info("Starting monitoring cycle")

        # Step 1: Fetch current price
        logging.info("Step 1: Fetching current price...")
        current_price = price_fetcher.fetch_and_save_current_price()
        if current_price is None:
            logging.error("Failed to fetch price data")
            return False
        logging.info(f"Current price: ${current_price:.2f}")

        # Get timestamp for indicator calculations
        timestamp = datetime.now(timezone.utc)

        # Step 2: Calculate technical indicators
        logging.info("Step 2: Calculating technical indicators...")
        try:
            rsi = RSI(period=config.analysis.rsi_period)
            rsi.calculate_and_save(session, timestamp)
            logging.info(f"RSI calculated with period {config.analysis.rsi_period}")
        except Exception as e:
            logging.error(f"Failed to calculate RSI: {e}")

        try:
            macd = MACD(
                fast=config.analysis.macd_fast,
                slow=config.analysis.macd_slow,
                signal=config.analysis.macd_signal,
            )
            macd.calculate_and_save(session, timestamp)
            logging.info(
                f"MACD calculated ({config.analysis.macd_fast}/{config.analysis.macd_slow}/{config.analysis.macd_signal})"
            )
        except Exception as e:
            logging.error(f"Failed to calculate MACD: {e}")

        try:
            ma = MovingAverages()
            ma.calculate_and_save(session, timestamp)
            logging.info(f"Moving averages calculated: {config.analysis.moving_averages}")
        except Exception as e:
            logging.error(f"Failed to calculate moving averages: {e}")

        # Step 3: Collect sentiment
        logging.info("Step 3: Collecting sentiment data...")
        sentiment_collected = False

        # Twitter sentiment
        if (config.twitter.consumer_key and config.twitter.consumer_secret and
            config.twitter.access_token and config.twitter.access_token_secret):
            try:
                twitter_collector = TwitterSentimentCollector(
                    consumer_key=config.twitter.consumer_key,
                    consumer_secret=config.twitter.consumer_secret,
                    access_token=config.twitter.access_token,
                    access_token_secret=config.twitter.access_token_secret,
                    bearer_token=config.twitter.bearer_token,
                    max_tweets=50,
                )
                twitter_sentiment = twitter_collector.collect()
                if twitter_sentiment:
                    twitter_collector.collect_and_save(session)
                    logging.info(f"Collected {len(twitter_sentiment)} Twitter sentiment entries")
                    sentiment_collected = True
            except Exception as e:
                logging.error(f"Failed to collect Twitter sentiment: {e}")
        else:
            logging.info("Twitter API credentials not fully configured, skipping Twitter sentiment")

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
        trend_analysis = trend_analyzer.analyze(session, timestamp)

        if trend_analysis:
            logging.info(f"Trend: {trend_analysis['trend'].upper()}")
            logging.info(f"Confidence: {trend_analysis['confidence'] * 100:.1f}%")
            logging.info(f"Indicators: {trend_analysis['indicators_summary']}")

            # Output results if requested
            if output_json:
                output = {
                    "timestamp": timestamp.isoformat(),
                    "trend": trend_analysis["trend"],
                    "confidence": trend_analysis["confidence"] * 100,
                    "rsi_signal": trend_analysis.get("rsi_signal"),
                    "macd_signal": trend_analysis.get("macd_signal"),
                    "ma_signal": trend_analysis.get("ma_signal"),
                    "sentiment_signal": trend_analysis.get("sentiment_signal"),
                    "indicators_summary": trend_analysis["indicators_summary"],
                }
                print(format_output(output, as_json=True))
            else:
                print()
                print("Analysis Results:")
                print("-" * 40)
                print(format_output({
                    "Timestamp": timestamp.isoformat(),
                    "Trend": trend_analysis["trend"],
                    "Confidence (%)": trend_analysis["confidence"] * 100,
                    "RSI Signal": trend_analysis.get("rsi_signal"),
                    "MACD Signal": trend_analysis.get("macd_signal"),
                    "MA Signal": trend_analysis.get("ma_signal"),
                    "Sentiment Signal": trend_analysis.get("sentiment_signal"),
                    "Indicators Summary": trend_analysis["indicators_summary"],
                }))
                print()
        else:
            logging.warning("Trend analysis returned no result")

        logging.info("Monitoring cycle completed successfully")
        logging.info("=" * 60)
        return True

    except Exception as e:
        logging.error(f"Error in monitoring cycle: {e}", exc_info=True)
        return False


def cmd_analyze(args: argparse.Namespace) -> None:
    """
    Perform single analysis and print results.

    Args:
        args: Parsed command-line arguments
    """
    # Load configuration
    config = load_config(args.config)

    # Set up logging
    setup_logging(args.verbose, config)

    # Initialize database
    db_path = config.db_path
    init_db(db_path)

    # Create database session
    session = get_session()

    # Initialize components
    price_fetcher = PriceFetcher(db_path=db_path)
    trend_analyzer = TrendAnalyzer(
        sentiment_window_hours=24,
        max_data_age_hours=1,
    )

    logging.info("Performing single analysis...")

    # Run single monitoring cycle
    success = run_monitoring_cycle(
        config,
        session,
        price_fetcher,
        trend_analyzer,
        output_json=args.json,
    )

    # Clean up
    session.close()

    if not success:
        logging.error("Analysis failed")
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    """
    Show current trend analysis and system health from database.

    Args:
        args: Parsed command-line arguments
    """
    from sqlalchemy import desc
    from datetime import datetime, timedelta, timezone

    # Load configuration
    config = load_config(args.config)

    # Set up logging
    setup_logging(args.verbose, config)

    # Initialize database
    db_path = config.db_path
    init_db(db_path)

    # Create database session
    session = get_session()

    # Initialize components for health check
    price_fetcher = PriceFetcher(db_path=db_path)

    # Fetch latest trend analysis
    from btc_monitor.models import TrendAnalysis, PriceData, SentimentData, TechnicalIndicators
    latest_analysis = (
        session.query(TrendAnalysis)
        .order_by(desc(TrendAnalysis.timestamp))
        .first()
    )

    if latest_analysis is None:
        print("No trend analysis found in database.")
        logging.info("No trend analysis found. Run 'btc-monitor analyze' first.")
        session.close()
        sys.exit(1)

    # Check data freshness
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    latest_price = (
        session.query(PriceData)
        .order_by(desc(PriceData.timestamp))
        .first()
    )

    latest_indicators = (
        session.query(TechnicalIndicators)
        .order_by(desc(TechnicalIndicators.timestamp))
        .first()
    )

    latest_sentiment = (
        session.query(SentimentData)
        .order_by(desc(SentimentData.timestamp))
        .first()
    )

    # Determine health status
    health_status = "healthy"

    price_freshness = "unknown"
    if latest_price:
        price_age = (now - latest_price.timestamp).total_seconds() / 60
        price_freshness = f"{price_age:.0f} min old"
        if latest_price.timestamp < one_hour_ago:
            health_status = "degraded"
    else:
        price_freshness = "no data"
        health_status = "degraded"

    indicators_freshness = "unknown"
    if latest_indicators:
        indicators_age = (now - latest_indicators.timestamp).total_seconds() / 60
        indicators_freshness = f"{indicators_age:.0f} min old"
        if latest_indicators.timestamp < one_hour_ago:
            health_status = "degraded"
    else:
        indicators_freshness = "no data"
        health_status = "degraded"

    sentiment_freshness = "unknown"
    if latest_sentiment:
        sentiment_age = (now - latest_sentiment.timestamp).total_seconds() / 60
        sentiment_freshness = f"{sentiment_age:.0f} min old"
        if latest_sentiment.timestamp < one_hour_ago:
            health_status = "degraded"
    else:
        sentiment_freshness = "no data"

    # Get circuit breaker status
    circuit_breaker_status = price_fetcher.get_health().get("circuit_breaker")
    if circuit_breaker_status and circuit_breaker_status.get("state") == "OPEN":
        health_status = "degraded"

    # Prepare output data
    output = {
        "timestamp": latest_analysis.timestamp.isoformat(),
        "trend": latest_analysis.trend,
        "confidence": latest_analysis.confidence * 100,
        "indicators_summary": latest_analysis.indicators_summary,
        "health": {
            "status": health_status,
            "price_data": price_freshness,
            "indicators": indicators_freshness,
            "sentiment": sentiment_freshness,
            "circuit_breaker": circuit_breaker_status,
        },
    }

    # Format and print output
    print(format_output(output, as_json=args.json))

    # Clean up
    session.close()


def cmd_history(args: argparse.Namespace) -> None:
    """
    Show past N analyses from database.

    Args:
        args: Parsed command-line arguments
    """
    from sqlalchemy import desc

    # Load configuration
    config = load_config(args.config)

    # Set up logging
    setup_logging(args.verbose, config)

    # Initialize database
    db_path = config.db_path
    init_db(db_path)

    # Create database session
    session = get_session()

    # Fetch past N trend analyses
    from btc_monitor.models import TrendAnalysis
    analyses = (
        session.query(TrendAnalysis)
        .order_by(desc(TrendAnalysis.timestamp))
        .limit(args.count)
        .all()
    )

    if not analyses:
        print("No trend analyses found in database.")
        logging.info("No trend analyses found. Run 'btc-monitor analyze' first.")
        session.close()
        sys.exit(1)

    # Prepare output data
    output_data: list[dict[str, Any]] = []
    for analysis in analyses:
        output_data.append({
            "timestamp": analysis.timestamp.isoformat(),
            "trend": str(analysis.trend),
            "confidence": analysis.confidence * 100,
            "indicators_summary": analysis.indicators_summary,
        })

    # Format and print output
    if args.json:
        print(json.dumps(output_data, indent=2, default=str))
    else:
        print(f"\nPast {len(output_data)} analyses:")
        print("=" * 80)
        for i, data in enumerate(output_data, 1):
            print(f"\n#{i} - {data['timestamp']}")
            print(f"  Trend: {data['trend'].upper()}")
            print(f"  Confidence: {data['confidence']:.1f}%")
            print(f"  Indicators: {data['indicators_summary']}")
        print()

    # Clean up
    session.close()


def main() -> None:
    """
    Main entry point for CLI.

    Parses command-line arguments and dispatches to appropriate command handler.
    """
    # Create top-level parser
    parser = argparse.ArgumentParser(
        description="BTC Monitor - Cryptocurrency price and sentiment analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  btc-monitor monitor              # Run continuous monitoring
  btc-monitor monitor --once       # Run single analysis
  btc-monitor analyze              # Perform single analysis and print results
  btc-monitor status               # Show current trend
  btc-monitor history              # Show past 10 analyses
  btc-monitor history --count 20   # Show past 20 analyses
  btc-monitor analyze --json       # Output results as JSON
  btc-monitor monitor --verbose    # Enable debug logging
  btc-monitor analyze --config custom.yaml --interval 60
        """,
    )

    # Global options
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    # Create subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=True,
    )

    # monitor command
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Run continuous monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    monitor_parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Refresh interval in seconds (overrides config)",
    )
    monitor_parser.add_argument(
        "--once",
        action="store_true",
        help="Run single analysis then exit",
    )
    monitor_parser.set_defaults(func=cmd_monitor)

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Perform single analysis and print results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show current trend analysis from database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    status_parser.set_defaults(func=cmd_status)

    # history command
    history_parser = subparsers.add_parser(
        "history",
        help="Show past N analyses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    history_parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of past analyses to show (default: 10)",
    )
    history_parser.set_defaults(func=cmd_history)

    # Parse arguments
    args = parser.parse_args()

    # Dispatch to appropriate command handler
    args.func(args)


if __name__ == "__main__":
    main()
