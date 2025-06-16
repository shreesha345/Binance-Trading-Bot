import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Get MODE from environment (default to 'live' if not set)
MODE = os.getenv('MODE', 'live').lower()
print(f"MODE from .env: '{MODE}'")

def get_binance_keys():
    """
    Returns the appropriate Binance API key and secret based on MODE.
    If MODE is 'test' or 'true', use testnet keys.
    If MODE is 'live' or 'false', use mainnet keys.
    """
    if MODE in ['test', 'true']:
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
    if MODE in ['test', 'true']:
        print('true')
        return True
    else:
        print('false')
        return False

# Example usage:
# api_key, secret_key = get_binance_keys()
MODE = print_mode_status()

BINANCE_API_KEY, BINANCE_API_SECRET = get_binance_keys()