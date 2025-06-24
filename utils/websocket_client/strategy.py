from datetime import datetime
from utils.buy_sell_handler import buy_long, sell_long
from utils.order_utils import get_order_status, cancel_order
from utils.bot_state import (
    get_position, set_position,
    get_active_buy_order, set_active_buy_order,
    get_active_sell_order, set_active_sell_order,
    get_buy_filled_price, set_buy_filled_price,
    get_candle_order_created_at, set_candle_order_created_at
)
from utils.config import (
    QUANTITY, BUY_OFFSET, SELL_OFFSET
)
from rich import print as rich_print
from rich.pretty import Pretty

# Strategy summary:
# BUY: Place a buy order at current candle's HA_High + BUY_OFFSET 
# SELL/STOP LOSS: Place a sell order at current candle's HA_Low - SELL_OFFSET
# Orders are placed at the beginning of each candle to prepare for the next price movement

def add_strategy_to_historical_data(historical_data):
    """Process historical data for display without creating actual orders"""
    for candle in historical_data:
        # For historical data, we just add placeholder values
        candle.update({
            "signal": "HOLD",
            "entry": None,
            "stop_loss": None,
            "position": "NONE"
        })
    return historical_data

def format_row_with_strategy(kline, symbol, previous_ha_candle, allow_trading=True):
    """Process new candle data and execute the trading strategy"""
    # Create basic row data from kline
    row_data = {
        "symbol": symbol.upper(),
        "time": datetime.fromtimestamp(int(kline["t"])/1000).strftime("%H:%M"),
        "open": float(kline["o"]),
        "high": float(kline["h"]),
        "low": float(kline["l"]),
        "close": float(kline["c"]),
        "timestamp": int(kline["t"]),
        "signal": "HOLD",
        "position": get_position(),
        "entry": None,
        "stop_loss": None
    }
      # Reset position from CLOSED_LONG to NONE after one candle
    if row_data["position"] == "CLOSED_LONG":
        # For the next candle after CLOSED_LONG, reset to NONE
        # This ensures "CLOSED_LONG" only shows for the candle where the SELL happens
        row_data["position"] = "NONE"
        row_data["stop_loss"] = None
        set_position("NONE")
    
    # Calculate Heikin Ashi values
    from utils.websocket_client.heikin_ashi import calculate_heikin_ashi
    ha_values = calculate_heikin_ashi(row_data, previous_ha_candle)
    row_data.update(ha_values)
    
    # Current candle values
    current_candle_high = row_data["high"]
    current_candle_low = row_data["low"]
    current_close = float(kline["c"])
      # Calculate buy parameters - use HA_High + BUY_OFFSET - truncate to 2 decimal places
    buy_price = int((row_data["ha_high"] + BUY_OFFSET) * 100) / 100
    
    # Use previous candle high for stop limit to avoid immediate trigger
    prev_candle_high = previous_ha_candle.get("high", current_candle_high) if previous_ha_candle else current_candle_high
    buy_stop_limit = int(prev_candle_high * 100) / 100
    
    # Calculate sell parameters - set both price and stop_limit to HA_Low minus offset
    sell_stop_limit = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
    
    # Set display values
    if get_position() == "LONG":
        buy_filled_price = get_buy_filled_price() or buy_price
        row_data["entry"] = int(buy_filled_price * 100) / 100
        # For stop loss when in LONG position, use the current candle's HA_Low minus SELL_OFFSET
        row_data["stop_loss"] = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
    elif get_position() == "NONE":
        row_data["entry"] = int(buy_price * 100) / 100
        row_data["stop_loss"] = int(sell_stop_limit * 100) / 100
    
    # Check active buy orders
    active_buy_order = get_active_buy_order()
    if active_buy_order and get_position() == "NONE":
        if get_candle_order_created_at() != row_data["timestamp"]:
            order_id = active_buy_order.get("orderId")
            status, order_details = get_order_status(symbol, order_id)
            
            if status == "NEW":
                rich_print(f"[STRATEGY] Cancelling unfilled buy order from previous candle: {order_id}")
                cancel_order(symbol, order_id)
                set_active_buy_order(None)
            elif status == "FILLED":
                rich_print(f"[STRATEGY] Buy order filled: {order_id}")
                set_position("LONG")
                filled_price = int(float(order_details.get("price", 0)) * 100) / 100
                set_buy_filled_price(filled_price)
                row_data["signal"] = "BUY"
                row_data["position"] = "LONG"
                row_data["entry"] = filled_price                  # Create immediate stop loss
                current_price = float(kline["c"])                # Use current candle HA_Low for the stop loss trigger price
                stop_trigger_price = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
                
                rich_print(f"[STRATEGY] Creating initial stop loss after fill with trigger at: {stop_trigger_price}")
                sell_order = sell_long(symbol, price=stop_trigger_price, stop_limit=stop_trigger_price, quantity=QUANTITY)
                if sell_order:
                    set_active_sell_order(sell_order)
                    # Update the stop_loss in row_data with the actual trigger price (stopPrice)
                    # This makes more sense for display purposes because it's when the stop loss is triggered
                    actual_trigger_price = float(sell_order.get('stopPrice', stop_trigger_price))
                    row_data["stop_loss"] = actual_trigger_price
                    rich_print(f"[STRATEGY] Stop Loss order placed with trigger price: {actual_trigger_price}, order price: {sell_order.get('price')}")
                    rich_print(Pretty(sell_order))
    
    # Place new orders if allowed - always place order to be ready for next candle
    if get_position() == "NONE" and allow_trading:
        # Check if we already have an active buy order
        active_buy_order = get_active_buy_order()
        
        # If there's an existing order from a previous candle, check its status
        if active_buy_order:
            order_id = active_buy_order.get("orderId")
            status, order_details = get_order_status(symbol, order_id)
            
            if status == "FILLED":
                # Order was filled between candles
                rich_print(f"[STRATEGY] Buy order filled: {order_id}")
                set_position("LONG")
                filled_price = int(float(order_details.get("price", 0)) * 100) / 100
                set_buy_filled_price(filled_price)
                row_data["signal"] = "BUY"
                row_data["position"] = "LONG"
                row_data["entry"] = filled_price                # Create immediate stop loss after buy is filled
                # Use current candle HA_Low for the stop loss calculation
                stop_loss_price = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
                rich_print(f"[STRATEGY] Creating initial stop loss after fill at: {stop_loss_price}")
                # Using the same price and stop_limit to ensure they're identical
                sell_order = sell_long(symbol, price=stop_loss_price, stop_limit=stop_loss_price, quantity=QUANTITY)
                if sell_order:
                    set_active_sell_order(sell_order)
                    # Update the stop_loss in row_data with the trigger price from the order
                    actual_stop_price = float(sell_order.get('stopPrice', stop_loss_price))
                    row_data["stop_loss"] = actual_stop_price
                    rich_print(f"[STRATEGY] Stop Loss order placed at trigger price: {actual_stop_price}")
                    rich_print(Pretty(sell_order))
            else:                # Cancel existing order to place a new one with updated prices
                rich_print(f"[STRATEGY] Cancelling existing buy order to update with new prices: {order_id}")
                cancel_order(symbol, order_id)
                set_active_buy_order(None)
        
        # If we don't have an active order (either there never was one or we just cancelled it),
        # create a new buy order for the next candle
        if not get_active_buy_order() and get_position() == "NONE":
            rich_print(f"[STRATEGY] Creating buy order for next candle: {symbol} at price: {buy_price}, stop_limit: {buy_stop_limit}")
            buy_order = buy_long(symbol, price=buy_price, stop_limit=buy_stop_limit, quantity=QUANTITY)
            if buy_order:
                set_active_buy_order(buy_order)
                set_candle_order_created_at(row_data["timestamp"])
                rich_print(Pretty(buy_order))
    elif get_position() == "LONG" and allow_trading:
        # Handle stop loss orders
        active_sell_order = get_active_sell_order()
        if active_sell_order:
            order_id = active_sell_order.get("orderId")
            status, order_details = get_order_status(symbol, order_id)
            
            if status == "FILLED":
                rich_print(f"[STRATEGY] Sell order filled (stop loss hit): {order_id}")
                set_position("CLOSED_LONG")  # Change from NONE to CLOSED_LONG
                set_active_sell_order(None)
                set_active_buy_order(None)
                set_buy_filled_price(None)
                row_data["signal"] = "SELL"
                row_data["position"] = "CLOSED_LONG"  # Change from NONE to CLOSED_LONG
                row_data["entry"] = None  # Clear entry as the position is closed
                # Keep the stop_loss value to show the price at which the position was closed
            else:                # Cancel existing stop loss to update with new prices
                cancel_order(symbol, order_id)
                set_active_sell_order(None)
        
        # Create or update stop loss for the next candle
        if get_position() == "LONG" and not get_active_sell_order():
            # Use same value for both price and stop_limit (ha_low - SELL_OFFSET)
            sell_stop_limit = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
            rich_print(f"[STRATEGY] Creating/updating stop loss for next candle: {symbol} at price: {sell_stop_limit}, stop_limit: {sell_stop_limit}")
            # Use the same value for both price and stop_limit
            sell_order = sell_long(symbol, price=sell_stop_limit, stop_limit=sell_stop_limit, quantity=QUANTITY)
            if sell_order:
                set_active_sell_order(sell_order)
                # Update the stop_loss in row_data with the actual trigger price (stopPrice)
                actual_trigger_price = float(sell_order.get('stopPrice', sell_stop_limit))
                row_data["stop_loss"] = actual_trigger_price
                rich_print(f"[STRATEGY] Stop Loss order placed with trigger price: {actual_trigger_price}, order price: {sell_order.get('price')}")
                rich_print(Pretty(sell_order))
    
    return row_data
