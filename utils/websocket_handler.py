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

def main():
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
    
    print(f"🚀 Starting {interval} interval data collection for {symbol.upper()}")
    print(f"📈 Will fetch 5 historical Heikin Ashi candles for proper calculation")
    print(f"⏰ For {interval} interval, expect data every {interval}")
    print(f"💡 Press Ctrl+C to stop the bot")
    if debug_mode:
        print(f"🐛 DEBUG MODE ENABLED: Screen will not be cleared and errors will be shown in detail")
    print("=" * 60)
    
    while retry_count < max_retries:
        try:
            asyncio.run(ohlc_strategy_collector(symbol, interval, testnet=testnet, debug_mode=debug_mode))
            # If the WebSocket closes cleanly, we still want to reconnect
            retry_count += 1
            retry_delay = retry_delay_initial * (2 ** min(retry_count, 3))  # Exponential backoff up to 8x
            print(f"\n🔄 WebSocket connection closed. Reconnecting in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(retry_delay)
            
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user (Ctrl+C)")
            print("👋 Goodbye!")
            break
            
        except websockets.exceptions.ConnectionClosedError as e:
            retry_count += 1
            retry_delay = retry_delay_initial * (2 ** min(retry_count, 3))  # Exponential backoff up to 8x
            print(f"\n📡 WebSocket connection error: {e}")
            print(f"🔄 Reconnecting in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(retry_delay)
            
        except Exception as e:
            retry_count += 1
            retry_delay = retry_delay_initial * (2 ** min(retry_count, 3))  # Exponential backoff up to 8x
            print(f"\n❌ An error occurred: {e}")
            
            if SHOW_ERRORS or debug_mode:
                print("\nDetailed error information:")
                traceback.print_exc()
            
            if retry_count < max_retries:
                print(f"\n🔄 Restarting bot in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"\n❌ Maximum retry attempts ({max_retries}) reached. Exiting.")
                print("👋 Bot stopped due to repeated errors")
                break
    
    if retry_count >= max_retries:
        print(f"\n❌ Maximum retry attempts ({max_retries}) reached. Exiting.")
        print("👋 Bot stopped due to too many reconnection attempts")

if __name__ == "__main__":
    main()

