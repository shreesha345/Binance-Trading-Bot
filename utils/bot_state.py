"""
Bot state management module to track positions and orders across the application
"""

# Global state variables
position = 'NONE'  # Current position: 'NONE', 'LONG', 'SHORT'
active_buy_order = None  # Details of the current buy order
active_sell_order = None  # Details of the current sell order
buy_filled_price = None  # Price at which the buy order was filled
candle_order_created_at = None  # Timestamp of the candle when the order was created

def get_position():
    """Get current position"""
    global position
    return position

def set_position(new_position):
    """Set current position"""
    global position
    position = new_position
    return position

def get_active_buy_order():
    """Get current active buy order"""
    global active_buy_order
    return active_buy_order

def set_active_buy_order(order):
    """Set current active buy order"""
    global active_buy_order
    active_buy_order = order
    return active_buy_order

def get_active_sell_order():
    """Get current active sell order"""
    global active_sell_order
    return active_sell_order

def set_active_sell_order(order):
    """Set current active sell order"""
    global active_sell_order
    active_sell_order = order
    return active_sell_order

def get_buy_filled_price():
    """Get price at which the buy order was filled"""
    global buy_filled_price
    return buy_filled_price

def set_buy_filled_price(price):
    """Set price at which the buy order was filled"""
    global buy_filled_price
    buy_filled_price = price
    return buy_filled_price

def get_candle_order_created_at():
    """Get timestamp of the candle when the order was created"""
    global candle_order_created_at
    return candle_order_created_at

def set_candle_order_created_at(timestamp):
    """Set timestamp of the candle when the order was created"""
    global candle_order_created_at
    candle_order_created_at = timestamp
    return candle_order_created_at

def reset_state():
    """Reset all state variables"""
    global position, active_buy_order, active_sell_order, buy_filled_price, candle_order_created_at
    position = 'NONE'
    active_buy_order = None
    active_sell_order = None
    buy_filled_price = None
    candle_order_created_at = None
    return True

