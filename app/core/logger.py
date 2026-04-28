import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger():
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("courseforge")
    logger.setLevel(logging.INFO)

    # Max 5MB per log file, keeps 3 backups to prevent disk saturation
    handler = RotatingFileHandler("logs/system.log", maxBytes=5*1024*1024, backupCount=3)
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logger()
