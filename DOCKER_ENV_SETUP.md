# Docker & Podman Environment Setup

## Quick Start

### 1. Copy the example .env file

```bash
cp .env.example .env

```

### 2. Edit .env with your credentials

```bash

# On Windows
notepad .env

# On macOS/Linux
nano .env

```

**Required fields** (fill these in):

```env
CB_API_KEY=your_api_key_here
CB_API_SECRET=your_api_secret_base64_here
CB_API_PASSPHRASE=your_passphrase_here

```

**Optional fields** (customize as needed):

```env
DB_PASSWORD=your_encryption_password
CONFIG_PATH=./config.yaml
LOG_LEVEL=INFO

```

### 3. Run with Docker Compose

```bash

# Start the trading engine
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f quant_trade

# Stop
docker-compose down

```

### 4. Run with Podman

```bash

# Start the trading engine
podman-compose up

# Or manually with podman:
podman run --env-file .env \
  -v "$(pwd)/state:/app/state" \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  quant-trade:latest

```

## Getting Coinbase API Credentials

### Step 1: Create API Key

1. Go to <https://www.coinbase.com/settings/api>
2. Click "+ New API Key"
3. Choose **Wallet Viewer + Trading** permissions
4. **Do NOT** grant Withdraw permission
5. Copy the API Key

### Step 2: Create API Secret

1. The API Secret will be shown once (Base64-encoded)
2. Copy it immediately and paste into `.env` as `CB_API_SECRET`

3. **Note**: The secret is only shown once, save it securely

### Step 3: Set Passphrase

1. You'll be prompted to create a passphrase
2. Choose a strong passphrase and remember it
3. Add to `.env` as `CB_API_PASSPHRASE`

### Step 4: (Optional) IP Whitelist

1. Add your IP address to the API key settings
2. This restricts API access to your IP only

## .env File Locations

### Docker Compose

- **Location**: Root directory of project
- **File**: `.env` (will be auto-loaded by docker-compose.yml)
- **Command**: `docker-compose up` (automatically uses `.env`)

### Podman

- **Location**: Anywhere, but root is recommended
- **Command**: `podman run --env-file .env ...`

### Manual Docker

- **Location**: Anywhere
- **Command**: `docker run -e CB_API_KEY=... -e CB_API_SECRET=... ...`

## Environment Variables Reference

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CB_API_KEY` | ✓ | - | Coinbase API key |
| `CB_API_SECRET` | ✓ | - | Coinbase API secret (Base64) |
| `CB_API_PASSPHRASE` | ✓ | - | Coinbase API passphrase |
| `STATE_DB` | | `/app/state/portfolio.db` | Database file path |
| `DB_PASSWORD` | | - | Database encryption password |
| `CONFIG_PATH` | | `/app/config.yaml` | Trading config file path |
| `LOG_LEVEL` | | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PAPER_TRADING` | | `false` | Set to `true` for paper trading |
| `MAX_POSITIONS` | | `10` | Max concurrent positions |
| `REQUEST_TIMEOUT` | | `30` | API request timeout (seconds) |

## Security Best Practices

### ✅ DO

- ✓ Keep `.env` out of Git (it's in `.gitignore`)
- ✓ Use strong passphrases
- ✓ Rotate API keys periodically (every 3-6 months)
- ✓ Restrict IP whitelist if possible
- ✓ Store `.env` file with restricted permissions (600)
- ✓ Use separate API keys for paper vs live trading

### ❌ DON'T

- ✗ Commit `.env` to Git
- ✗ Grant Withdraw permission
- ✗ Reuse API keys across projects
- ✗ Share credentials in Slack/email
- ✗ Use short passphrases

- ✗ Leave API keys in Docker images

## Volumes for Docker/Podman

Map these volumes for persistent data:

```yaml
volumes:
  # Trading state database
  - ./state:/app/state

  # Trading configuration
  - ./config.yaml:/app/config.yaml:ro

  # Logs (optional)
  - ./logs:/app/logs

  # Backups (optional)
  - ./backups:/app/backups

```

## Health Check

Once container is running:

```bash

# Check if service is healthy
curl http://localhost:8080/health

# Expected response:

# {"status": "ok", "database": "connected", "orchestrator": "running"}

```

## Troubleshooting

### Container won't start

```bash

# Check logs
docker-compose logs quant_trade

# Common issues:

# 1. Missing .env file → Create from .env.example

# 2. Invalid credentials → Check CB_API_* values

# 3. Port already in use → Change ports in docker-compose.yml

# 4. Database locked → Remove state/portfolio.db and restart

```

### API Authentication Failed

```bash

# Verify credentials:

# 1. Check .env file formatting (no extra spaces)

# 2. CB_API_SECRET must be Base64-encoded

# 3. Verify on https://www.coinbase.com/settings/api

# 4. Try regenerating API key if too old

```

### Podman vs Docker

Both work identically:

```bash

# Docker
docker-compose up

# Podman (drop-in replacement)
podman-compose up

```

## Example .env for Different Scenarios

### Paper Trading

```env
CB_API_KEY=your_key
CB_API_SECRET=your_secret
CB_API_PASSPHRASE=your_passphrase
PAPER_TRADING=true
CONFIG_PATH=/app/config.paper.yaml

```

### Production with Encryption

```env
CB_API_KEY=your_key
CB_API_SECRET=your_secret
CB_API_PASSPHRASE=your_passphrase
DB_PASSWORD=strong_encryption_password_here
CONFIG_PATH=/app/config.yaml
LOG_LEVEL=WARNING

```

### Development with Debug Logs

```env
CB_API_KEY=your_key
CB_API_SECRET=your_secret
CB_API_PASSPHRASE=your_passphrase
LOG_LEVEL=DEBUG
PAPER_TRADING=true

```

## Next Steps

1. Copy `.env.example` to `.env`

2. Fill in your Coinbase credentials
3. Run `docker-compose up` or `podman-compose up`

4. Verify with `curl http://localhost:8080/health`

5. Check logs for any errors

See [DEPLOYMENT.md](./docs/DEPLOYMENT.md) for full production deployment guide.
