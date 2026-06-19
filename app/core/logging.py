import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging() -> None:
    Path('logs').mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            RotatingFileHandler(
                'logs/app.log',
                maxBytes=10_000_000,
                backupCount=5
            ),
            logging.StreamHandler(sys.stdout)
        ]
    )