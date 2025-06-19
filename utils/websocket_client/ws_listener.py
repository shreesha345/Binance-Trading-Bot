import websockets
import json

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

    try:
        async with websockets.connect(url) as ws:
            async for message in ws:
                data = json.loads(message)
                kline = data.get("k", {})
                await callback(kline)
    except KeyboardInterrupt:
        print("📡 WebSocket connection closed by user")
        raise
    except Exception as e:
        print(f"📡 WebSocket connection error: {e}")
        raise
