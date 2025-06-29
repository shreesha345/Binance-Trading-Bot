import logging
import os
import sys
import re
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# ANSI color codes
GREEN = '\033[92m'   # Green for BUY signals and LONG positions
RED = '\033[91m'     # Red for SELL signals
GREY = '\033[90m'    # Light grey for HOLD signals and NONE positions
RESET = '\033[0m'    # Reset color

# Pattern to remove ANSI color codes
ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Custom formatter to strip ANSI codes for log files
class ANSIStrippingFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, str):
            record.msg = ansi_escape.sub('', record.msg)
        return super().format(record)

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler for regular output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

# Error log file handler
error_handler = RotatingFileHandler(
    os.path.join(logs_dir, 'errors.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_formatter = ANSIStrippingFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
root_logger.addHandler(error_handler)

# WebSocket log file handler
websocket_logger = logging.getLogger('websocket')
websocket_logger.setLevel(logging.INFO)
websocket_handler = RotatingFileHandler(
    os.path.join(logs_dir, 'websocket.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
websocket_formatter = ANSIStrippingFormatter('%(message)s')
websocket_handler.setFormatter(websocket_formatter)
websocket_logger.addHandler(websocket_handler)

# API log file handler
api_logger = logging.getLogger('api')
api_logger.setLevel(logging.INFO)
api_handler = RotatingFileHandler(
    os.path.join(logs_dir, 'api.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
api_formatter = ANSIStrippingFormatter('%(asctime)s - %(levelname)s - %(message)s')
api_handler.setFormatter(api_formatter)
api_logger.addHandler(api_handler)

# This ensures websocket logger doesn't propagate to root logger
websocket_logger.propagate = False

# This ensures API logger doesn't propagate to root logger
api_logger.propagate = False


def strip_ansi_codes(text):
    """Remove ANSI color codes from a string"""
    return ansi_escape.sub('', text)


def log_websocket(message):
    """
    Log a message to the websocket log file.
    This captures all terminal output from websocket operations.
    ANSI color codes will be displayed in the console but stripped in the log file.
    """
    websocket_logger.info(message)
    # Also print to console
    print(message)


def log_error(message, exc_info=None):
    """
    Log an error message to the errors log file.
    ANSI color codes will be stripped in the log file.
    """
    root_logger.error(message, exc_info=exc_info)


def log_api(message):
    """
    Log a message to the API log file.
    """
    api_logger.info(message)


def get_websocket_logger():
    """
    Returns the websocket logger instance.
    """
    return websocket_logger


def get_colored_signal(signal):
    """Return the signal with appropriate color coding"""
    if signal == 'BUY':
        return f"{GREEN}BUY{RESET}"
    elif signal == 'SELL':
        return f"{RED}SELL{RESET}"
    else:  # HOLD or other
        return f"{GREY}HOLD{RESET}"


def get_colored_position(position):
    """Return the position with appropriate color coding"""
    if position == 'LONG':
        return f"{GREEN}LONG{RESET}"
    elif position == 'CLOSED_LONG':
        return f"{RED}CLOSED_LONG{RESET}"
    elif position == 'NONE':
        return f"{GREY}NONE{RESET}"
    else:
        return position

