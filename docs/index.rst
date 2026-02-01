Quant Trade Documentation
=========================

A production-ready real-time trading system for Coinbase Spot markets with limit entry, dynamic trailing exit, and atomic persistence.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   ../QUICK_START.md
   ../DEVELOPMENT.md

.. toctree::
   :maxdepth: 2
   :caption: Deployment & Operations

   ../docs/DEPLOYMENT.md
   ../DOCKER_ENV_SETUP.md
   ../OPERATIONAL_TOOLS.md

.. toctree::
   :maxdepth: 2
   :caption: Architecture & Design

   ../docs/ADRs/ADR-001-limit-orders-only.md
   ../docs/ADRs/ADR-002-ratchet-stops.md
   ../docs/ADRs/ADR-003-sqlite-persistence.md
   ../docs/ADRs/ADR-004-sync-async-dual.md
   ../docs/ADRs/ADR-005-decimal-precision.md
   ../docs/ADRs/ADR-006-config-driven.md

.. toctree::
   :maxdepth: 3
   :caption: API Reference

   api/trading

.. toctree::
   :maxdepth: 2
   :caption: Contributing

   ../CONTRIBUTING.md

Features
--------

- **5-minute OHLCV candle analysis** with multi-indicator entry confirmation
- **Limit buy entries only** (no market orders)
- **Synthetic dynamic trailing exit** via stop-limit cancel/replace (ratchet-only)
- **Atomic persistence** with SQLite + restart reconciliation
- **Rate-limit policy enforcement** per endpoint
- **Optional encryption at rest** via sqlcipher
- **Async-capable architecture** with WebSocket-ready event loop
- **Structured logging** via loguru
- **Configuration-driven** (YAML)
- **Health check endpoints** for Kubernetes
- **Prometheus metrics** for monitoring

Quick Start
-----------

1. **Setup**::

    python -m venv .venv
    source .venv/bin/activate
    make install-dev

2. **Configure Credentials**::

    export CB_API_KEY=your_api_key
    export CB_API_SECRET=base64_secret
    export CB_API_PASSPHRASE=your_passphrase

3. **Run Demo**::

    python examples/demo_trader.py

4. **Run Tests**::

    make test

Project Structure
-----------------

.. code-block:: text

    quant_trade/
    ├── trading/              # Core trading logic
    │   ├── position.py       # Position state + ratchet logic
    │   ├── order_state.py    # Order state machine
    │   ├── execution.py      # Sync execution engine
    │   ├── async_execution.py  # Async execution engine
    │   └── persistence_sqlite.py  # Database layer
    ├── tests/                # Test suite (103 tests)
    ├── examples/             # Usage examples
    ├── scripts/              # Operational CLI tools
    ├── web/                  # Web GUI (aiohttp)
    ├── docs/                 # Documentation
    └── README.md             # Overview

File Reference
--------------

.. autosummary::
   :toctree: api

   trading

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
