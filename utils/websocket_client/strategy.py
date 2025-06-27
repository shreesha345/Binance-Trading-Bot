import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from datetime import datetime
import time
import math  # Add math module import for floor function
from utils.buy_sell_handler import buy_long, sell_long, client, get_tick_size
from utils.order_utils import get_order_status, cancel_order
from utils.order_storage import save_filled_order, save_open_order, remove_open_order, enrich_order_details
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
from utils.logger import log_websocket, log_error

# Helper function to replace rich_print with log_websocket
def log_message(message):
    log_websocket(message)
    # We still show in console via the log_websocket implementation

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

def check_order_status_multiple_times(symbol, order_id, max_attempts=3, delay_seconds=10):
    """
    Check order status multiple times for partially filled orders
    
    Args:
        symbol: Trading pair symbol
        order_id: ID of the order to check
        max_attempts: Maximum number of attempts to check (default: 3)
        delay_seconds: Delay between attempts in seconds (default: 10)
        
    Returns:
        tuple: (final_status, order_details)
    """
    attempts = 0
    while attempts < max_attempts:
        status, order_details = get_order_status(symbol, order_id)
        log_message(f"[ORDER] Status for {symbol} order {order_id}: {status}")
        log_message(f"[ORDER CHECK] Attempt {attempts+1}/{max_attempts}: Order {order_id} status: {status}")
        
        # If order is fully filled or in a final state, return immediately
        if status in ["FILLED", "CANCELED", "REJECTED", "EXPIRED"]:
            return status, order_details
        
        # If partially filled, wait and try again
        if status == "PARTIALLY_FILLED":
            log_message(f"[ORDER CHECK] Order {order_id} partially filled. Waiting {delay_seconds}s before checking again...")
            time.sleep(delay_seconds)
            attempts += 1
        else:
            # For other statuses like NEW, just return
            return status, order_details
    
    # After max attempts, get the final status
    final_status, final_order_details = get_order_status(symbol, order_id)
    log_message(f"[ORDER CHECK] Final status for order {order_id} after {max_attempts} attempts: {final_status}")
    return final_status, final_order_details

def handle_filled_buy_order(row_data, symbol, order_details, filled_price):
    """
    Handle logic for a filled buy order
    
    Args:
        row_data: Current row data for display
        symbol: Trading pair symbol
        order_details: Details of the filled order
        filled_price: Price at which the order was filled
        
    Returns:
        Updated row_data
    """
    # Update bot state
    set_position("LONG")
    set_buy_filled_price(filled_price)
    
    # Update row data for display
    row_data["signal"] = "BUY"
    row_data["position"] = "LONG"
    row_data["entry"] = filled_price
    
    # Save the filled order details to order_book.json
    enriched_order = enrich_order_details(
        order_details,
        order_type='BUY',
        position_side='LONG',
        filled_price=filled_price,
        additional_info={
            'symbol': symbol,
            'ha_values': {
                'ha_open': row_data.get('ha_open'),
                'ha_high': row_data.get('ha_high'),
                'ha_low': row_data.get('ha_low'),
                'ha_close': row_data.get('ha_close')
            }
        }
    )
    save_filled_order(enriched_order)
    log_message(f"[STRATEGY] Buy order filled and saved to order_book.json: {order_details.get('orderId')}")
    
    # Remove from open orders if it exists there
    remove_open_order(order_details.get('orderId'))
    
    # Calculate stop loss price using floor to match exchange behavior
    # First calculate the raw price
    raw_stop_price = row_data["ha_low"] - SELL_OFFSET
    
    # Apply floor with tick size for exact matching with exchange
    tick_size = get_tick_size(symbol)
    stop_trigger_price = math.floor(raw_stop_price / tick_size) * tick_size
    stop_trigger_price = round(stop_trigger_price, 2)  # Ensure clean 2 decimal places
    
    # For display purposes, use the exact calculated value
    row_data["stop_loss"] = stop_trigger_price
    
    # Get the actual filled quantity from the order details
    filled_quantity = float(order_details.get('executedQty', QUANTITY))
    if filled_quantity <= 0:
        filled_quantity = QUANTITY  # Fallback to configured quantity
    
    log_message(f"[STRATEGY] Creating initial stop loss after buy fill with trigger at: {stop_trigger_price}")
    sell_order = sell_long(symbol, price=stop_trigger_price, stop_limit=stop_trigger_price, quantity=filled_quantity)
    if sell_order:
        set_active_sell_order(sell_order)
        log_message(f"[STRATEGY] Stop Loss order placed with trigger price: {stop_trigger_price}, order price: {sell_order.get('price')}")
        log_message(str(sell_order))
    
    return row_data

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
    buy_price_display = round(row_data["ha_high"] + BUY_OFFSET, 2)
    buy_price = buy_price_display  # Keep the original value for display
    
    # Use current candle HA high for stop limit
    buy_stop_limit = round(row_data["ha_high"], 2)
    
    # Calculate sell parameters with math.floor for exact tick size matching
    tick_size = get_tick_size(symbol)
    raw_stop_price = row_data["ha_low"] - SELL_OFFSET
    sell_stop_limit_display = math.floor(raw_stop_price / tick_size) * tick_size
    sell_stop_limit_display = round(sell_stop_limit_display, 2)  # Format to clean 2 decimal places
    sell_stop_limit = sell_stop_limit_display  # Keep the original value for order placement
    
    # Set display values
    if get_position() == "LONG":
        buy_filled_price = get_buy_filled_price() or buy_price_display
        row_data["entry"] = round(buy_filled_price, 2)
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
            
            # Check the order status multiple times if needed
            status, order_details = check_order_status_multiple_times(symbol, order_id)
            
            if status == "NEW":
                log_message(f"[STRATEGY] Cancelling unfilled buy order from previous candle: {order_id}")
                cancel_order(symbol, order_id)
                set_active_buy_order(None)
            elif status == "FILLED":
                log_message(f"[STRATEGY] Buy order filled: {order_id}")
                filled_price = round(float(order_details.get("price", 0)), 2)
                row_data = handle_filled_buy_order(row_data, symbol, order_details, filled_price)
            elif status == "PARTIALLY_FILLED":
                log_message(f"[STRATEGY] Buy order partially filled: {order_id}. Not creating new orders.")
                # Keep the order active and wait for it to be fully filled
            elif status in ["EXPIRED", "CANCELED", "REJECTED"]:
                log_message(f"[STRATEGY] Buy order {status}: {order_id}. Will create new order.")
                set_active_buy_order(None)
            elif status == "PENDING_CANCEL":
                log_message(f"[STRATEGY] Buy order is pending cancellation: {order_id}. Waiting for final status.")
    
    # Place new orders if allowed - always place order to be ready for next candle
    if get_position() == "NONE" and allow_trading:
        # Check if we already have an active buy order
        active_buy_order = get_active_buy_order()
        
        # If there's an existing order from a previous candle, check its status
        if active_buy_order:
            order_id = active_buy_order.get("orderId")
            status, order_details = check_order_status_multiple_times(symbol, order_id)
            
            if status == "FILLED":
                # Order was filled between candles
                log_message(f"[STRATEGY] Buy order filled: {order_id}")
                filled_price = round(float(order_details.get("price", 0)), 2)
                row_data = handle_filled_buy_order(row_data, symbol, order_details, filled_price)
            elif status == "PARTIALLY_FILLED":
                log_message(f"[STRATEGY] Buy order partially filled: {order_id}. Waiting for full fill.")
                # Keep the order active and wait for it to be fully filled
            else:
                # Cancel existing order to place a new one with updated prices
                log_message(f"[STRATEGY] Cancelling existing buy order (status: {status}) to update with new prices: {order_id}")
                cancel_order(symbol, order_id)
                set_active_buy_order(None)
          # If we don't have an active order (either there never was one or we just cancelled it),
    # create a new buy order for the next candle
    if not get_active_buy_order() and get_position() == "NONE":
        # Check current market price to avoid "would immediately trigger" error
        try:
            # Get recent market price
            ticker = client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Only place stop order if current price is below stop_limit
            if current_price < buy_stop_limit:
                log_message(f"[STRATEGY] Creating buy order for next candle: {symbol} at price: {buy_price} (HA_High + {BUY_OFFSET}), stop_limit: {buy_stop_limit} (HA_High)")
                buy_order = buy_long(symbol, price=buy_price, stop_limit=buy_stop_limit, quantity=QUANTITY)
                if buy_order:
                    set_active_buy_order(buy_order)
                    set_candle_order_created_at(row_data["timestamp"])
                    log_message(str(buy_order))
            else:
                log_message(f"[STRATEGY] Skipping buy order creation - current price ({current_price}) is already above stop limit ({buy_stop_limit})")
                log_message(f"[STRATEGY] Would have created: price={buy_price}, stop_limit={buy_stop_limit}")
        except Exception as e:
            log_error(f"Error checking market price before placing order: {e}", exc_info=True)
            # Fallback - try placing the order anyway
            log_message(f"[STRATEGY] Creating buy order for next candle (fallback): {symbol} at price: {buy_price}, stop_limit: {buy_stop_limit}")
            buy_order = buy_long(symbol, price=buy_price, stop_limit=buy_stop_limit, quantity=QUANTITY)
            if buy_order:
                set_active_buy_order(buy_order)
                set_candle_order_created_at(row_data["timestamp"])
                log_message(str(buy_order))
    elif get_position() == "LONG" and allow_trading:
        # Handle stop loss orders
        active_sell_order = get_active_sell_order()
        if active_sell_order:
            order_id = active_sell_order.get("orderId")
            status, order_details = check_order_status_multiple_times(symbol, order_id)
            
            if status == "FILLED":
                log_message(f"[STRATEGY] Sell order filled (stop loss hit): {order_id}")
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
                    row_data["stop_loss"] = round(executed_price, 2)
                    log_message(f"[STRATEGY] Position closed at price: {row_data['stop_loss']}")
                
                # Save the filled sell order details to order_book.json
                enriched_order = enrich_order_details(
                    order_details,
                    order_type='SELL',
                    position_side='LONG',
                    filled_price=executed_price,
                    additional_info={
                        'symbol': symbol,
                        'executed_price': executed_price,
                        'is_stop_loss': True,
                        'ha_values': {
                            'ha_open': row_data.get('ha_open'),
                            'ha_high': row_data.get('ha_high'),
                            'ha_low': row_data.get('ha_low'),
                            'ha_close': row_data.get('ha_close')
                        }
                    }
                )
                save_filled_order(enriched_order)
                log_message(f"[STRATEGY] Sell order filled and saved to order_book.json: {order_id}")
                
                # Remove from open orders if it exists there
                remove_open_order(order_id)
            elif status == "PARTIALLY_FILLED":
                log_message(f"[STRATEGY] Sell order partially filled: {order_id}. Waiting for full fill.")
                # Keep the order active and wait for it to be fully filled
            elif status == "EXPIRED":
                # For expired sell orders, this could mean the position was already closed
                # by another order or manually, so we should check the position status
                log_message(f"[STRATEGY] Sell order expired: {order_id}. Checking position status.")
                
                # Clear the sell order regardless
                set_active_sell_order(None)
                
                # We don't create a new stop loss immediately because we need to determine
                # if the position is still open
                position_check = client.futures_position_information(symbol=symbol)
                position_found = False
                for pos in position_check:
                    if pos['symbol'] == symbol and pos['positionSide'] == 'LONG' and float(pos['positionAmt']) > 0:
                        position_found = True
                        break
                
                if not position_found:
                    # Position is closed, update the state
                    log_message(f"[STRATEGY] Position appears to be closed. Updating state.")
                    set_position("CLOSED_LONG")
                    set_active_buy_order(None)
                    set_buy_filled_price(None)
                    row_data["signal"] = "SELL"
                    row_data["position"] = "CLOSED_LONG"
                    row_data["entry"] = None
                    # We don't have the exact closing price, so keep the existing stop_loss
            else:
                # For all other statuses, cancel the existing order to create a new one with updated prices
                log_message(f"[STRATEGY] Cancelling existing sell order (status: {status}) to update with new stop loss price")
                cancel_order(symbol, order_id)
                set_active_sell_order(None)
                # We'll check again next candle
        # Create or update stop loss for the next candle
        if get_position() == "LONG":
            # Always update the stop loss with each new candle
            
            # Check if the position really exists (in case we missed a fill or the position was closed manually)
            position_check = client.futures_position_information(symbol=symbol)
            position_found = False
            position_amt = 0
            for pos in position_check:
                if pos['symbol'] == symbol and pos['positionSide'] == 'LONG' and float(pos['positionAmt']) > 0:
                    position_found = True
                    position_amt = float(pos['positionAmt'])
                    break
            
            # Only create a new stop loss if the position actually exists
            if position_found:
                # Calculate the new stop loss price based on current candle with tick size adjustment
                raw_stop_price = row_data["ha_low"] - SELL_OFFSET
                tick_size = get_tick_size(symbol)
                sell_stop_limit = math.floor(raw_stop_price / tick_size) * tick_size
                sell_stop_limit = round(sell_stop_limit, 2)  # Format to clean 2 decimal places
                
                # Set display value to exact calculated value
                row_data["stop_loss"] = sell_stop_limit
                
                # First, cancel any existing stop loss order
                if get_active_sell_order():
                    order_id = get_active_sell_order().get("orderId")
                    log_message(f"[STRATEGY] Cancelling existing stop loss order to update with new price: {order_id}")
                    cancel_result = cancel_order(symbol, order_id)
                    
                    if cancel_result:
                        log_message(f"[STRATEGY] Successfully cancelled stop loss order: {order_id}")
                        set_active_sell_order(None)
                    else:
                        # Check if the order still exists
                        status, order_details = get_order_status(symbol, order_id)
                        if status is None or status in ['CANCELED', 'REJECTED', 'EXPIRED', 'FILLED']:
                            log_message(f"[STRATEGY] Order {order_id} is already {status}, can proceed with new order")
                            set_active_sell_order(None)
                        else:
                            log_message(f"[STRATEGY] Failed to cancel stop loss order {order_id} (status: {status}), will not create new order to avoid duplicates")
                            # Skip creating a new order if we couldn't cancel the existing one
                            # and it's still active
                            return row_data
                
                # Create new stop loss order with updated price
                log_message(f"[STRATEGY] Creating/updating stop loss for next candle: {symbol} at price: {sell_stop_limit}, stop_limit: {sell_stop_limit}")
                # Use the same value for both price and stop_limit
                sell_order = sell_long(symbol, price=sell_stop_limit, stop_limit=sell_stop_limit, quantity=position_amt)
                if sell_order:
                    set_active_sell_order(sell_order)
                    # Keep using the exact calculated value for display
                    log_message(f"[STRATEGY] Stop Loss order placed with trigger price: {sell_stop_limit}, order price: {sell_order.get('price')}")
                    log_message(str(sell_order))
                else:
                    log_message(f"[STRATEGY] Failed to create stop loss order. Will try again with next candle.")
            else:
                # Position not found, update the state
                log_message(f"[STRATEGY] Position not found in exchange. Updating state to CLOSED_LONG.")
                set_position("CLOSED_LONG")
                set_active_buy_order(None)
                set_buy_filled_price(None)
                row_data["signal"] = "SELL"
                row_data["position"] = "CLOSED_LONG"
                row_data["entry"] = None
                # We don't have the exact closing price, so keep the existing stop_loss
    
    return row_data
