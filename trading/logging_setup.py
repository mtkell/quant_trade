"""Structured logging setup using loguru."""
import sys
from pathlib import Path
from loguru import logger as _logger


def setup_logging(
    log_file: str = "trading.log",
    level: str = "INFO",
    enable_console: bool = True,
) -> None:
    """Configure structured logging for the trading system.
    
    Args:
        log_file: Path to log file (in project root by default)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Whether to log to console as well
    """
    # Remove default handler
    _logger.remove()
    
    # Log format: timestamp, level, module, function, message
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # File logging
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _logger.add(
        str(log_path),
        format=log_format,
        level=level,
        rotation="100 MB",  # rotate when file reaches 100 MB
        retention="7 days",  # keep 7 days of logs
    )
    
    # Console logging
    if enable_console:
        _logger.add(
            sys.stdout,
            format=log_format,
            level=level,
            colorize=True,
        )


# Get logger for use in modules
logger = _logger
