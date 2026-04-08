import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Custom log levels
CHAT_LEVEL = 25  # Between INFO and WARNING
CONN_LEVEL = 24  # Between INFO and WARNING
API_LEVEL = 23   # Between INFO and WARNING

logging.addLevelName(CHAT_LEVEL, "CHAT")
logging.addLevelName(CONN_LEVEL, "CONN")
logging.addLevelName(API_LEVEL, "API")


def chat(self, message, *args, **kwargs):
    """Log chat messages"""
    if self.isEnabledFor(CHAT_LEVEL):
        self._log(CHAT_LEVEL, message, args, **kwargs)


def conn(self, message, *args, **kwargs):
    """Log Database operations (Connection & CRUD)"""
    if self.isEnabledFor(CONN_LEVEL):
        self._log(CONN_LEVEL, message, args, **kwargs)


def api(self, message, *args, **kwargs):
    """Log API requests"""
    if self.isEnabledFor(API_LEVEL):
        self._log(API_LEVEL, message, args, **kwargs)


# Add custom methods to Logger
logging.Logger.chat = chat
logging.Logger.conn = conn
logging.Logger.api = api


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'API': '\033[35m',        # Magenta
        'CONN': '\033[96m',       # Light Cyan
        'CHAT': '\033[34m',       # Blue
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[41m',   # Red background
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger():
    """Configure and return the main logger"""
    
    # Create logger
    logger = logging.getLogger('DeepMory')
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate logs
    if logger.handlers:
        return logger
    
    # Format
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console Handler (colored)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    # Combined log file (all logs)
    combined_handler = RotatingFileHandler(
        LOGS_DIR / 'combined.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    combined_handler.setLevel(logging.DEBUG)
    combined_handler.setFormatter(detailed_formatter)
    logger.addHandler(combined_handler)
    
    # Error log file (errors only)
    error_handler = RotatingFileHandler(
        LOGS_DIR / 'error.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    # Chat log file (chat messages only)
    chat_handler = RotatingFileHandler(
        LOGS_DIR / 'chat.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    chat_handler.setLevel(CHAT_LEVEL)
    chat_handler.addFilter(lambda record: record.levelno == CHAT_LEVEL)
    chat_handler.setFormatter(detailed_formatter)
    logger.addHandler(chat_handler)
    
    # API log file (API requests only)
    api_handler = RotatingFileHandler(
        LOGS_DIR / 'api.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    api_handler.setLevel(API_LEVEL)
    api_handler.addFilter(lambda record: record.levelno == API_LEVEL)
    api_handler.setFormatter(detailed_formatter)
    logger.addHandler(api_handler)
    
    # Connection / DB log file (DB Login & CRUD only)
    conn_handler = RotatingFileHandler(
        LOGS_DIR / 'connection.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    conn_handler.setLevel(CONN_LEVEL)
    conn_handler.addFilter(lambda record: record.levelno == CONN_LEVEL)
    conn_handler.setFormatter(detailed_formatter)
    logger.addHandler(conn_handler)
    
    return logger


# Create and export logger
logger = setup_logger()
