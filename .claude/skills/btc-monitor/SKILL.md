```markdown
# btc-monitor Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you how to contribute effectively to the `btc-monitor` Python codebase. You'll learn the project's coding conventions, file organization, commit patterns, and the main development workflows for adding features, updating database models, implementing strategies, and ensuring type safety. The guide also covers testing patterns and provides handy commands for common tasks.

## Coding Conventions

- **File Naming:**  
  Use PascalCase for file names.  
  _Example:_  
  ```
  CoinMarketCap.py
  Backtest.py
  ```

- **Import Style:**  
  Use relative imports within the package.  
  _Example:_  
  ```python
  from .models import PriceData
  from .coinmarketcap import fetch_prices
  ```

- **Export Style:**  
  Use named exports (i.e., explicitly define what is exported from each module).  
  _Example:_  
  ```python
  __all__ = ["fetch_prices", "PriceData"]
  ```

- **Commit Messages:**  
  Follow [Conventional Commits](https://www.conventionalcommits.org/).  
  Prefixes: `feat`, `fix`, `chore`, `docs`  
  _Example:_  
  ```
  feat: add CoinMarketCap integration
  fix: correct timestamp parsing in Backtest
  ```

## Workflows

### Add New Feature or Module
**Trigger:** When you want to add a new capability (API integration, backtesting, logging, etc.)  
**Command:** `/new-feature`

1. Create new module file(s) in `src/btc_monitor/` (e.g., `logging.py`, `coinmarketcap.py`, `backtest.py`)
2. Update `src/btc_monitor/config.py` and/or `config/config.yaml` to add configuration for the new feature
3. Update `src/btc_monitor/main.py` to integrate or enable the new feature
4. Update CLI or scripts if user interaction is required (e.g., `src/btc_monitor/cli.py`, `scripts/run_backtest.py`)
5. Add or update documentation (`README.md`) to explain usage and configuration
6. Add new tests or test files (e.g., `tests/test_logging.py`) to cover the new feature

_Example:_
```python
# src/btc_monitor/logging.py
def setup_logging(config):
    # ...implementation...

# src/btc_monitor/main.py
from .logging import setup_logging
setup_logging(config)
```

### Extend Database Model and Update Tests
**Trigger:** When you want to add or change fields in database models (e.g., adding OHLCV fields to price data)  
**Command:** `/update-db-model`

1. Update `src/btc_monitor/models.py` to add or change model fields
2. Update data fetchers and save logic (e.g., `src/btc_monitor/coinmarketcap.py`, `main.py`) to handle new fields
3. Update or add tests to reflect new schema (e.g., change `'price'` to `'close'` in tests)
4. Update config or documentation if new fields are user-facing
5. Run and fix all tests to ensure compatibility with new schema

_Example:_
```python
# src/btc_monitor/models.py
class PriceData:
    open: float
    high: float
    low: float
    close: float  # new field
    volume: float
```

### Add or Update Strategy and Backtesting
**Trigger:** When you want to add or improve trading strategies or backtesting capabilities  
**Command:** `/add-strategy`

1. Add or update strategy logic in `src/btc_monitor/backtest.py` or new script files
2. Add or update scripts in `scripts/` (e.g., `run_backtest.py`, `compare_strategies.py`)
3. Add or update PineScript files for TradingView verification (e.g., `strategy_mystrategy.pine`)
4. Add or update test data (e.g., CSV files in `data/`)
5. Update documentation or usage instructions if needed

_Example:_
```python
# src/btc_monitor/backtest.py
def moving_average_strategy(prices, window=20):
    # ...implementation...
```

### Fix or Extend Type Checking and Stubs
**Trigger:** When you want to fix type errors or improve type safety, especially after major changes  
**Command:** `/fix-types`

1. Add or update type stubs (`*.pyi`) for modules with complex types
2. Update `pyproject.toml` or requirements for type-related dependencies (e.g., `pandas-stubs`)
3. Fix type annotations in affected source files
4. Add or update regression tests to ensure type checks pass
5. Run `mypy` and `pytest` to confirm all checks pass

_Example:_
```python
# src/btc_monitor/coinmarketcap.pyi
def fetch_prices(api_key: str) -> list[PriceData]: ...
```

## Testing Patterns

- **Test Framework:** Unknown (pytest likely, but not confirmed)
- **Test File Pattern:** All test files match `*.test.*` or are in the `tests/` directory.
- **Test Example:**
  ```python
  # tests/test_logging.py
  def test_logging_setup():
      # ...test implementation...
  ```
- **How to Run Tests:**  
  Typically with `pytest` or `python -m unittest discover tests`

## Commands

| Command         | Purpose                                                                 |
|-----------------|-------------------------------------------------------------------------|
| /new-feature    | Start the process to add a new feature or module                        |
| /update-db-model| Begin updating the database model and related tests                     |
| /add-strategy   | Add or update a trading strategy and backtesting logic                  |
| /fix-types      | Fix or extend type checking and update type stubs                       |
```