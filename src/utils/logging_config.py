"""
Logging configuration for EOR Atlas.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logging(
    name: str = "eor_atlas",
    level: int = logging.INFO,
    log_dir: Optional[Path] = None,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Configure application logging.
    
    Args:
        name: Logger name
        level: Logging level
        log_dir: Directory for log files (default: None, console only)
        log_file: Log file name (default: None, console only)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_dir and log_file:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / log_file,
            maxBytes=10_000_000,  # 10 MB
            backupCount=5,
        )
        file_handler.setLevel(level)
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


# Global logger instance
logger = setup_logging()
