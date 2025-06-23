from binance.client import Client
from config import BINANCE_API_KEY, BINANCE_API_SECRET, MODE
import time
from rich import print as rich_print
from rich.pretty import Pretty

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=MODE)

def get_order_status(symbol, order_id):
    """
    Check the status of an order
    
    Args:
        symbol: Trading pair symbol
        order_id: The order ID to check
        
    Returns:
        (status, order_details) tuple
    """
    try:
        order = client.futures_get_order(symbol=symbol, orderId=order_id)
        rich_print(f"[ORDER] Status for {symbol} order {order_id}: {order.get('status', 'Unknown')}")
        return order.get('status', None), order
    except Exception as e:
        print(f"[ERROR] Fetching order status: {e}")
        return None, None

def cancel_order(symbol, order_id):
    """
    Cancel an order
    
    Args:
        symbol: Trading pair symbol
        order_id: The order ID to cancel
        
    Returns:
        Cancellation result or None if error
    """
    try:
        result = client.futures_cancel_order(symbol=symbol, orderId=order_id)
        rich_print(f"[ORDER] Cancelled {symbol} order {order_id}")
        rich_print(Pretty(result))
        return result
    except Exception as e:
        print(f"[ERROR] Cancelling order: {e}")
        return None

def wait_for_order_fill(symbol, order_id, timeout=60, check_interval=5):
    """
    Wait for an order to be filled or timeout
    
    Args:
        symbol: Trading pair symbol
        order_id: The order ID to check
        timeout: Maximum time to wait (seconds)
        check_interval: How often to check (seconds)
        
    Returns:
        True if filled, False if not filled or cancelled
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        status, order = get_order_status(symbol, order_id)
        if status == 'FILLED':
            print(f"[ORDER] Order {order_id} has been filled!")
            return True
        elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
            print(f"[ORDER] Order {order_id} status: {status}")
            return False
        print(f"[ORDER] Waiting for order {order_id} to fill. Current status: {status}")
        time.sleep(check_interval)
    
    print(f"[WARNING] Order {order_id} not filled after {timeout} seconds")
    return False
