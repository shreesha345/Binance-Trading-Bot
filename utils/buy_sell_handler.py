from binance.enums import *
from binance.client import Client
from utils.config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE
from pprint import pprint
from rich import print as rich_print
from rich.pretty import Pretty
import math
from utils.order_storage import save_filled_order, enrich_order_details


client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=MODE)


def round_to_tick(price, tick_size):
    """
    Round price to the closest valid tick size for the exchange
    Floor the result to be conservative with stop loss prices
    """
    # Floor to the nearest tick size (this is what Binance appears to do)
    # This will ensure prices match exactly with what the exchange expects
    rounded = math.floor(price / tick_size) * tick_size
    
    # Format to max 2 decimal places to avoid floating point issues
    return round(rounded, 2)

def enable_hedge_mode():
    try:
        client.futures_change_position_mode(dualSidePosition=True)
        print("Hedge mode enabled.")
    except Exception as e:
        print(f"Error enabling hedge mode: {e}")

# enable_hedge_mode()

def long_buy_order(symbol:str, price:float, stopLimit:float, quantity:float):
    try:
        # Round price and stopLimit to 2 decimal places
        price = round(price, 2)
        stopLimit = round(stopLimit, 2)
        
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY,
            price=price,
            stopPrice=stopLimit,
            type=FUTURE_ORDER_TYPE_STOP,
            positionSide='LONG',  # Required in hedge mode
            quantity=quantity
        )
        return order
    except Exception as e:
        print(f"Error creating long buy order: {e}")
        return None



def long_sell_order(symbol:str, price:float, stopLimit:float, quantity:float):
    try:
        # Round price and stopLimit to 2 decimal places
        price = round(price, 2)
        stopLimit = round(stopLimit, 2)
        
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL,
            price=price,
            stopPrice=stopLimit,
            type=FUTURE_ORDER_TYPE_STOP,
            positionSide='LONG',  # Required in hedge mode
            quantity=quantity,
        )
        return order
    except Exception as e:
        print(f"Error creating long sell order: {e}")
        return None



def short_buy_order(symbol:str, price:float, stopLimit:float, quantity:float):
    try:
        # Round price and stopLimit to 2 decimal places
        price = round(price, 2)
        stopLimit = round(stopLimit, 2)
        
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY,
            price=price,
            stopPrice=stopLimit,
            type=FUTURE_ORDER_TYPE_STOP,
            positionSide='SHORT',  # Required in hedge mode
            quantity=quantity
        )
        return order
    except Exception as e:
        print(f"Error creating short buy order: {e}")
        return None

def short_sell_order(symbol:str, price:float, stopLimit:float, quantity:float):
    try:
        # Round price and stopLimit to 2 decimal places
        price = round(price, 2)
        stopLimit = round(stopLimit, 2)
        
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL,
            price=price,
            stopPrice=stopLimit,
            type=FUTURE_ORDER_TYPE_STOP,
            positionSide='SHORT',  # Required in hedge mode
            quantity=quantity
        )
        return order
    except Exception as e:
        print(f"Error creating short sell order: {e}")
        return None


def get_tick_size(symbol: str):
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    return float(f['tickSize'])
    raise ValueError(f"Tick size not found for symbol {symbol}")


def format_order_info(order):
    """
    Extract and format key order information
    """
    if not order:
        return None
    
    # Determine order type display
    order_type = order.get('type', '')
    if order_type == 'STOP':
        order_type = 'STOP Limit'
    
    formatted_info = {
        'orderId': order.get('orderId'),
        'status': order.get('status'),
        'clientOrderId': order.get('clientOrderId'),
        'price': order.get('price'),
        'side': order.get('side'),
        'type': order_type,
        'stopPrice': order.get('stopPrice')
    }
    
    return formatted_info

def print_order_info(order):
    """
    Print formatted order information
    """
    info = format_order_info(order)
    if info:
        rich_print(Pretty(info))
    else:
        print("No order information available")

def buy_long(symbol, price, stop_limit, quantity):
    """
    Create a long buy order with stop price
    
    Args:
        symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
        price (float): Order price
        stop_limit (float): Stop price to trigger the order
        quantity (float): Order quantity
        
    Returns:
        Order details dictionary or None if error
    """
    try:
        # Round price and stop_limit to 2 decimal places
        price = round(price, 2)
        stop_limit = round(stop_limit, 2)
        
        # Get tick size and adjust to valid exchange values
        tick_size = get_tick_size(symbol)
        price = round_to_tick(price, tick_size)
        stop_limit = round_to_tick(stop_limit, tick_size)
        
        rich_print(f"[BUY_LONG] Rounded price: {price}, stop_limit: {stop_limit}")
        order = long_buy_order(symbol, price=price, stopLimit=stop_limit, quantity=quantity)
        
        if order:
            # No longer saving open orders
            rich_print(f"[BUY_LONG] Order created: {order.get('orderId')}")
        
        return order
    except Exception as e:
        rich_print(f"Error in buy_long: {e}")
        return None

def sell_long(symbol, price, stop_limit, quantity):
    """
    Create a long sell order with stop price (for stop-loss)
    
    Args:
        symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
        price (float): Order price - should be the same as stop_limit for consistency
        stop_limit (float): Stop price to trigger the order
        quantity (float): Order quantity
        
    Returns:
        Order details dictionary or None if error
    """
    try:
        # Round price and stop_limit to 2 decimal places
        price = round(price, 2)
        stop_limit = round(stop_limit, 2)
        
        # Make price and stop_limit the same for consistent execution
        # Use stop_limit as the source of truth
        price = stop_limit
        
        # Get tick size and adjust to valid exchange values
        tick_size = get_tick_size(symbol)
        price = round_to_tick(price, tick_size)
        stop_limit = round_to_tick(stop_limit, tick_size)
        
        # Make sure price and stop_limit are identical
        price = stop_limit
        
        rich_print(f"[SELL_LONG] Rounded price: {price}, stop_limit: {stop_limit}")
        order = long_sell_order(symbol, price=price, stopLimit=stop_limit, quantity=quantity)
        
        if order:
            # No longer saving open orders
            rich_print(f"[SELL_LONG] Order created: {order.get('orderId')}")
        
        return order
    except Exception as e:
        rich_print(f"Error in sell_long: {e}")
        return None



if __name__ == "__main__":
    symbol = 'ETHUSDT'
    quantity = 1  # Adjust for your capital and margin settings

    # # Example usage
    # buy = long_buy_order(symbol, price=2505.73, stopLimit=2505.23, quantity=quantity)
    # sell = long_sell_order(symbol, price=2498.97, stopLimit=2499.47, quantity=quantity)
    # print("Order buy created:")
    # print_order_info(buy)
    # print("Order sell created:")
    # print_order_info(sell)
    # # long_sell_order(symbol, 31000, 31100, quantity)
    # # short_buy_order(symbol, 29000, 28900, quantity)

    # tick_size = get_tick_size(symbol)
    # price = round_to_tick(84.38, tick_size)
    # stopLimit = round_to_tick(85.40, tick_size)

    # print(f"Tick size for {symbol}: {tick_size}")
    # print(f"Rounded price: {price}, Rounded stop limit: {stopLimit}")

    # short_sell_order(symbol, price=104526.05, stopLimit=104526.10, quantity=quantity)
    # print(get_tick_size('LTCUSDT'))
    # Print all orders for verification
    # pprint(client.futures_get_all_orders(symbol=symbol))