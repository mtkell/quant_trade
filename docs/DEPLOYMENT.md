# Deployment Guide

Production deployment checklist and best practices for the trading engine.

## Pre-Deployment

### 1. Credentials & Secrets

## Never commit credentials to Git

Set via environment variables:

```bash
# Coinbase API
export CB_API_KEY=<your_api_key>
export CB_API_SECRET=<your_api_secret_base64>
export CB_API_PASSPHRASE=<your_passphrase>

# GUI access (if using web server)
export GUI_USER=admin
export GUI_PASS=<strong_password>
export GUI_SESSION_KEY=<32_byte_key>

# Database encryption (optional)
export DB_PASSWORD=<strong_password>
```

**Store in**:

- `.env` file (local development only, .gitignore'd)
- CI/CD secrets (GitHub Actions, GitLab, etc.)
- Cloud secret manager (AWS Secrets Manager, Azure Key Vault, etc.)
- 1Password, LastPass for team sharing

### 2. Configuration Review

Before deploying, review `config.yaml`:

```bash
# Check for test/demo values
grep -i "demo\|test\|mock\|fake" config.yaml

# Verify trading parameters are sensible
cat config.yaml | grep trail_pct  # Should be reasonable (0.01 - 0.05)
cat config.yaml | grep max_positions  # Should match capital allocation
```

**For production use**:

- Set `max_position_size_usd` conservatively (~1-3% of capital)
- Set `trail_pct` based on volatility (BTC 1-2%, alts 2-5%)
- Enable database encryption if trading with significant capital
- Use conservative indicator settings initially; tune after 2-4 weeks

### 3. Database Initialization

```bash
# Ensure state directory exists
mkdir -p state

# Initialize database with encryption (optional)
python -c "from trading.db_encryption import init_encrypted_db; \
           db = init_encrypted_db('state/portfolio.db'); print('DB ready')"

# Or without encryption:
python -c "from trading.persistence_sqlite import SQLitePersistence; \
           p = SQLitePersistence('state/portfolio.db'); print('DB ready')"

# Verify database integrity
sqlite3 state/portfolio.db "PRAGMA integrity_check;"
```

### 4. API Permissions

**Coinbase API requirements**:

- Create API key with **trade** permission (minimum)
- Do **NOT** grant withdraw permission
- Set IP whitelist if supported
- Consider separate keys for paper trading vs live trading
- Rotate API keys every 3-6 months

**Test API connectivity**:
```bash
python -c "from trading.coinbase_adapter import CoinbaseAdapter; \
           from trading.secrets import load_credentials; \
           creds = load_credentials(); \
           adapter = CoinbaseAdapter.from_credentials(creds); \
           print('API connected:', adapter.get_accounts()[:1])"
```

## Deployment Methods

### Option 1: Direct Python (Single Machine)

```bash
# Install production dependencies
pip install -e .

# Run trading engine
python examples/demo_multi_pair.py

# Or run with nohup for persistent background execution
nohup python examples/demo_multi_pair.py > logs/trading.log 2>&1 &
```

**Systemd service** (`/etc/systemd/system/quant-trade.service`):
```ini
[Unit]
Description=Coinbase Spot Trading Engine
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/quant_trade
ExecStart=/home/trader/quant_trade/.venv/bin/python examples/demo_multi_pair.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable quant-trade
sudo systemctl start quant-trade
sudo systemctl status quant-trade
```

Monitor logs:
```bash
sudo journalctl -u quant-trade -f  # Follow logs
```

### Option 2: Docker (Recommended)

**Build image**:
```bash
make docker-build
```

**Run container**:
```bash
docker run \
  -e CB_API_KEY=$CB_API_KEY \
  -e CB_API_SECRET=$CB_API_SECRET \
  -e CB_API_PASSPHRASE=$CB_API_PASSPHRASE \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  --name quant-trade \
  quant-trade:latest
```

**Using docker-compose**:
```bash
# Set environment variables
export CB_API_KEY=...
export CB_API_SECRET=...
export CB_API_PASSPHRASE=...

# Start services
docker-compose up -d

# View logs
docker-compose logs -f quant-trade

# Stop services
docker-compose down
```

### Option 3: Kubernetes (Production)

Example deployment manifests:

**deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quant-trade
spec:
  replicas: 1
  selector:
    matchLabels:
      app: quant-trade
  template:
    metadata:
      labels:
        app: quant-trade
    spec:
      containers:
      - name: quant-trade
        image: quant-trade:v1.0.0
        imagePullPolicy: IfNotPresent
        env:
        - name: CB_API_KEY
          valueFrom:
            secretKeyRef:
              name: coinbase-creds
              key: api_key
        - name: CB_API_SECRET
          valueFrom:
            secretKeyRef:
              name: coinbase-creds
              key: api_secret
        - name: CB_API_PASSPHRASE
          valueFrom:
            secretKeyRef:
              name: coinbase-creds
              key: passphrase
        volumeMounts:
        - name: state
          mountPath: /app/state
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: state
        persistentVolumeClaim:
          claimName: quant-trade-state
      - name: config
        configMap:
          name: quant-trade-config
```

Deploy:
```bash
# Create secrets
kubectl create secret generic coinbase-creds \
  --from-literal=api_key=$CB_API_KEY \
  --from-literal=api_secret=$CB_API_SECRET \
  --from-literal=passphrase=$CB_API_PASSPHRASE

# Create config
kubectl create configmap quant-trade-config --from-file=config.yaml

# Deploy
kubectl apply -f deployment.yaml

# Monitor
kubectl logs -f deployment/quant-trade
kubectl get pods
```

## Monitoring & Observability

### 1. Health Checks

Check service health:
```bash
# Liveness (is it running?)
curl http://localhost:8080/health/live

# Readiness (can it serve requests?)
curl http://localhost:8080/health/ready

# Full health
curl http://localhost:8080/health
```

### 2. Logging

Log location: `stdout` via loguru

Configure log level:
```python
# In code
from trading.logging_setup import logger
logger.enable("trading")
logger.debug("Debug messages enabled")
```

View logs:
```bash
# Direct output
python examples/demo_multi_pair.py

# With file capture
python examples/demo_multi_pair.py 2>&1 | tee logs/trading.log

# Docker
docker logs quant-trade -f

# Kubernetes
kubectl logs deployment/quant-trade -f
```

### 3. Position Monitoring

Check open positions:
```bash
# Via CLI tool
python scripts/position_status.py list

# Via database
sqlite3 state/portfolio.db "SELECT * FROM positions;"

# Via API
curl http://localhost:8080/api/positions
```

### 4. Metrics (Optional)

Prometheus metrics endpoint (if enabled):
```bash
curl http://localhost:8080/metrics
```

Includes:

- Trade count
- P&L metrics
- Order latency
- API call latency
- Stop ratchet frequency

## Backup & Recovery

### Daily Backups

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup database
cp state/portfolio.db $BACKUP_DIR/portfolio.db

# Backup config
cp config.yaml $BACKUP_DIR/config.yaml

# Keep only last 30 days
find backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
```

Schedule via cron:
```bash
0 2 * * * cd /home/trader/quant_trade && bash backup.sh
```

### Recovery

```bash
# Stop the service
systemctl stop quant-trade

# Restore database
cp backups/20260125/portfolio.db state/portfolio.db

# Restart
systemctl start quant-trade

# Verify
systemctl status quant-trade
```

## Emergency Procedures

### Liquidate All Positions

```bash
# Via CLI
python scripts/order_manager.py force-exit all

# Or manually via database
sqlite3 state/portfolio.db "UPDATE positions SET status='FORCED_EXIT';"
```

Then manually place market sell orders for all open positions.

### Kill Switch

```bash
# Stop the service immediately
systemctl stop quant-trade

# Or kill the process
pkill -f "python.*demo_multi_pair.py"

# Verify it's stopped
ps aux | grep python
```

### Restart After Crash

```bash
# Service will auto-restart (if configured with Restart=on-failure)
systemctl status quant-trade

# Or manual restart
systemctl restart quant-trade

# Check logs for errors
journalctl -u quant-trade -n 50
```

## Performance Tuning

### Memory Usage

Default memory: ~100-200MB per 10 positions

Optimize:

- Archive old trades (separate database)
- Reduce max_positions if memory is tight
- Use PyPy for better performance (if supported)

### CPU Usage

Monitor:
```bash
top -p $(pgrep -f "demo_multi_pair.py")
```

Typical: <5% CPU for 10-20 positions

### Database Performance

Check database size:
```bash
ls -lh state/portfolio.db
```

Vacuum to reclaim space:
```bash
sqlite3 state/portfolio.db "VACUUM;"
```

## Troubleshooting

### API Connection Issues

```bash
# Test Coinbase API
curl -X GET "https://api.exchange.coinbase.com/products"

# Check credentials
python -c "from trading.secrets import load_credentials; \
           print(load_credentials())"
```

### Database Corruption

```bash
# Check integrity
sqlite3 state/portfolio.db "PRAGMA integrity_check;"

# Rebuild if corrupted
sqlite3 state/portfolio.db "VACUUM; REINDEX;"
```

### Orders Not Filling

Check:

1. Limit price is reasonable (not too far from market)
2. Account has sufficient balance
3. API key has trade permission
4. Order not cancelled prematurely

## Success Metrics

After 1 week of production:

- [ ] No crashes (or proper auto-restart)
- [ ] All positions reconciled correctly
- [ ] Trailing stops executing as expected
- [ ] Logs are clean (no errors/warnings)
- [ ] P&L metrics reasonable

After 1 month:

- [ ] Win rate > 40% (depends on strategy)
- [ ] Average trade duration realistic
- [ ] No database corruption
- [ ] Backup/restore tested successfully
