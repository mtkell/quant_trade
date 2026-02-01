"""
Setup configuration for quant-trade package.

Supports both modern (pyproject.toml) and legacy installations.
"""
from setuptools import setup, find_packages

setup(
    name="quant-trade",
    version="0.1.0",
    description="Coinbase Spot Trading Engine with limit entry and dynamic trailing exit",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Trading System Team",
    license="MIT",
    url="https://github.com/yourusername/quant_trade",
    packages=find_packages(exclude=["tests", "docs", "examples"]),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.28.0,<3.0",
        "aiohttp>=3.8.0,<4.0",
        "pytest>=7.0.0,<8.0",
        "pytest-asyncio>=0.21.0,<1.0",
        "aiohttp-session>=2.12.0,<3.0",
        "cryptography>=40.0.0,<42.0",
        "pyyaml>=6.0,<7.0",
        "loguru>=0.7.0,<1.0",
        "pydantic>=2.0.0,<3.0",
        "sqlcipher3-binary>=3.4.0,<4.0",
    ],
    extras_require={
        "dev": [
            "black>=23.0.0,<24.0",
            "ruff>=0.1.0,<1.0",
            "mypy>=1.0.0,<2.0",
            "isort>=5.12.0,<6.0",
            "pytest-cov>=4.0.0,<5.0",
            "pre-commit>=3.0.0,<4.0",
            "sphinx>=6.0.0,<8.0",
            "sphinx-rtd-theme>=1.2.0,<2.0",
        ],
        "monitoring": [
            "prometheus-client>=0.17.0,<1.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
