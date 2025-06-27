import websockets
import json
import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.logger import log_websocket, log_error

FUTURES_MAINNET_WS_URL = "wss://fstream.binance.com/ws"
FUTURES_TESTNET_WS_URL = "wss://stream.binancefuture.com/ws"

async def ohlc_listener_futures_ws(symbol: str, interval: str, callback, testnet: bool = False, max_retries: int = 10, retry_delay: int = 5):
    """
    Connects to Binance Futures WebSocket (mainnet or testnet, based on testnet argument) and listens for OHLC (kline) data.
    Includes automatic retry mechanism for connection issues.
    
    Args:
        symbol (str): Trading symbol (e.g., "BTCUSDT")
        interval (str): Candle interval (e.g., "1m", "5m", "1h")
        callback (function): Async function to call when new kline data is received
        testnet (bool): Whether to use testnet (True) or mainnet (False)
        max_retries (int): Maximum number of reconnection attempts
        retry_delay (int): Delay in seconds between retry attempts
    """
    ws_url = FUTURES_TESTNET_WS_URL if testnet else FUTURES_MAINNET_WS_URL
    stream = f"{symbol.lower()}@kline_{interval}"
    url = f"{ws_url}/{stream}"
    
    retry_count = 0
    backoff_factor = 1.5  # Exponential backoff factor
    
    while retry_count < max_retries:
        try:
            if retry_count > 0:
                log_websocket(f"📡 Attempting to reconnect... (Attempt {retry_count}/{max_retries})")
            else:
                log_websocket(f"🔌 Starting WebSocket connection for {symbol.upper()}...")
                log_websocket(f"📡 Connected to {'futures testnet' if testnet else 'futures mainnet'}: {url}")
                
            async with websockets.connect(url) as ws:
                # Reset retry count on successful connection
                retry_count = 0
                
                async for message in ws:
                    data = json.loads(message)
                    kline = data.get("k", {})
                    await callback(kline)
                    
        except KeyboardInterrupt:
            log_websocket("📡 WebSocket connection closed by user")
            raise
            
        except websockets.exceptions.ConnectionClosedError as e:
            retry_count += 1
            current_delay = retry_delay * (backoff_factor ** (retry_count - 1))
            
            log_websocket(f"📡 WebSocket connection closed: {e}")
            log_error(f"WebSocket connection closed: {e}", exc_info=True)
            
            if retry_count < max_retries:
                log_websocket(f"📡 Reconnecting in {current_delay:.1f} seconds...")
                await asyncio.sleep(current_delay)
            else:
                log_websocket(f"📡 Maximum retries ({max_retries}) reached. Giving up.")
                raise
                
        except Exception as e:
            log_websocket(f"📡 WebSocket connection error: {e}")
            log_error(f"WebSocket connection error: {e}", exc_info=True)
            
            retry_count += 1
            current_delay = retry_delay * (backoff_factor ** (retry_count - 1))
            
            if retry_count < max_retries:
                log_websocket(f"📡 Reconnecting in {current_delay:.1f} seconds...")
                await asyncio.sleep(current_delay)
            else:
                log_websocket(f"📡 Maximum retries ({max_retries}) reached. Giving up.")
                raise
