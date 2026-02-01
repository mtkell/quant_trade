#!/bin/bash
# Run full test suite with coverage

set -e

echo "🧪 Running test suite..."

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated. Activating..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo "❌ No virtual environment found. Run: make install-dev"
        exit 1
    fi
fi

# Run tests with coverage
echo "📊 Running tests with coverage..."
pytest tests/ -v \
    --cov=trading \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-report=xml \
    --tb=short

echo ""
echo "✅ Tests completed!"
echo "📈 Coverage report: htmlcov/index.html"
echo ""
