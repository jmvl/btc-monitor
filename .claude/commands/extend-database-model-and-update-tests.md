---
name: extend-database-model-and-update-tests
description: Workflow command scaffold for extend-database-model-and-update-tests in btc-monitor.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /extend-database-model-and-update-tests

Use this workflow when working on **extend-database-model-and-update-tests** in `btc-monitor`.

## Goal

Expands or modifies the database model, updates code to use new fields, and ensures all tests are updated accordingly.

## Common Files

- `src/btc_monitor/models.py`
- `src/btc_monitor/*.py`
- `tests/*.py`
- `config/config.example.yaml`
- `README.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Update src/btc_monitor/models.py to add or change model fields
- Update data fetchers and save logic (e.g., src/btc_monitor/coinmarketcap.py, main.py) to handle new fields
- Update or add tests to reflect new schema (e.g., change 'price' to 'close' in tests)
- Update config or documentation if new fields are user-facing
- Run and fix all tests to ensure compatibility with new schema

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.