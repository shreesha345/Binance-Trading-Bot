from binance.enums import *
from binance.client import Client
from config import BINANCE_API_KEY, BINANCE_API_SECRET, TEST
from pprint import pprint
from rich import print as rich_print
from rich.pretty import Pretty

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=TEST)


def _build_order_params(symbol, side, quantity, order_type, **kwargs):
    """Build base order parameters with optional arguments."""
    params = {
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
        'type': order_type
    }
    
    # Add parameters based on order type
    if order_type == FUTURE_ORDER_TYPE_LIMIT:
        if kwargs.get('price') is None:
            raise ValueError("Price is required for limit orders")
        params['price'] = kwargs['price']
        params['timeInForce'] = kwargs.get('time_in_force', TIME_IN_FORCE_GTC)
    
    elif order_type in [FUTURE_ORDER_TYPE_STOP, FUTURE_ORDER_TYPE_TAKE_PROFIT]:
        if kwargs.get('price') is None or kwargs.get('stop_price') is None:
            raise ValueError("Price and stop price are required for stop/take profit orders")
        params['price'] = kwargs['price']
        params['stopPrice'] = kwargs['stop_price']
        params['timeInForce'] = kwargs.get('time_in_force', TIME_IN_FORCE_GTC)
    
    elif order_type in [FUTURE_ORDER_TYPE_STOP_MARKET, FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET]:
        if kwargs.get('stop_price') is None:
            raise ValueError("Stop price is required for stop market/take profit market orders")
        params['stopPrice'] = kwargs['stop_price']
        if kwargs.get('close_position'):
            params['closePosition'] = kwargs['close_position']
    
    elif order_type == FUTURE_ORDER_TYPE_TRAILING_STOP_MARKET:
        if kwargs.get('activation_price') is None or kwargs.get('callback_rate') is None:
            raise ValueError("Activation price and callback rate are required for trailing stop market orders")
        params['activationPrice'] = kwargs['activation_price']
        params['callbackRate'] = kwargs['callback_rate']
        if kwargs.get('working_type'):
            params['workingType'] = kwargs['working_type']
    
    # Optional parameters
    for param, key in [
        ('reduce_only', 'reduceOnly'),
        ('position_side', 'positionSide'),
        ('new_client_order_id', 'newClientOrderId')
    ]:
        if kwargs.get(param):
            params[key] = kwargs[param]
    
    return params



def create_buy_order(client, symbol, quantity, **kwargs):
    """Create a futures buy order with support for different order types."""
    order_type = kwargs.pop('order_type', FUTURE_ORDER_TYPE_MARKET)
    params = _build_order_params(symbol, SIDE_BUY, quantity, order_type, **kwargs)
    return client.futures_create_order(**params)


def create_sell_order(client, symbol, quantity, **kwargs):
    """Create a futures sell order with support for different order types."""
    order_type = kwargs.pop('order_type', FUTURE_ORDER_TYPE_MARKET)
    params = _build_order_params(symbol, SIDE_SELL, quantity, order_type, **kwargs)
    return client.futures_create_order(**params)




def print_order_response(order, label="Order"):
    """Pretty-print the order response with color highlighting."""
    side = order.get('side', '').upper()
    order_type = order.get('type', '').upper()
    side_color = "green" if side == "BUY" else "red" if side == "SELL" else "yellow"
    type_color = "cyan" if order_type == "MARKET" else "magenta" if order_type == "LIMIT" else "yellow"
    
    rich_print(f"[bold]{label}[/bold]:")
    rich_print(f"  [bold]Side:[/] [{side_color}]{side}[/{side_color}]")
    rich_print(f"  [bold]Order Type:[/] [{type_color}]{order_type}[/{type_color}]")
    
    # Print the rest of the order dictionary, excluding 'side' and 'type'
    filtered = {k: v for k, v in order.items() if k not in ('side', 'type')}
    rich_print(Pretty(filtered, indent_guides=True))




def get_tick_size(symbol):
    """Fetch the tick size for a given symbol from Binance exchange info."""
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    return float(f['tickSize'])
    raise ValueError(f"Tick size not found for symbol {symbol}")




def cancel_order(client, symbol, order_id=None, orig_client_order_id=None):
    """Cancel a futures order by symbol and order ID or client order ID."""
    params = {'symbol': symbol}
    if order_id is not None:
        params['orderId'] = order_id
    elif orig_client_order_id is not None:
        params['origClientOrderId'] = orig_client_order_id
    else:
        raise ValueError("Either order_id or orig_client_order_id must be provided")
    return client.futures_cancel_order(**params)


def open_orders(symbol):
    """Fetch all open orders for a given symbol."""
    params = {'symbol': symbol}
    return client.futures_get_open_orders(symbol=symbol)

def get_all_orders(symbol):
    """Fetch all orders for a given symbol."""
    params = {'symbol': symbol}
    return client.futures_get_all_orders(**params)

def get_current_position(symbol):
    """Fetch the current position for a given symbol."""
    positions = client.futures_position_information(symbol=symbol)
    for position in positions:
        if position['symbol'] == symbol:
            return position
    raise ValueError(f"No position found for symbol {symbol}")


def get_status_order(symbol, orderId):
    """Get the status, orderId, clientOrderId, and symbol of an order."""
    status = client.futures_get_order(symbol=symbol, orderId=orderId)
    filtered = {
        'status': status.get('status'),
        'orderId': status.get('orderId'),
        'clientOrderId': status.get('clientOrderId'),
        'symbol': status.get('symbol')
    }
    return filtered


def get_recent_trades(symbol, limit=10):
    """Fetch recent trades for a given symbol."""
    trades = client.futures_recent_trades(symbol=symbol, limit=limit)
    return trades

# print(get_status_order("ETCUSDT", 210695890))  # Replace with actual orderId

# print(get_current_position("ETCUSDT"))

# print(get_all_orders("ETCUSDT"))

# if __name__ == "__main__":
#     # # Example of creating a BTCUSDT perpetual futures market buy order
#     symbol = "ETCUSDT"
#     quantity = 1  # Buy 1 ETC (adjust according to your requirements)

#     try:
#         # Get current market price (optional, for information only)
#         btc_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
#         print(f"Current {symbol} price: {btc_price}")
        
#     #     # orders = all_orders(symbol)
#     #     # print(f"Open orders for {orders}:")
#     #     # Uncomment below examples as needed
        
#     #     # Example 1: Cancel order by client order ID
#     #     # cancel_order(client, symbol, orig_client_order_id="x-Cb7ytekJ8a57f9c2cf91489eb00efd")
        
#         # Example 2: Create a market buy order
#         order = create_buy_order(
#             client=client,
#             symbol=symbol,
#             quantity=quantity
#         )
#         print_order_response(order, label="Buy Order")
        
#     #     # Example 3: Create a market sell order
#     #     # sell_order = create_sell_order(
#     #     #     client=client,
#     #     #     symbol=symbol,
#     #     #     quantity=quantity
#     #     # )
#     #     # print_order_response(sell_order, label="Sell Order")
        
#     #     # Example 4: Create a limit sell order
#     #     # tick_size = get_tick_size(symbol)
#     #     # print(f"Tick size for {symbol}: {tick_size}")
#     #     # sell_price = round((btc_price * 2) / tick_size) * tick_size  # 2% higher, adjusted to tick size
#     #     # sell_price = 17.076
#     #     # sell_order = create_sell_order(
#     #     #     client=client,
#     #     #     symbol=symbol,
#     #     #     quantity=quantity,
#     #     #     price=sell_price,
#     #     #     order_type=FUTURE_ORDER_TYPE_LIMIT
#     #     # )
#     #     # print_order_response(sell_order, label="Sell Limit Order")
        
#     except Exception as e:
#         print("An error occurred:")
#         pprint(e)
