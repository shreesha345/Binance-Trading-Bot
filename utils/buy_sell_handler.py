from binance.enums import *
from binance.client import Client
from config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE
from pprint import pprint
from rich import print as rich_print
from rich.pretty import Pretty
import math


client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=MODE)


def round_to_tick(price, tick_size):
    return math.floor(price / tick_size) * tick_size

def enable_hedge_mode():
    try:
        client.futures_change_position_mode(dualSidePosition=True)
        print("Hedge mode enabled.")
    except Exception as e:
        print(f"Error enabling hedge mode: {e}")

# enable_hedge_mode()

def long_buy_order(symbol:str,price:int,stopLimit:int,quantity:int):
    try:
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



def long_sell_order(symbol:str,price:int,stopLimit:int,quantity:int):
    try:
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



def short_buy_order(symbol:str,price:int,stopLimit:int,quantity:int):
    try:
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

def short_sell_order(symbol:str,price:int,stopLimit:int,quantity:int):
    try:
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