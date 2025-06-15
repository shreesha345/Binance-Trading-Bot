# ➤ Loads .env values, provides API keys and global config based on MODE
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_mode():
    """Get current trading mode (live/test)"""
    return os.getenv('MODE', 'test')

def is_testnet():
    """Check if running in testnet mode"""
    return get_mode() != 'live'

def get_api_credentials():
    """Get API credentials based on current mode"""
    mode = get_mode()
    
    if mode == 'live':
        return {
            'api_key': os.getenv('BINANCE_API_KEY'),
            'secret_key': os.getenv('BINANCE_SECRET_KEY'),
            'testnet': False
        }
    else:
        return {
            'api_key': os.getenv('BINANCE_TESTNET_API_KEY'),
            'secret_key': os.getenv('BINANCE_TESTNET_SECRET_KEY'),
            'testnet': True
        }

class Config:
    """Configuration class that holds API credentials"""
    def __init__(self):
        creds = get_api_credentials()
        self.api_key = creds['api_key']
        self.secret_key = creds['secret_key']
        self.testnet = creds['testnet']

def get_config():
    """Load and return configuration instance"""
    return Config()

# Create a default config instance for direct variable access
_default_config = Config()

# Export variables for backward compatibility
BINANCE_API_KEY = _default_config.api_key
BINANCE_API_SECRET = _default_config.secret_key
TEST = _default_config.testnet
