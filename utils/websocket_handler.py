import asyncio
import websockets
import json
from config import MODE
from datetime import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from basic_strategy import generate_signal, calculate_entry_sl

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

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_ohlcv_table_with_signals(data):
    """
    Prints OHLCV data with trading signals in table format.
    """
    print("=" * 100)
    print(f"{'Time':<8} {'Symbol':<10} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Signal':<6} {'Entry':<10} {'SL':<10}")
    print("=" * 100)
    
    for row in data:
        signal = row.get('signal', 'HOLD')
        entry = row.get('entry', '-')
        stop_loss = row.get('stop_loss', '-')
        
        # Format entry and stop loss for display
        entry_str = f"{entry:.2f}" if entry else "-"
        sl_str = f"{stop_loss:.2f}" if stop_loss else "-"
        
        print(f"{row['time']:<8} {row['symbol']:<10} {row['open']:<10.2f} {row['high']:<10.2f} {row['low']:<10.2f} {row['close']:<10.2f} {signal:<6} {entry_str:<10} {sl_str:<10}")

async def ohlc_strategy_collector(symbol: str, interval: str, testnet: bool = False):
    """
    Collects OHLC data from Binance websocket, applies strategy, and displays with signals.
    """
    ohlc_data = []
    current_candle = None

    def format_row_with_strategy(kline):
        row_data = {
            "symbol": symbol.upper(),
            "time": datetime.fromtimestamp(int(kline['t'])/1000).strftime('%H:%M'),
            "open": float(kline['o']),
            "high": float(kline['h']),
            "low": float(kline['l']),
            "close": float(kline['c']),
        }
        
        # Apply strategy
        signal = generate_signal(row_data)
        levels = calculate_entry_sl(row_data, signal)
        
        row_data.update({
            'signal': signal,
            'entry': levels['entry'],
            'stop_loss': levels['stop_loss']
        })
        
        return row_data

    async def on_kline(kline):
        nonlocal current_candle
        
        formatted_candle = format_row_with_strategy(kline)
        
        if kline.get('x'):  # Candle is closed
            # Add the closed candle to history
            ohlc_data.append(formatted_candle)
            current_candle = None
        else:
            # Update current candle
            current_candle = formatted_candle
        
        # Always show updated table
        clear_screen()
        display_data = ohlc_data[-9:] + ([current_candle] if current_candle else [])
        print_ohlcv_table_with_signals(display_data)
        if current_candle:
            print(f"\n(Current candle updating... Signal: {current_candle['signal']})")

    await ohlc_listener_futures_ws(symbol, interval, on_kline, testnet=testnet)

# Example usage
if __name__ == "__main__":
    symbol = "btcusdt"
    interval = "5m"
    testnet = MODE  # Change to False for mainnet
    asyncio.run(ohlc_strategy_collector(symbol, interval, testnet=testnet))

