import os
from dotenv import load_dotenv
from binance.client import Client  # Importing Client from python-binance

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Get MODE from environment (default to 'live' if not set)
MODE_ENV = os.getenv('MODE', 'live').lower()
# print(f"MODE from .env: '{MODE_ENV}'")

def get_binance_keys():
    """
    Returns the appropriate Binance API key and secret based on MODE.
    If MODE is 'test' or 'true', use testnet keys.
    If MODE is 'live' or 'false', use mainnet keys.
    """
    if MODE_ENV in ['test', 'true']:
        api_key = os.getenv('BINANCE_TESTNET_API_KEY')
        secret_key = os.getenv('BINANCE_TESTNET_SECRET_KEY')
    else:
        api_key = os.getenv('BINANCE_API_KEY')
        secret_key = os.getenv('BINANCE_SECRET_KEY')

    return api_key, secret_key


def print_mode_status():
    """
    Prints 'true' if MODE is 'test' or 'true', otherwise prints 'false'.
    """
    if MODE_ENV in ['test', 'true']:
        print('true')
        return True
    else:
        print('false')
        return False

# Example usage:
# api_key, secret_key = get_binance_keys()
MODE = print_mode_status()
TEST = MODE  # For backward compatibility

BINANCE_API_KEY, BINANCE_API_SECRET = get_binance_keys()

# print(f"Binance API Key: {BINANCE_API_KEY}")
# print(f"Binance API Secret: {BINANCE_API_SECRET}")

# Trading parameters
QUANTITY = float(os.getenv('QUANTITY', '0.01'))  # Default quantity for trades
BUY_OFFSET = float(os.getenv('BUY_OFFSET', '0.0'))  # Offset for buy price
SELL_OFFSET = float(os.getenv('SELL_OFFSET', '0.0'))  # Offset for sell price

# Trading symbol - this is the source of truth for the symbol to trade
TRADING_SYMBOL = "ETHUSDT"

# Time settings
CANDLE_INTERVAL = '1m'  # Candle interval ('1m', '5m', '15m', '1h', etc.)

# Order settings
MAX_ORDERS = 1  # Maximum number of open orders per symbol

# Debug settings
DEBUG_MODE = True  # Set to True to enable debug output and disable screen clearing
SHOW_ERRORS = True  # Set to True to show error messages