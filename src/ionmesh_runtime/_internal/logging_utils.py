from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from .constants import DEFAULT_CONSOLE_LOG_FORMAT, DEFAULT_LOG_FILE_PATTERN, DEFAULT_LOG_FORMAT


def setup_logging(name: str) -> logging.Logger:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / DEFAULT_LOG_FILE_PATTERN.format(name=name, timestamp=timestamp)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(DEFAULT_CONSOLE_LOG_FORMAT))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def set_reproducibility(seed: int) -> None:
    np.random.seed(seed)
    try:  # pragma: no cover - optional dependency
        import torch  # type: ignore
    except Exception:
        torch = None
    if torch is not None:
        torch.manual_seed(seed)

__all__ = [
    'setup_logging',
    'set_reproducibility',
]
