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
    }    # Reset position from CLOSED_LONG to NONE after one candle
    # But store the closing price temporarily
    closing_price = None
    if row_data["position"] == "CLOSED_LONG":
        # Save the stop_loss value (which contains the selling price) before clearing
        closing_price = row_data["stop_loss"]
        
        # For the next candle after CLOSED_LONG, reset to NONE
        # This ensures "CLOSED_LONG" only shows for the candle where the SELL happens
        row_data["position"] = "NONE"
        row_data["stop_loss"] = closing_price  # Keep the closing price in stop_loss column
        set_position("NONE")
    
    # Calculate Heikin Ashi values
    from utils.websocket_client.heikin_ashi import calculate_heikin_ashi
    ha_values = calculate_heikin_ashi(row_data, previous_ha_candle)
    row_data.update(ha_values)
      # Current candle values
    current_candle_high = row_data["high"]
    current_candle_low = row_data["low"]
    current_close = float(kline["c"])
    
    # Calculate buy parameters
    # Price = HA_High + BUY_OFFSET
    # Stop limit = Current HA_High (not previous candle)
    buy_price_display = int((row_data["ha_high"] + BUY_OFFSET) * 100) / 100
    buy_price = buy_price_display  # Keep the original value for display
    
    # Use current candle HA high for stop limit
    buy_stop_limit = int(row_data["ha_high"] * 100) / 100
    
    # Calculate sell parameters - set both price and stop_limit to HA_Low minus offset
    sell_stop_limit_display = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
    sell_stop_limit = sell_stop_limit_display  # Keep the original value for display# Set display values
    if get_position() == "LONG":
        buy_filled_price = get_buy_filled_price() or buy_price_display
        row_data["entry"] = int(buy_filled_price * 100) / 100
        # For stop loss when in LONG position, use the current candle's HA_Low minus SELL_OFFSET
        row_data["stop_loss"] = sell_stop_limit_display
    elif get_position() == "NONE":
        # If we already have a stop_loss value set (from a recent CLOSED_LONG position),
        # don't override it with the calculated entry value
        if row_data["stop_loss"] is None:
            row_data["entry"] = buy_price_display
            row_data["stop_loss"] = sell_stop_limit_display
    
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
                row_data["entry"] = filled_price                # Create immediate stop loss
                current_price = float(kline["c"])                
                # Use current candle HA_Low for the stop loss trigger price
                stop_trigger_price = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
                
                # For display purposes, use the exact calculated value
                row_data["stop_loss"] = stop_trigger_price
                
                rich_print(f"[STRATEGY] Creating initial stop loss after fill with trigger at: {stop_trigger_price}")
                sell_order = sell_long(symbol, price=stop_trigger_price, stop_limit=stop_trigger_price, quantity=QUANTITY)
                if sell_order:
                    set_active_sell_order(sell_order)
                    # For exchange purposes, we need to get the actual value from the order
                    # But we'll continue to show the exact calculated value for display
                    rich_print(f"[STRATEGY] Stop Loss order placed with trigger price: {stop_trigger_price}, order price: {sell_order.get('price')}")
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
                
                # For display purposes, use the exact calculated value
                row_data["stop_loss"] = stop_loss_price
                
                rich_print(f"[STRATEGY] Creating initial stop loss after fill at: {stop_loss_price}")
                # Using the same price and stop_limit to ensure they're identical
                sell_order = sell_long(symbol, price=stop_loss_price, stop_limit=stop_loss_price, quantity=QUANTITY)
                if sell_order:
                    set_active_sell_order(sell_order)
                    # For exchange purposes, we need to use the adjusted value, but for display we keep the exact calculated value
                    rich_print(f"[STRATEGY] Stop Loss order placed at trigger price: {stop_loss_price}")
                    rich_print(Pretty(sell_order))
            else:                # Cancel existing order to place a new one with updated prices
                rich_print(f"[STRATEGY] Cancelling existing buy order to update with new prices: {order_id}")
                cancel_order(symbol, order_id)
                set_active_buy_order(None)
          # If we don't have an active order (either there never was one or we just cancelled it),
        # create a new buy order for the next candle
        if not get_active_buy_order() and get_position() == "NONE":
            rich_print(f"[STRATEGY] Creating buy order for next candle: {symbol} at price: {buy_price} (HA_High + {BUY_OFFSET}), stop_limit: {buy_stop_limit} (HA_High)")
            buy_order = buy_long(symbol, price=buy_price, stop_limit=buy_stop_limit, quantity=QUANTITY)
            if buy_order:
                set_active_buy_order(buy_order)
                set_candle_order_created_at(row_data["timestamp"])
                rich_print(Pretty(buy_order))
    elif get_position() == "LONG" and allow_trading:        # Handle stop loss orders
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
                
                # Get the actual executed price from the order details
                executed_price = float(order_details.get('price', 0))
                if executed_price == 0:  # If price is not available, try avgPrice
                    executed_price = float(order_details.get('avgPrice', 0))
                
                # If we still don't have a price, use the stopPrice as fallback
                if executed_price == 0:
                    executed_price = float(order_details.get('stopPrice', 0))
                
                # Set the stop_loss value to the actual sell price to show where position was closed
                if executed_price > 0:
                    row_data["stop_loss"] = int(executed_price * 100) / 100
                    rich_print(f"[STRATEGY] Position closed at price: {row_data['stop_loss']}")
            else:
                # Cancel existing stop loss to update with new prices
                cancel_order(symbol, order_id)
                set_active_sell_order(None)
          # Create or update stop loss for the next candle
        if get_position() == "LONG" and not get_active_sell_order():
            # Use same value for both price and stop_limit (ha_low - SELL_OFFSET)
            sell_stop_limit = int((row_data["ha_low"] - SELL_OFFSET) * 100) / 100
            
            # Set display value to exact calculated value
            row_data["stop_loss"] = sell_stop_limit
            
            rich_print(f"[STRATEGY] Creating/updating stop loss for next candle: {symbol} at price: {sell_stop_limit}, stop_limit: {sell_stop_limit}")
            # Use the same value for both price and stop_limit
            sell_order = sell_long(symbol, price=sell_stop_limit, stop_limit=sell_stop_limit, quantity=QUANTITY)
            if sell_order:
                set_active_sell_order(sell_order)
                # Keep using the exact calculated value for display
                rich_print(f"[STRATEGY] Stop Loss order placed with trigger price: {sell_stop_limit}, order price: {sell_order.get('price')}")
                rich_print(Pretty(sell_order))
    
    return row_data
