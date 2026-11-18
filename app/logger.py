import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv


class Logger_App:
    def __init__(self, name: str):
        self.name = name
        self.console = os.getenv("LOG_CONSOLE", "false").strip().lower() in ("1", "true", "yes", "on")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.log_dir = Path(os.getenv("LOG_DIR", str(Path(__file__).resolve().parents[1] / "data" / "logs")))
        self.log_file = self.log_dir / os.getenv("LOG_FILE", "app.log")

        self.log_format = (
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        )

        self.date_format = "%Y-%m-%d %H:%M:%S"


    def get_logger(self) -> logging.Logger:
        logger = logging.getLogger(self.name)

        if logger.handlers:
            return logger

        logger.setLevel(self.log_level)
        logger.propagate = False

        formatter = logging.Formatter(
            fmt=self.log_format,
            datefmt=self.date_format
        )

        # Console
        if self.console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(formatter)

            logger.addHandler(console_handler)

        # File
        self.log_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=5*1024*1024,
            backupCount=3,
            encoding="utf-8"
        )

        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        return logger

def configure_logging():
    """Call once at the application boundary, never during module imports."""
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    return Logger_App('worldgen').get_logger()
