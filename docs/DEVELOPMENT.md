# Development Guide

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/quant_trade
cd quant_trade
chmod +x scripts/setup-dev.sh
./scripts/setup-dev.sh

Or use Docker Dev Container:

```bash
# In VS Code: Remote - Containers: Reopen in Container
# Or: docker build -t quant-trade-dev -f .devcontainer/Dockerfile .
```

### 2. Install Development Tools

```bash
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
make install-dev
```

### 3. Configure for Development

```bash
# Copy example config
cp examples/config.example.yaml config.yaml

# Set up test credentials (use mock/paper trading)
export CB_API_KEY="test_key"
export CB_API_SECRET="test_secret"
```

## Common Development Tasks

### Running Tests

```bash
# All tests
make test

# Tests with coverage report
make test-cov

# Integration tests only
make test-integration

# Specific test file
pytest tests/test_trailing_ratchet.py -v

# Specific test function
pytest tests/test_trailing_ratchet.py::test_ratchet_with_price_increase -v
```

### Code Quality

```bash
# Check all (lint + type check + test)
make check

# Individual checks
make lint          # Run ruff and black checks
make format        # Auto-format code
make type-check    # Run mypy
```

### Running the Application

```bash
# Sync demo
python examples/demo_trader.py

# Multi-pair demo
python examples/demo_multi_pair.py

# Run specific tool
python scripts/position_status.py list
python scripts/trade_history.py summary
```

### Debugging

```bash
# Run with verbose logging
export LOGLEVEL=DEBUG
python examples/demo_trader.py

# Debug specific module
pytest tests/test_execution_engine.py -v -s  # -s shows print statements

# Use pdb
python -m pdb examples/demo_trader.py
```

## Code Organization

```text
trading/              # Core trading engine
├── execution.py      # Sync execution engine
├── async_execution.py# Async execution engine
├── order_state.py    # Order state machine
├── position.py       # Position state & ratcheting
├── persistence_sqlite.py
├── coinbase_adapter.py
├── config.py         # Configuration loading
├── secrets.py        # Credential management
└── ...

scripts/              # Operational CLI tools
├── position_status.py
├── order_manager.py
├── trade_history.py
└── ...

tests/                # Test suite
├── test_execution_engine.py
├── test_trailing_ratchet.py
├── test_persistence_sqlite.py
└── ...

examples/             # Demo applications
├── demo_trader.py    # Single-pair sync example
└── demo_multi_pair.py# Multi-pair async example
```

## Architecture Decisions

### Why Limit Orders Only?

- Reduces slippage and market impact
- Predictable execution prices
- Better control over entry points

### Why Ratchet-Only Stops?

- Prevents emotional stop moving (stops always improve or stay same)
- Captures uptrend momentum while protecting downside
- Mathematically optimal for trending markets

### Why SQLite?

- Zero external dependencies
- Atomic transactions for consistency
- Built-in encryption (sqlcipher)
- Easy backups and inspection

### Async vs Sync

- Sync (`execution.py`) for single-pair simplicity
- Async (`async_execution.py`) for multi-pair scaling
- Both share identical state machines and logic

## Type Checking

This project uses type hints and mypy for safety:

```bash
# Run type checker
mypy trading/ --ignore-missing-imports

# Add type hints to files
# Use editor hints (Pylance) or manually add: variable: Type = value
```

## Testing Philosophy

1. **Unit Tests** - Test individual functions in isolation
2. **Integration Tests** - Test order flow with mocked adapter
3. **State Tests** - Verify position and order state transitions
4. **Ratchet Tests** - Critical: verify stops never move downward

Key test files:

- `test_trailing_ratchet.py` - Stop logic correctness
- `test_order_state_machine.py` - Order lifecycle
- `test_execution_engine.py` - Full engine integration
- `test_reconciliation.py` - Restart safety

## Pre-commit Hooks

Hooks are automatically installed via `make install-dev`:

- `trailing-whitespace` - Clean up trailing spaces
- `black` - Auto-format code
- `ruff` - Lint and import sorting
- `mypy` - Type checking (can be skipped with `--no-verify`)

Bypass hooks for a commit:

```bash
git commit --no-verify
```

## Making Changes

1. Create a feature branch:

   ```bash
   git checkout -b feature/my-feature
   ```

2. Make changes and test:

   ```bash
   make format
   make check
   pytest tests/
   ```

3. Commit with clear messages:

   ```bash
   git add .
   git commit -m "Add: new trailing stop feature"
   ```

4. Push and create PR:

   ```bash
   git push origin feature/my-feature
   ```

## Documentation

- **README.md** - Overview and quick start
- **docs/DEVELOPMENT_ROADMAP.md** - Feature completion status
- **docs/MULTI_PAIR_PORTFOLIO.md** - Portfolio architecture
- **OPERATIONAL_TOOLS.md** - CLI tool documentation

Generate Sphinx docs:

```bash
make docs
open docs/_build/html/index.html
```

## Troubleshooting

### Import errors

```bash
# Reinstall in editable mode
pip install -e .
```

### Test discovery issues

```bash
# Clear pycache
make clean
# Re-run tests
pytest tests/ -v
```

### Type checking too strict

```bash
# Temporarily disable for a function
# type: ignore
```

### Pre-commit hook failures

```bash
# Run formatter to fix most issues
make format
```

## Resources

- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Pytest Documentation](https://docs.pytest.org/)
- [Black Code Formatter](https://github.com/psf/black)
- [Ruff Linter](https://github.com/astral-sh/ruff)
- [Mypy Type Checker](https://www.mypy-lang.org/)

## Support

For issues or questions:

1. Check existing GitHub issues
2. Review tests for usage examples
3. Check logs: `tail -f logs/*.log`
