import asyncio
import websockets
import json
from config import MODE
from datetime import datetime, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from basic_strategy import generate_signal, calculate_entry_sl
from historical_handler import get_heikin_ashi_by_datetime

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

# Example callback function
async def print_ohlc(kline):
    print(f"Open: {kline['o']}, High: {kline['h']}, Low: {kline['l']}, Close: {kline['c']}")

def calculate_heikin_ashi(current, previous=None):
    """
    Calculate Heikin-Ashi values for a single candle
    
    Args:
        current: Dictionary with current candle OHLC values
        previous: Dictionary with previous Heikin-Ashi values or None
        
    Returns:
        Dictionary with Heikin-Ashi OHLC values
    """
    if previous is None:
        # First candle - use regular candle values with modified close
        ha_open = current['open']
        ha_close = (current['open'] + current['high'] + current['low'] + current['close']) / 4
    else:
        # Calculate based on previous HA candle
        ha_open = (previous['ha_open'] + previous['ha_close']) / 2
        ha_close = (current['open'] + current['high'] + current['low'] + current['close']) / 4
    
    ha_high = max(current['high'], ha_open, ha_close)
    ha_low = min(current['low'], ha_open, ha_close)
    
    return {
        'ha_open': ha_open,
        'ha_high': ha_high,
        'ha_low': ha_low,
        'ha_close': ha_close
    }

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_ohlcv_table_with_signals(data, show_heikin_ashi=True):
    """
    Prints OHLCV data with trading signals in table format.
    Option to show Heikin-Ashi values instead of regular OHLC.
    """
    print("=" * 120)
    header = f"{'Time':<8} {'Symbol':<10}"
    
    if show_heikin_ashi:
        header += f" {'HA_Open':<10} {'HA_High':<10} {'HA_Low':<10} {'HA_Close':<10}"
    else:
        header += f" {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}"
        
    header += f" {'Signal':<6} {'Entry':<10} {'SL':<10}"
    print(header)
    print("=" * 120)
    
    for row in data:
        signal = row.get('signal', 'HOLD')
        entry = row.get('entry', '-')
        stop_loss = row.get('stop_loss', '-')
        
        # Format entry and stop loss for display
        entry_str = f"{entry:.2f}" if isinstance(entry, (int, float)) else "-"
        sl_str = f"{stop_loss:.2f}" if isinstance(stop_loss, (int, float)) else "-"
        
        line = f"{row['time']:<8} {row['symbol']:<10}"
        
        if show_heikin_ashi:
            line += f" {row.get('ha_open', '-'):<10.2f} {row.get('ha_high', '-'):<10.2f}"
            line += f" {row.get('ha_low', '-'):<10.2f} {row.get('ha_close', '-'):<10.2f}"
        else:
            line += f" {row['open']:<10.2f} {row['high']:<10.2f}"
            line += f" {row['low']:<10.2f} {row['close']:<10.2f}"
            
        line += f" {signal:<6} {entry_str:<10} {sl_str:<10}"
        print(line)

def align_time_to_interval(dt, interval):
    """
    Align datetime to the proper interval boundary
    """
    if interval == '1s':
        return dt.replace(microsecond=0)
    elif interval == '1m':
        return dt.replace(second=0, microsecond=0)
    elif interval == '3m':
        # Round down to nearest 3-minute mark
        minutes = (dt.minute // 3) * 3
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '5m':
        # Round down to nearest 5-minute mark
        minutes = (dt.minute // 5) * 5
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '15m':
        # Round down to nearest 15-minute mark
        minutes = (dt.minute // 15) * 15
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '30m':
        # Round down to nearest 30-minute mark
        minutes = (dt.minute // 30) * 30
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '1h':
        return dt.replace(minute=0, second=0, microsecond=0)
    elif interval == '2h':
        # Round down to nearest 2-hour mark
        hours = (dt.hour // 2) * 2
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '6h':
        # Round down to nearest 6-hour mark (00, 06, 12, 18)
        hours = (dt.hour // 6) * 6
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '8h':
        # Round down to nearest 8-hour mark (00, 08, 16)
        hours = (dt.hour // 8) * 8
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '12h':
        # Round down to nearest 12-hour mark (00, 12)
        hours = (dt.hour // 12) * 12
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '1d':
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == '3d':
        # Round down to nearest 3-day mark
        days_since_epoch = (dt - datetime(1970, 1, 1)).days
        aligned_days = (days_since_epoch // 3) * 3
        aligned_date = datetime(1970, 1, 1) + timedelta(days=aligned_days)
        return aligned_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == '1w':
        # Round down to nearest Monday
        days_since_monday = dt.weekday()
        monday = dt - timedelta(days=days_since_monday)
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == '1M':
        # Round down to first day of month
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return dt

async def get_historical_ha_data(symbol: str, interval: str, count: int = 5):
    """
    Get historical Heikin Ashi data using the historical_handler
    """
    try:
        historical_ha_data = []
        current_time = datetime.now()
        
        # Align current time to the interval boundary
        aligned_time = align_time_to_interval(current_time, interval)
        
        print(f"📚 Fetching last {count} historical {interval} Heikin Ashi candles...")
        
        # Get historical candles going back in time from aligned boundary
        for i in range(count, 0, -1):  # count, count-1, ..., 1
            if interval == '1s':
                target_time = aligned_time - timedelta(seconds=i)
            elif interval == '1m':
                target_time = aligned_time - timedelta(minutes=i)
            elif interval == '3m':
                target_time = aligned_time - timedelta(minutes=i * 3)
            elif interval == '5m':
                target_time = aligned_time - timedelta(minutes=i * 5)
            elif interval == '15m':
                target_time = aligned_time - timedelta(minutes=i * 15)
            elif interval == '30m':
                target_time = aligned_time - timedelta(minutes=i * 30)
            elif interval == '1h':
                target_time = aligned_time - timedelta(hours=i)
            elif interval == '2h':
                target_time = aligned_time - timedelta(hours=i * 2)
            elif interval == '6h':
                target_time = aligned_time - timedelta(hours=i * 6)
            elif interval == '8h':
                target_time = aligned_time - timedelta(hours=i * 8)
            elif interval == '12h':
                target_time = aligned_time - timedelta(hours=i * 12)
            elif interval == '1d':
                target_time = aligned_time - timedelta(days=i)
            elif interval == '3d':
                target_time = aligned_time - timedelta(days=i * 3)
            elif interval == '1w':
                target_time = aligned_time - timedelta(weeks=i)
            elif interval == '1M':
                # For months, we need to handle differently
                target_time = aligned_time.replace(month=aligned_time.month - i if aligned_time.month > i else 12 - (i - aligned_time.month), 
                                                 year=aligned_time.year if aligned_time.month > i else aligned_time.year - 1)
            else:
                print(f"Unsupported interval: {interval}")
                return [], None
            
            # Format time for the historical handler
            target_datetime_str = target_time.strftime('%d-%m-%Y %H:%M')
            
            try:
                ha_data = get_heikin_ashi_by_datetime(symbol, interval, target_datetime_str)
                if ha_data:
                    # Convert to our format
                    formatted_data = {
                        "symbol": symbol.upper(),
                        "time": datetime.fromtimestamp(ha_data['timestamp']/1000).strftime('%H:%M'),
                        "open": ha_data['regular_open'],
                        "high": ha_data['regular_high'], 
                        "low": ha_data['regular_low'],
                        "close": ha_data['regular_close'],
                        "ha_open": ha_data['ha_open'],
                        "ha_high": ha_data['ha_high'],
                        "ha_low": ha_data['ha_low'],
                        "ha_close": ha_data['ha_close'],
                        "timestamp": ha_data['timestamp']
                    }
                    historical_ha_data.append(formatted_data)
                    print(f"✅ Got HA data for {target_datetime_str}")
                else:
                    print(f"⚠️  No data for {target_datetime_str}")
            except Exception as e:
                print(f"❌ Error getting data for {target_datetime_str}: {e}")
        
        if not historical_ha_data:
            print("❌ Could not fetch any historical data")
            return [], None
        
        # Sort by timestamp to ensure proper order
        historical_ha_data.sort(key=lambda x: x['timestamp'])
        
        # Get the last HA values for initialization
        last_ha = historical_ha_data[-1]
        previous_ha_values = {
            'ha_open': last_ha['ha_open'],
            'ha_high': last_ha['ha_high'],
            'ha_low': last_ha['ha_low'],
            'ha_close': last_ha['ha_close']
        }
        
        print(f"✅ Successfully fetched {len(historical_ha_data)} historical HA candles")
        print(f"🔧 Initialized with HA_open: {previous_ha_values['ha_open']:.2f}, HA_close: {previous_ha_values['ha_close']:.2f}")
        
        return historical_ha_data, previous_ha_values
        
    except Exception as e:
        print(f"❌ Error fetching historical HA data: {e}")
        return [], None

def get_next_interval_time(interval):
    """Calculate when the next candle of the given interval should complete"""
    now = datetime.now()
    
    if interval == '1s':
        next_second = now.replace(microsecond=0) + timedelta(seconds=1)
        return next_second.strftime('%H:%M:%S')
    elif interval == '1m':
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        return next_minute.strftime('%H:%M')
    elif interval == '3m':
        minutes = (now.minute // 3 + 1) * 3
        if minutes >= 60:
            next_time = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(minute=minutes, second=0, microsecond=0)
        return next_time.strftime('%H:%M')
    elif interval == '5m':
        minutes = (now.minute // 5 + 1) * 5
        if minutes >= 60:
            next_time = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(minute=minutes, second=0, microsecond=0)
        return next_time.strftime('%H:%M')
    elif interval == '15m':
        minutes = (now.minute // 15 + 1) * 15
        if minutes >= 60:
            next_time = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(minute=minutes, second=0, microsecond=0)
        return next_time.strftime('%H:%M')
    elif interval == '30m':
        minutes = (now.minute // 30 + 1) * 30
        if minutes >= 60:
            next_time = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(minute=minutes, second=0, microsecond=0)
        return next_time.strftime('%H:%M')
    elif interval == '1h':
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return next_hour.strftime('%H:%M')
    elif interval == '2h':
        hours = (now.hour // 2 + 1) * 2
        if hours >= 24:
            next_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(hour=hours, minute=0, second=0, microsecond=0)
        return next_time.strftime('%d %H:%M')
    elif interval == '6h':
        hours = (now.hour // 6 + 1) * 6
        if hours >= 24:
            next_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(hour=hours, minute=0, second=0, microsecond=0)
        return next_time.strftime('%d %H:%M')
    elif interval == '8h':
        hours = (now.hour // 8 + 1) * 8
        if hours >= 24:
            next_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(hour=hours, minute=0, second=0, microsecond=0)
        return next_time.strftime('%d %H:%M')
    elif interval == '12h':
        hours = (now.hour // 12 + 1) * 12
        if hours >= 24:
            next_time = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_time = now.replace(hour=hours, minute=0, second=0, microsecond=0)
        return next_time.strftime('%d %H:%M')
    elif interval == '1d':
        next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return next_day.strftime('%d/%m %H:%M')
    elif interval == '3d':
        next_time = now + timedelta(days=3)
        return next_time.strftime('%d/%m')
    elif interval == '1w':
        days_until_monday = 7 - now.weekday()
        next_monday = now + timedelta(days=days_until_monday)
        return next_monday.strftime('%d/%m')
    elif interval == '1M':
        if now.month == 12:
            next_month = now.replace(year=now.year+1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = now.replace(month=now.month+1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return next_month.strftime('%d/%m/%Y')
    else:
        return "Unknown"

def add_strategy_to_historical_data(historical_data):
    """
    Add strategy signals to historical data
    """
    for candle in historical_data:
        signal = generate_signal(candle)
        levels = calculate_entry_sl(candle, signal)
        candle.update({
            'signal': signal,
            'entry': levels['entry'],
            'stop_loss': levels['stop_loss']
        })
    return historical_data

async def ohlc_strategy_collector(symbol: str, interval: str, testnet: bool = False):
    """
    Collects OHLC data from Binance websocket, applies strategy, and displays with signals.
    Only processes completed candles at exact interval times.
    """
    display_data = []  # Only for display - separate from background processing
    show_heikin_ashi = True
    last_candle_time = None
    
    try:
        # Get historical Heikin Ashi data first (processed in background)
        print(f"📚 Processing historical data in background...")
        historical_ha_data, previous_ha_candle = await get_historical_ha_data(symbol, interval, 5)
        
        if historical_ha_data:
            # Add strategy signals to historical data (background processing only)
            historical_ha_data = add_strategy_to_historical_data(historical_ha_data)
            
            # Only add the LATEST historical candle to display data
            latest_historical = historical_ha_data[-1]
            display_data.append(latest_historical)
            
            # Display only the latest historical candle
            clear_screen()
            print_ohlcv_table_with_signals([latest_historical], show_heikin_ashi)
        else:
            print("⚠️  Starting without historical data - HA calculation may be less accurate initially")
            previous_ha_candle = None

        def format_row_with_strategy(kline):
            row_data = {
                "symbol": symbol.upper(),
                "time": datetime.fromtimestamp(int(kline['t'])/1000).strftime('%H:%M'),
                "open": float(kline['o']),
                "high": float(kline['h']),
                "low": float(kline['l']),
                "close": float(kline['c']),
                "timestamp": int(kline['t'])
            }
            
            # Calculate Heikin-Ashi values using the previous HA values
            ha_values = calculate_heikin_ashi(row_data, previous_ha_candle)
            row_data.update(ha_values)
            
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
            nonlocal previous_ha_candle, last_candle_time
            
            # Only process completed candles (when kline is closed)
            if not kline.get('x'):
                return  # Skip incomplete candles
            
            candle_time = int(kline['t'])
            candle_datetime = datetime.fromtimestamp(candle_time / 1000)
            
            # Check if this candle aligns with the interval boundary
            aligned_candle_time = align_time_to_interval(candle_datetime, interval)
            if candle_datetime.replace(second=0, microsecond=0) != aligned_candle_time:
                return  # Skip candles that don't align with interval boundaries
            
            # Check if this is a duplicate candle (same timestamp)
            if last_candle_time == candle_time:
                return
            
            # Skip if this candle is older than our last historical candle (if we have historical data)
            if historical_ha_data and candle_time <= historical_ha_data[-1]['timestamp']:
                return
            
            last_candle_time = candle_time
            formatted_candle = format_row_with_strategy(kline)
            
            # Add the new live candle to display data only
            display_data.append(formatted_candle)
            
            # Update previous HA values for next calculation
            previous_ha_candle = {
                'ha_open': formatted_candle['ha_open'],
                'ha_high': formatted_candle['ha_high'],
                'ha_low': formatted_candle['ha_low'],
                'ha_close': formatted_candle['ha_close']
            }
            
            # Show updated table with only display data (1 historical + live candles)
            clear_screen()
            recent_data = display_data[-5:]  # Show last 5 from display data only
            print_ohlcv_table_with_signals(recent_data, show_heikin_ashi)

        await ohlc_listener_futures_ws(symbol, interval, on_kline, testnet=testnet)
        
    except KeyboardInterrupt:
        print("\n🔄 Shutting down gracefully...")
        raise
    except Exception as e:
        print(f"\n❌ Error in strategy collector: {e}")
        raise

def main():
    symbol = "btcusdt"
    interval = "3m"  # You can now use: 1s, 1m, 3m, 5m, 15m, 30m, 1h, 2h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
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

# Example usage
if __name__ == "__main__":
    main()

