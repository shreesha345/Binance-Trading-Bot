from binance.client import Client
import math
from utils.config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE, get_trading_symbol, get_leverage
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
                        return precision, step_size
        return 8, 0.00000001  # Default precision if not found
    except Exception as e:
        log_error(f"Error getting asset precision: {e}", exc_info=True)
        return 8, 0.00000001  # Default precision

def get_leverage(symbol):
    """
    Get the current leverage for a specific symbol
    """
    try:
        # First try to get position information
        position_info = client.futures_position_information(symbol=symbol)
        
        # If position info exists and has leverage information
        if position_info and len(position_info) > 0 and 'leverage' in position_info[0]:
            return int(position_info[0]['leverage'])
        
        # If we can't get leverage from position info, try leverage brackets
        leverage_info = client.futures_leverage_bracket(symbol=symbol)
        if leverage_info:
            # Return default max leverage for the first bracket
            for bracket in leverage_info:
                if bracket.get('symbol') == symbol and 'brackets' in bracket and len(bracket['brackets']) > 0:
                    return int(bracket['brackets'][0].get('initialLeverage', 1))
        
        # If all else fails, return default leverage
        return 1
    except Exception as e:
        log_error(f"Error getting leverage: {e}", exc_info=True)
        return 1  # Default leverage

def set_leverage(symbol, leverage):
    """
    Set the leverage for a specific symbol
    
    Args:
        symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
        leverage (int): Leverage value (1-125 depending on the asset)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        response = client.futures_change_leverage(symbol=symbol, leverage=leverage)
        log_websocket(f"Leverage for {symbol} set to {leverage}x")
        return True
    except Exception as e:
        log_error(f"Error setting leverage: {e}", exc_info=True)
        return False

def calculate_quantity(fixed_quantity, percentage, quantity_type='fixed', price_value=None, leverage=None):
    """
    Calculate the order quantity based on the configuration
    
    Args:
        fixed_quantity (float): The fixed quantity value
        percentage (float): The percentage of available balance to use (0-100)
        quantity_type (str): 'fixed' for absolute quantity, 'percentage' for percentage of balance, 
                            'price' for fixed price value in USDT
        price_value (float): The fixed price value in USDT (used when quantity_type is 'price')
        leverage (int): The leverage to use (1-125 depending on the asset)
        
    Returns:
        float: The calculated quantity for the order
    """
    try:
        # Get current price of the trading symbol
        ticker = client.futures_symbol_ticker(symbol=get_trading_symbol())
        current_price = float(ticker['price'])
        
        # Get precision and step size for the symbol
        precision, step_size = get_asset_precision(get_trading_symbol())
        
        # Get minimum notional value
        min_notional = get_min_notional(get_trading_symbol())
        
        # If leverage is provided, try to set it
        if leverage is not None:
            set_leverage(get_trading_symbol(), leverage)
        
        # Get the current leverage (will use the one just set if applicable)
        current_leverage = get_leverage(get_trading_symbol())
        
        # Calculate quantity based on the selected type
        if quantity_type.lower() == 'percentage':
            # Get available balance
            available_balance = get_available_balance()
            
            # Calculate the amount to use based on percentage
            amount_to_use = available_balance * (percentage / 100)
            
            # Apply leverage to the calculation
            effective_amount = amount_to_use * current_leverage
            
            # Calculate quantity based on amount and current price
            quantity = effective_amount / current_price
            
        elif quantity_type.lower() == 'price':
            # Use the price_value as the USDT amount to spend
            if price_value is None or price_value <= 0:
                log_error(f"Invalid price value for quantity calculation: {price_value}")
                price_value = 20.0  # Use minimum as fallback
            if float(price_value) < 20:
                log_error(f"Order not placed: price_value ({price_value}) is below Binance minimum notional (20 USDT). Increase price_value.")
                return 0  # Do not place order
            # Do NOT multiply by leverage; let Binance handle margin
            quantity = float(price_value) / current_price
            
        else:
            # Use the fixed quantity
            quantity = float(fixed_quantity)
        
        # Check if the calculated notional value meets the minimum requirement
        notional_value = quantity * current_price
        if notional_value < min_notional:
            log_websocket(f"⚠️ Calculated notional value ({notional_value:.2f} USDT) is below minimum ({min_notional} USDT). Adjusting quantity.")
            # Adjust quantity to meet minimum notional
            min_quantity = min_notional / current_price
            quantity = min_quantity
        
        # Round to step size (avoid "invalid lot size" errors)
        if step_size > 0:
            quantity = math.floor(quantity / step_size) * step_size
        
        # Round to the appropriate precision for display
        quantity = round(quantity, precision)
        
        # Log the calculation details
        if quantity_type.lower() == 'percentage':
            log_websocket(f"Calculated quantity based on {percentage}% of balance with {current_leverage}x leverage: {quantity} {get_trading_symbol().replace('USDT', '')}")
        elif quantity_type.lower() == 'price':
            log_websocket(f"Calculated quantity based on {price_value} USDT with {current_leverage}x leverage: {quantity} {get_trading_symbol().replace('USDT', '')}")
        else:
            log_websocket(f"Using fixed quantity: {quantity} {get_trading_symbol().replace('USDT', '')}")
        
        # Final check for minimum notional
        final_notional = quantity * current_price
        log_websocket(f"Order value: {final_notional:.2f} USDT (min required: {min_notional} USDT)")
        
        return quantity
            
    except Exception as e:
        log_error(f"Error calculating quantity: {e}", exc_info=True)
        # Fallback to fixed quantity if there's an error
        return float(fixed_quantity)

def get_min_notional(symbol):
    """
    Get the minimum notional value (order size in USDT) for a specific symbol
    
    Args:
        symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
        
    Returns:
        float: The minimum notional value required for orders
    """
    try:
        exchange_info = client.futures_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                for filter_item in symbol_info['filters']:
                    if filter_item['filterType'] == 'MIN_NOTIONAL':
                        return float(filter_item['notional'])
        # Default to 20 USDT if not found (Binance's typical minimum)
        return 20.0
    except Exception as e:
        log_error(f"Error getting minimum notional: {e}", exc_info=True)
        # Default to 20 USDT
        return 20.0
