import asyncio
import sys
import os
import traceback
import time
import websockets
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# custom imports
from utils.config import MODE, DEBUG_MODE, SHOW_ERRORS, TRADING_SYMBOL, CANDLE_INTERVAL
from utils.websocket_client.ohlc_collector import ohlc_strategy_collector
from utils.logger import log_websocket, log_error

def websocket_runner():
    # Process command line arguments
    debug_arg = "--debug" in sys.argv or "-d" in sys.argv
    debug_mode = DEBUG_MODE or debug_arg
    
    symbol = TRADING_SYMBOL
    interval = CANDLE_INTERVAL
    testnet = MODE
    
    # Retry settings
    max_retries = 10  # Increased for more robustness
    retry_delay_initial = 5  # seconds
    retry_count = 0
    
    log_websocket(f"🚀 Starting {interval} interval data collection for {symbol.upper()}")
    log_websocket(f"📈 Will fetch 5 historical Heikin Ashi candles for proper calculation")
    log_websocket(f"⏰ For {interval} interval, expect data every {interval}")
    log_websocket(f"💡 Press Ctrl+C to stop the bot")
    if debug_mode:
        log_websocket(f"🐛 DEBUG MODE ENABLED: Screen will not be cleared and errors will be shown in detail")
    log_websocket("=" * 60)
    
    while retry_count < max_retries:
        try:
            asyncio.run(ohlc_strategy_collector(symbol, interval, testnet=testnet, debug_mode=debug_mode))
            # If the WebSocket closes cleanly, we still want to reconnect
            retry_count += 1
            retry_delay = retry_delay_initial * (2 ** min(retry_count, 3))  # Exponential backoff up to 8x
            log_websocket(f"\n🔄 WebSocket connection closed. Reconnecting in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(retry_delay)
            
        except KeyboardInterrupt:
            log_websocket("\n🛑 Bot stopped by user (Ctrl+C)")
            log_websocket("👋 Goodbye!")
            break
            
        except websockets.exceptions.ConnectionClosedError as e:
            retry_count += 1
            retry_delay = retry_delay_initial * (2 ** min(retry_count, 3))  # Exponential backoff up to 8x
            log_websocket(f"\n📡 WebSocket connection error: {e}")
            log_websocket(f"🔄 Reconnecting in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
            log_error(f"WebSocket connection error: {e}", exc_info=True)
            time.sleep(retry_delay)
            
        except Exception as e:
            retry_count += 1
            retry_delay = retry_delay_initial * (2 ** min(retry_count, 3))  # Exponential backoff up to 8x
            log_websocket(f"\n❌ An error occurred: {e}")
            log_error(f"Error in websocket handler: {e}", exc_info=True)
            
            if SHOW_ERRORS or debug_mode:
                log_websocket("\nDetailed error information:")
                error_traceback = traceback.format_exc()
                log_websocket(error_traceback)
            
            if retry_count < max_retries:
                log_websocket(f"\n🔄 Restarting bot in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(retry_delay)
            else:
                log_websocket(f"\n❌ Maximum retry attempts ({max_retries}) reached. Exiting.")
                log_websocket("👋 Bot stopped due to repeated errors")
                break
    
    if retry_count >= max_retries:
        log_websocket(f"\n❌ Maximum retry attempts ({max_retries}) reached. Exiting.")
        log_websocket("👋 Bot stopped due to too many reconnection attempts")

if __name__ == "__main__":
    websocket_runner()

