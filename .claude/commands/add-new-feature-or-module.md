---
name: add-new-feature-or-module
description: Workflow command scaffold for add-new-feature-or-module in btc-monitor.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-new-feature-or-module

Use this workflow when working on **add-new-feature-or-module** in `btc-monitor`.

## Goal

Implements a new feature or module, including code, configuration, and documentation updates.

## Common Files

- `src/btc_monitor/*.py`
- `config/config.yaml`
- `config/config.example.yaml`
- `README.md`
- `tests/*.py`
- `scripts/*.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create new module file(s) in src/btc_monitor/ (e.g., logging.py, coinmarketcap.py, backtest.py)
- Update src/btc_monitor/config.py and/or config/config.yaml to add configuration for the new feature
- Update src/btc_monitor/main.py to integrate or enable the new feature
- Update CLI or scripts if user interaction is required (e.g., src/btc_monitor/cli.py, scripts/run_backtest.py)
- Add or update documentation (README.md) to explain usage and configuration

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.