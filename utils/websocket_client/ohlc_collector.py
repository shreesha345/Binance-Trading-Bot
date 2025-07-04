import asyncio
from datetime import datetime
import sys
import os
import traceback
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.websocket_client.ws_listener import ohlc_listener_futures_ws
from utils.websocket_client.ha_utils import get_historical_ha_data, align_time_to_interval
from utils.websocket_client.clear_screen import clear_screen
from utils.websocket_client.display import print_ohlcv_table_with_signals
from utils.websocket_client.heikin_ashi import calculate_heikin_ashi
from utils.websocket_client.strategy import format_row_with_strategy, add_strategy_to_historical_data
from utils.config import FIXED_QUANTITY, QUANTITY_TYPE, QUANTITY_PERCENTAGE, DEBUG_MODE, SHOW_ERRORS
from utils.quantity_calculator import calculate_quantity
from utils.bot_state import reset_state
from utils.logger import log_websocket, log_error

try:
    from binance.client import Client
except ImportError:
    Client = None

async def ohlc_strategy_collector(symbol: str, interval: str, testnet: bool = False, debug_mode: bool = False):
    # Sync system time with Binance server time if possible
    if Client is not None:
        try:
            # You may want to use your actual API keys here if needed
            client = Client()
            server_time = client.futures_time()['serverTime']
            local_time = int(time.time() * 1000)
            time_diff = server_time - local_time
            if abs(time_diff) > 1000:
                log_websocket(f"⚠️ Local time is off by {time_diff} ms from Binance server time. Please sync your system clock.")
            else:
                log_websocket(f"⏰ Local time is synchronized with Binance server (diff: {time_diff} ms)")
        except Exception as e:
            log_websocket(f"⚠️ Could not fetch Binance server time: {e}")
            
    display_data = []
    show_heikin_ashi = True
    last_candle_time = None
    try:
        # Get historical data and initialize previous_ha_candle
        historical_raw_data, raw_previous_ha_candle = await get_historical_ha_data(symbol, interval, 5)
        
        if historical_raw_data:
            # Reset bot state before processing
            reset_state()
              # Process historical data with our new strategy
            historical_ha_data = add_strategy_to_historical_data(historical_raw_data)
            
            # Add the latest historical candle to display data
            latest_historical = historical_ha_data[-1]
            display_data.append(latest_historical)
            
            # Store the latest historical timestamp to avoid placing orders on historical data
            latest_historical_timestamp = latest_historical['timestamp']
            
            # Show initial data - only clear screen if not in debug mode
            if not debug_mode and not DEBUG_MODE:
                clear_screen()
            table_output = print_ohlcv_table_with_signals([latest_historical], show_heikin_ashi, return_output=True)
            log_websocket(table_output)
            
            # Use the last historical candle for HA calculations
            previous_ha_candle = {
                'ha_open': latest_historical['ha_open'],
                'ha_high': latest_historical['ha_high'],
                'ha_low': latest_historical['ha_low'],
                'ha_close': latest_historical['ha_close']            }
        else:
            previous_ha_candle = None
            
        async def on_kline(kline):
            nonlocal previous_ha_candle, last_candle_time, latest_historical_timestamp
            
            # Skip if candle is not closed yet
            if not kline.get('x'):
                return
                  # Process timestamp and align to interval
            candle_time = int(kline['t'])
            candle_datetime = datetime.fromtimestamp(candle_time / 1000)
            aligned_candle_time = align_time_to_interval(candle_datetime, interval)
            
            # Skip if candle time doesn't align exactly with the interval start time
            if candle_datetime != aligned_candle_time:
                return
                
            # Skip duplicate candles
            if last_candle_time == candle_time:
                return
                
            # Skip if candle is older than our latest historical candle
            if historical_raw_data and candle_time <= historical_raw_data[-1]['timestamp']:
                return
                
            last_candle_time = candle_time            # Format the candle data with our new strategy implementation
            # Always allow trading for real-time candles, historical check is handled in strategy
            formatted_candle = format_row_with_strategy(kline, symbol, previous_ha_candle, True)
            formatted_candle['historical'] = False
            
            # Add to display data
            display_data.append(formatted_candle)
              # Update previous_ha_candle for next iteration
            previous_ha_candle = {
                'ha_open': formatted_candle['ha_open'],
                'ha_high': formatted_candle['ha_high'],
                'ha_low': formatted_candle['ha_low'],
                'ha_close': formatted_candle['ha_close']
            }
              # Update display - only clear screen if not in debug mode
            if not DEBUG_MODE:
                clear_screen()
            table_output = print_ohlcv_table_with_signals(display_data, show_heikin_ashi, return_output=True)
            log_websocket(table_output)
            
        # Start websocket listener with retry mechanism
        await ohlc_listener_futures_ws(symbol, interval, on_kline, testnet=testnet)
        
    except KeyboardInterrupt:
        log_websocket("\n🔄 Shutting down gracefully...")
        raise
    except Exception as e:
        error_msg = f"\n❌ Error in strategy collector: {e}"
        log_websocket(error_msg)
        log_error(f"Error in strategy collector: {e}", exc_info=True)
        
        if SHOW_ERRORS:
            error_details = "\nDetailed error information:\n" + traceback.format_exc()
            log_websocket(error_details)
        
        log_websocket("\n🔄 The connection will be retried automatically...")
        raise
