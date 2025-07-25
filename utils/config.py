import os
import json
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

    gemini_api_key = os.getenv('GEMINI_API_KEY')

    return api_key, secret_key, gemini_api_key


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

BINANCE_API_KEY, BINANCE_API_SECRET, GEMINI_API_KEY = get_binance_keys()

# print(f"Binance API Key: {BINANCE_API_KEY}")
# print(f"Binance API Secret: {BINANCE_API_SECRET}")

# Trading parameters
# BUY_OFFSET = float(os.getenv('BUY_OFFSET', '0.0'))  # Offset for buy price
# SELL_OFFSET = float(os.getenv('SELL_OFFSET', '0.0'))  # Offset for sell price

# Trading symbol - this is the source of truth for the symbol to trade
# TRADING_SYMBOL = "ETHUSDT"

# Path to trading_config.json in the api folder
TRADING_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'trading_config.json')

def load_trading_config():
    with open(TRADING_CONFIG_PATH, 'r') as f:
        return json.load(f)

def get_quantity_type():
    return load_trading_config().get('quantity_type', 'fixed')

def get_fixed_quantity():
    return float(load_trading_config().get('quantity', os.getenv('QUANTITY', '0.01')))

def get_quantity_percentage():
    return float(load_trading_config().get('quantity_percentage', '10'))

def get_price_value():
    return float(load_trading_config().get('price_value', '10'))

def get_leverage():
    return int(load_trading_config().get('leverage', '1'))

def get_trading_symbol():
    return load_trading_config().get('symbol_name')

def get_sell_offset():
    return float(load_trading_config().get('sell_long_offset', 0))

def get_buy_offset():
    return float(load_trading_config().get('buy_long_offset', 0))

def get_candle_interval():
    return load_trading_config().get('candle_interval')

# Order settings
MAX_ORDERS = 1  # Maximum number of open orders per symbol

# Debug settings
DEBUG_MODE = True  # Set to True to enable debug output and disable screen clearing
SHOW_ERRORS = True  # Set to True to show error messages