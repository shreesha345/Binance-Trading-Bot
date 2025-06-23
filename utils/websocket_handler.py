import asyncio
import sys
import os
import traceback
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
    print(f"🚀 Starting {interval} interval data collection for {symbol.upper()}")
    print(f"📈 Will fetch 5 historical Heikin Ashi candles for proper calculation")
    print(f"⏰ For {interval} interval, expect data every {interval}")
    print(f"💡 Press Ctrl+C to stop the bot")
    if debug_mode:
        print(f"🐛 DEBUG MODE ENABLED: Screen will not be cleared and errors will be shown in detail")
    print("=" * 60)
    try:
        asyncio.run(ohlc_strategy_collector(symbol, interval, testnet=testnet, debug_mode=debug_mode))
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user (Ctrl+C)")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        if SHOW_ERRORS or debug_mode:
            print("\nDetailed error information:")
            traceback.print_exc()
        print("👋 Bot stopped due to error")

if __name__ == "__main__":
    main()

