import asyncio
import websockets
import json
from config import MODE

FUTURES_MAINNET_WS_URL = "wss://fstream.binance.com/ws"
FUTURES_TESTNET_WS_URL = "wss://stream.binancefuture.com/ws"

async def ohlc_listener_futures_ws(symbol: str, interval: str, callback, testnet: bool = False):
    """
    Connects to Binance Futures WebSocket (mainnet or testnet, based on testnet argument) and listens for OHLC (kline) data.
    """
    ws_url = FUTURES_TESTNET_WS_URL if testnet else FUTURES_MAINNET_WS_URL
    stream = f"{symbol.lower()}@kline_{interval}"
    url = f"{ws_url}/{stream}"

    print(f"Connected to {'futures testnet' if testnet else 'futures mainnet'}: {url}")

    async with websockets.connect(url) as ws:
        async for message in ws:
            data = json.loads(message)
            kline = data.get("k", {})
            await callback(kline)

# Example callback function
async def print_ohlc(kline):
    print(f"Open: {kline['o']}, High: {kline['h']}, Low: {kline['l']}, Close: {kline['c']}")

# Example usage
if __name__ == "__main__":
    symbol = "btcusdt"
    interval = "1m"
    # Set testnet to True or False as needed
    testnet = MODE  # Change to False for mainnet
    asyncio.run(ohlc_listener_futures_ws(symbol, interval, print_ohlc, testnet=testnet))