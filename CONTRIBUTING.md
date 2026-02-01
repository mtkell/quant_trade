# Contributing to Quant Trade

Thank you for your interest in contributing! This guide explains how to submit pull requests, report issues, and develop new features.

## Getting Started

### 1. Fork & Clone

```bash
git clone https://github.com/yourusername/quant_trade.git
cd quant_trade
```

### 2. Setup Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install development dependencies
make install-dev

# Verify setup
make check  # Runs lint, type-check, and tests
```

### 3. Pre-Commit Hooks

Hooks are installed automatically via `make install-dev`. They run on every commit:

```bash
# Manually run hooks
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

## Development Workflow

### Creating a Feature Branch

```bash
# Create feature branch from main/master
git checkout -b feature/your-feature-name

# Make changes
# Write tests
# Update docs
```

### Code Style

All code must pass quality checks:

```bash
# Auto-format code
make format  # Black + isort + ruff --fix

# Check formatting
make lint    # Black + ruff check

# Type checking
make type-check  # mypy

# Run tests
make test

# Run all checks (recommended before commit)
make check
```

**Key Standards:**

- Line length: 100 characters (black)
- Python version: 3.9+ (targeted via ruff)
- Type hints: Required for new code
- Docstrings: Required for public functions/classes
- Tests: Required for new features and bug fixes

### Writing Tests

Tests go in `tests/` with `test_` prefix. Use pytest:


```python
import pytest
from trading.position import PositionState
from decimal import Decimal

def test_position_ratchet_logic():
    """Test that stop only ratchets upward."""
    pos = PositionState(entry_price=Decimal('50000'), qty_filled=Decimal('0.1'))

    # Should ratchet up
    assert pos.ratchet_stop(Decimal('51000'), Decimal('0.02')) == True

    # Should not ratchet down
    assert pos.ratchet_stop(Decimal('49000'), Decimal('0.02')) == False
```

**Run tests:**

```bash
pytest -v                          # All tests
pytest tests/test_position.py -v  # Single file
pytest -k test_ratchet -v         # By pattern
pytest -v --cov=trading            # With coverage
```

### Writing Documentation

Update relevant docs when changing behavior:

- **README.md** — High-level overview changes
- **docs/DEVELOPMENT.md** — Architecture/implementation details
- **docs/DEPLOYMENT.md** — Deployment-related changes
- **docs/ADRs/ADR-NNN.md** — Major design decisions

**ADR Format** (for significant decisions):

```markdown
# ADR-NNN: Your Decision Title

## Status
Accepted (or Proposed/Deprecated)

## Context
Explain the situation and constraints...

## Decision
What you decided and why...

## Consequences
Positive and negative impacts...
```

## Commit Messages

Use clear, descriptive commits:

```bash
# Good
git commit -m "Add Prometheus metrics endpoint for monitoring"
git commit -m "Fix ratchet stop logic to prevent downward movement"

# Avoid
git commit -m "fixes"
git commit -m "WIP"
```

**Format:**

- Imperative mood ("Add" not "Added")
- First line ≤ 50 characters
- Reference issues if applicable: "Fixes #123"

## Submitting a Pull Request

### Before Submitting

1. **Run all checks:**

   ```bash
   make check
   ```

2. **Update documentation** for user-facing changes

3. **Rebase on main** if needed:

   ```bash
   git fetch origin
   git rebase origin/main
   ```

### PR Description

Include:

- What problem does this solve?
- How does it solve it?
- Any trade-offs or alternatives considered?
- Testing instructions
- Screenshots/logs if relevant

**Template:**

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
How to verify the changes work

## Checklist
- [ ] `make check` passes
- [ ] Tests added/updated
- [ ] Docs updated
- [ ] No breaking changes (or justified)
```

### CI/CD

GitHub Actions automatically:

- Runs tests on Python 3.9-3.13
- Checks linting (ruff, black)
- Validates type hints (mypy)
- Uploads coverage reports

Your PR must pass all checks before merging.

## Reporting Issues

### Security Issues

**Do not** open a public issue for security vulnerabilities. Email [security@yourdomain.com](mailto:security@yourdomain.com) instead.

### Bug Reports

Include:

- Python version and OS
- Trading system version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs or error messages

**Example:**

```markdown
**Environment:**
- Python 3.11
- Ubuntu 22.04
- quant_trade 0.1.0

**Steps to Reproduce:**
1. Configure API credentials
2. Run `python examples/demo_trader.py`
3. Wait for entry signal

**Error:**

```text
ConnectionError: Failed to connect to Coinbase API
```

**Expected:** Should retry with exponential backoff
**Actual:** Exits immediately

### Feature Requests

Include:

- Use case and motivation
- Proposed solution (if any)
- Alternative approaches
- Any trade-offs

## Project Structure

Key files for contributors:

```text
quant_trade/
├── trading/               # Core trading logic
│   ├── position.py       # Position state + ratchet
│   ├── order_state.py    # Order state machine
│   ├── execution.py      # Sync execution engine
│   ├── persistence_sqlite.py  # Database layer
├── tests/                # Test suite (103 tests)
├── docs/                 # Documentation
│   ├── DEVELOPMENT.md    # Architecture guide
│   ├── DEPLOYMENT.md     # Production guide
│   └── ADRs/            # Architecture decisions
├── examples/             # Usage examples
├── scripts/              # Operational CLI tools
├── web/                  # Web GUI (aiohttp)
├── Makefile             # Development commands
├── pyproject.toml       # Project configuration
└── README.md            # Overview
```

## Questions?

- Check existing issues/discussions
- Review docs in `docs/` and ADRs in `docs/ADRs/`
- Open an issue with `question` label

## Code of Conduct

- Be respectful and inclusive
- Focus on code, not person
- Help others learn
- Report harassment to maintainers

## Recognition

Contributors are recognized in:

- GitHub contributors page
- Release notes for PRs
- CONTRIBUTORS.md (when created)

Thank you for contributing! 🎉
