import logging
import os
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler


def setup_logging(log_file: str = "trading_bot.log", level: int = logging.INFO) -> logging.Logger:
    """Sets up a unified logger that outputs beautiful console messages using Rich
    and writes detailed, structured logs to a rotating file.
    
    Args:
        log_file (str): The filename for the persistent log file.
        level (int): The logging level.
        
    Returns:
        logging.Logger: The configured root-level logger.
    """
    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.DEBUG)  # Capture all logs, filter at handler level
    
    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        return logger

    # 1. Console Handler (Rich)
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        markup=True
    )
    console_handler.setLevel(level)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating File for persistence)
    # Put log file in the workspace root or parent workspace directories
    log_dir = os.path.dirname(os.path.abspath(log_file))
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # File gets all debug details
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger
