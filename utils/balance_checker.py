from binance.client import Client
from dotenv import load_dotenv
import os
from utils.config import BINANCE_API_KEY, BINANCE_API_SECRET, TEST

# Load environment variables from .env file
load_dotenv()

def check_balance():
    """
    Check the futures account balance.
    """
    print("=" * 30)
    print("ACCOUNT BALANCE CHECK")
    print("=" * 30)
    # Initialize Binance client with appropriate credentials
    client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=TEST)
    
    info = client.futures_account()

    if 'totalWalletBalance' in info:
        print(f"TOTAL WALLET BALANCE: {info['totalWalletBalance']}")
    if 'totalUnrealizedProfit' in info:
        print(f"TOTAL UNREALIZED PROFIT: {info['totalUnrealizedProfit']}")
    if 'totalMarginBalance' in info:
        print(f"TOTAL MARGIN BALANCE: {info['totalMarginBalance']}")
    if 'availableBalance' in info:
        print(f"AVAILABLE BALANCE: {info['availableBalance']}")

    print(f"Bot Status: {'TEST' if TEST else 'LIVE'} mode")

if __name__ == "__main__":
    check_balance()