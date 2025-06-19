import asyncio
from config import MODE
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# custom imports
from websocket_client.ohlc_collector import ohlc_strategy_collector

def main():
    symbol = "btcusdt"
    interval = "1m"
    testnet = MODE
    print(f"🚀 Starting {interval} interval data collection for {symbol.upper()}")
    print(f"📈 Will fetch 5 historical Heikin Ashi candles for proper calculation")
    print(f"⏰ For {interval} interval, expect data every {interval}")
    print(f"💡 Press Ctrl+C to stop the bot")
    print("=" * 60)
    try:
        asyncio.run(ohlc_strategy_collector(symbol, interval, testnet=testnet))
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user (Ctrl+C)")
        print("👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("👋 Bot stopped due to error")

if __name__ == "__main__":
    main()

