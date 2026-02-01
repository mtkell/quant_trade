#!/bin/bash
# Setup development environment for quant-trade

set -e

echo "🚀 Setting up quant-trade development environment..."

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "📥 Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install development dependencies
echo "📚 Installing development dependencies..."
pip install -e ".[dev,monitoring]"

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run initial checks
echo "✅ Running initial code checks..."
make check || true

echo ""
echo "✨ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate the environment: source .venv/bin/activate"
echo "  2. Configure Coinbase credentials: export CB_API_KEY=... CB_API_SECRET=... CB_API_PASSPHRASE=..."
echo "  3. Copy config: cp examples/config.example.yaml config.yaml"
echo "  4. Run tests: make test"
echo "  5. Run demo: python examples/demo_trader.py"
echo ""
