from binance.client import Client
import math
from utils.config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE, TRADING_SYMBOL
from utils.logger import log_websocket, log_error

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=MODE)

def get_available_balance(asset='USDT'):
    """
    Get the available balance for a specific asset in the futures account
    """
    try:
        account_info = client.futures_account()
        for balance in account_info['assets']:
            if balance['asset'] == asset:
                return float(balance['availableBalance'])
        return 0
    except Exception as e:
        log_error(f"Error getting available balance: {e}", exc_info=True)
        return 0

def get_asset_precision(symbol):
    """
    Get the quantity precision for a specific symbol
    """
    try:
        exchange_info = client.futures_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                for filter_item in symbol_info['filters']:
                    if filter_item['filterType'] == 'LOT_SIZE':
                        # Calculate precision from stepSize
                        step_size = float(filter_item['stepSize'])
                        precision = 0
                        if step_size < 1:
                            precision = len(str(step_size).split('.')[-1].rstrip('0'))
                        return precision
        return 8  # Default precision if not found
    except Exception as e:
        log_error(f"Error getting asset precision: {e}", exc_info=True)
        return 8  # Default precision

def calculate_quantity(fixed_quantity, percentage, quantity_type='fixed'):
    """
    Calculate the order quantity based on the configuration
    
    Args:
        fixed_quantity (float): The fixed quantity value
        percentage (float): The percentage of available balance to use (0-100)
        quantity_type (str): 'fixed' for absolute quantity or 'percentage' for percentage of balance
        
    Returns:
        float: The calculated quantity for the order
    """
    try:
        if quantity_type.lower() == 'percentage':
            # Get available balance
            available_balance = get_available_balance()
            
            # Calculate the amount to use based on percentage
            amount_to_use = available_balance * (percentage / 100)
            
            # Get current price of the trading symbol
            ticker = client.futures_symbol_ticker(symbol=TRADING_SYMBOL)
            current_price = float(ticker['price'])
            
            # Calculate quantity based on amount and current price
            quantity = amount_to_use / current_price
            
            # Get precision for the symbol
            precision = get_asset_precision(TRADING_SYMBOL)
            
            # Round to the appropriate precision
            quantity = round(quantity, precision)
            
            log_websocket(f"Calculated quantity based on {percentage}% of balance ({available_balance} USDT): {quantity} {TRADING_SYMBOL.replace('USDT', '')}")
            return quantity
        else:
            # Return the fixed quantity
            return fixed_quantity
    except Exception as e:
        log_error(f"Error calculating quantity: {e}", exc_info=True)
        # Fallback to fixed quantity if there's an error
        return fixed_quantity
