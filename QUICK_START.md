# Quick Start Guide

Get up and running with the Coinbase Spot Trading Engine in minutes.

## Prerequisites

- Python 3.9 or higher

- Git
- Virtual environment (venv)

## 5-Minute Setup

```bash

# 1. Clone the repository
git clone https://github.com/yourusername/quant_trade.git
cd quant_trade

# 2. Install development dependencies
make install-dev

# 3. Activate virtual environment
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 4. Set Coinbase credentials (for paper trading, use mock values)
export CB_API_KEY=your_api_key
export CB_API_SECRET=your_api_secret_base64

# 5. Run tests
make test

# 6. Run demo (uses mock adapter)
python examples/demo_trader.py

```

That's it! You're ready to develop or deploy.

## Verify Installation

```bash

# Check Python version
python --version  # Should be 3.9+

# Check virtual environment is active
which python  # Should show .venv directory

# Run a quick test
pytest tests/test_position.py -v

```

## Common Commands

```bash

# Development
make format          # Auto-format code
make lint           # Check code style
make type-check     # Type checking
make test           # Run all tests
make check          # lint + type-check + test

# Docker
make docker-build   # Build Docker image
make docker-up      # Start with docker-compose
make docker-down    # Stop docker-compose

# Utilities
make clean          # Clean generated files
make help           # Show all available commands

```

## Configuration

### Create Your Config

```bash

# Copy example config
cp examples/config.example.yaml config.yaml

# Edit for your preferences
nano config.yaml  # or your favorite editor

```

### Example Configs

- **Conservative**: Low-risk, wide stops → `examples/config.conservative.yaml`

- **Aggressive**: High-frequency, tight stops → `examples/config.aggressive.yaml`

- **Paper Trading**: Simulated mode → `examples/config.paper.yaml`

## Development Workflow

```bash

# 1. Create feature branch
git checkout -b feature/my-feature

# 2. Make changes
edit trading/my_module.py

# 3. Format and test
make format
make check

# 4. Commit
git add .
git commit -m "feat: add awesome feature"

# 5. Push and create PR
git push origin feature/my-feature

```

## Testing

```bash

# Run all tests
make test

# Run specific test
pytest tests/test_trailing_ratchet.py -v

# Run with coverage
make test-cov

# Open coverage report
open htmlcov/index.html  # macOS

# or
xdg-open htmlcov/index.html  # Linux

# or
start htmlcov/index.html  # Windows

```

## Code Quality

```bash

# Auto-fix formatting
make format

# Check for issues (read-only)
make lint

# Type check
make type-check

# Run everything
make check

```

## Debugging

Enable debug logging:

```python
from trading.logging_setup import logger
logger.enable("trading")
logger.debug("This will print")

```

Use pytest debugging:

```bash
pytest tests/test_trailing_ratchet.py -v --pdb  # Drop to debugger on failure

```

Inspect database:

```bash
sqlite3 state.db
sqlite> SELECT * FROM positions;
sqlite> .schema

```

## Docker Development

```bash

# Build image
make docker-build

# Run container
docker run -it quant-trade:latest

# Run with compose
make docker-up

# View logs
docker-compose logs -f quant-trade

# Stop
make docker-down

```

## VS Code Setup

```bash

# Install recommended extensions
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-python.black-formatter
code --install-extension charliermarsh.ruff

# Or let VS Code prompt you when opening the workspace

```

## Getting Help

1. **Setup Issues** → See `docs/DEVELOPMENT.md`

2. **Deployment** → See `docs/DEPLOYMENT.md`

3. **Architecture** → See `docs/ADRs/`

4. **API Reference** → Check module docstrings in `trading/`

5. **Examples** → See `examples/` and `tests/`

## Troubleshooting

**Virtual environment not activating?**

```bash

# Recreate it
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
make install-dev

```

**Pre-commit hooks failing?**

```bash

# Reinstall hooks
pre-commit install
pre-commit run --all-files  # Run manually to fix

```

**Database corruption?**

```bash

# Clean up
rm state/portfolio.db

# Or vacuum if just needs optimization
sqlite3 state/portfolio.db "VACUUM;"

```

**API connection issues?**

```bash

# Test credentials
python -c "from trading.secrets import load_credentials; print(load_credentials())"

# Test API
curl https://api.exchange.coinbase.com/products

```

## Useful Resources

- **Python Docs**: <https://docs.python.org/3/>

- **pytest Docs**: <https://docs.pytest.org/>
- **Decimal Module**: <https://docs.python.org/3/library/decimal.html>

- **aiohttp Docs**: <https://docs.aiohttp.org/>
- **SQLite CLI**: `sqlite3 state.db`

## Next Steps

1. **Read** `docs/DEVELOPMENT.md` for detailed workflows
2. **Explore** `docs/ADRs/` for design decisions
3. **Review** `examples/config.*.yaml` for configuration options
4. **Check** `tests/` for code examples
5. **Deploy** following `docs/DEPLOYMENT.md` when ready

---

**Ready to start?**

```bash
make install-dev && source .venv/bin/activate && make test

```

Good luck! 🚀
