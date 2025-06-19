import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
from datetime import datetime, timedelta, timezone
from config import MODE, BINANCE_API_KEY, BINANCE_API_SECRET  # Fixed import path
import time

def setup_binance_client():
    """
    Set up and return a Binance client using API keys from environment variables.
    For public data like historical klines, API keys are required but don't need permissions.
    """
    api_key = BINANCE_API_KEY
    api_secret = BINANCE_API_SECRET

    if not api_key or not api_secret:
        print("Warning: API key and secret not found. Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables.")
        print("You can create API keys at https://www.binance.com/en/my/settings/api-management")
    
    return Client(api_key, api_secret, testnet=MODE)

def convert_to_heikin_ashi(candles):
    """
    Convert regular candlestick data to Heikin Ashi candles.
    
    Parameters:
    - candles: list of regular candlestick data from Binance
    
    Returns:
    - A list of Heikin Ashi candle dictionaries
    """
    ha_candles = []
    
    for i, candle in enumerate(candles):
        # Extract OHLC values from regular candle
        regular_open = float(candle[1])
        regular_high = float(candle[2])
        regular_low = float(candle[3])
        regular_close = float(candle[4])
        
        # For the first candle, HA values are calculated differently
        if i == 0:
            ha_open = ((regular_open + regular_close) / 2)
        else:
            # HA Open = (Previous HA Open + Previous HA Close) / 2
            ha_open = (ha_candles[-1]['ha_open'] + ha_candles[-1]['ha_close']) / 2

        # HA Close = (Open + High + Low + Close) / 4
        ha_close = ((regular_open + regular_high + regular_low + regular_close) / 4)
        
        # HA High = Max(High, HA Open, HA Close)
        ha_high = max(regular_high, ha_open, ha_close)
        
        # HA Low = Min(Low, HA Open, HA Close)
        ha_low = min(regular_low, ha_open, ha_close)
        
        # Create a new dictionary with both regular and HA values
        ha_candle = {
            'timestamp': candle[0],
            'open_time': datetime.fromtimestamp(candle[0] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'close_time': datetime.fromtimestamp(candle[6] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'regular_open': regular_open,
            'regular_high': regular_high,
            'regular_low': regular_low,
            'regular_close': regular_close,
            'volume': float(candle[5]),
            'number_of_trades': int(candle[8]),
            'ha_open': ha_open,
            'ha_high': ha_high,
            'ha_low': ha_low,
            'ha_close': ha_close,
        }
        
        ha_candles.append(ha_candle)
    
    return ha_candles

def format_to_two_decimals(number):
    """
    Format a number to show exactly two decimal places without rounding.
    
    Parameters:
    - number: float or int - The number to format
    
    Returns:
    - String with exactly two decimal places
    """
    # Convert to string
    num_str = str(number)
    
    # Split by decimal point
    parts = num_str.split('.')
    
    # Get the integer part
    integer_part = parts[0]
    
    # If there's a decimal part, take only the first two digits
    if len(parts) > 1:
        decimal_part = parts[1][:2].ljust(2, '0')  # Ensure exactly 2 digits, pad with 0 if needed
    else:
        decimal_part = '00'
    
    return f"{integer_part}.{decimal_part}"

def get_heikin_ashi_by_datetime(symbol, interval, target_datetime_str):
    """
    Fetch Heikin Ashi candle for the exact datetime specified.
    
    Args:
        symbol (str): Trading pair symbol, e.g. 'BTCUSDT'
        interval (str): Kline interval, e.g. '1s', '1m', '3m', '5m', '15m', '30m', '1h', '2h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'
        target_datetime_str (str): Target datetime in 'dd-mm-YYYY HH:MM' (24h) format, local time
    
    Returns:
        The Heikin Ashi candle data, or None if not found
    """
    # Parse the target datetime string as local time and convert to UTC (timezone-aware)
    target_dt_local = datetime.strptime(target_datetime_str, '%d-%m-%Y %H:%M')
    try:
        from tzlocal import get_localzone
        local_tz = get_localzone()
        target_dt_local = target_dt_local.replace(tzinfo=local_tz)
        target_dt_utc = target_dt_local.astimezone(timezone.utc)
    except Exception:
        offset = datetime.now() - datetime.utcnow()
        target_dt_utc = (target_dt_local - offset).replace(tzinfo=timezone.utc)
    
    # Calculate the time range based on interval for proper Heikin Ashi calculation
    if interval == '1s':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (10 * 1000)  # 10 seconds before
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (1000)  # 1 second after
    elif interval == '1m':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (10 * 60 * 1000)  # 10 minutes before
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (60 * 1000)  # 1 minute after
    elif interval == '3m':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (30 * 60 * 1000)  # 30 minutes before (10 * 3m)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (3 * 60 * 1000)  # 3 minutes after
    elif interval == '5m':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (50 * 60 * 1000)  # 50 minutes before (10 * 5m)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (5 * 60 * 1000)  # 5 minutes after
    elif interval == '15m':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (150 * 60 * 1000)  # 150 minutes before (10 * 15m)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (15 * 60 * 1000)  # 15 minutes after
    elif interval == '30m':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (300 * 60 * 1000)  # 300 minutes before (10 * 30m)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (30 * 60 * 1000)  # 30 minutes after
    elif interval == '1h':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (10 * 60 * 60 * 1000)  # 10 hours before
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (60 * 60 * 1000)  # 1 hour after
    elif interval == '2h':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (20 * 60 * 60 * 1000)  # 20 hours before (10 * 2h)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (2 * 60 * 60 * 1000)  # 2 hours after
    elif interval == '6h':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (60 * 60 * 60 * 1000)  # 60 hours before (10 * 6h)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (6 * 60 * 60 * 1000)  # 6 hours after
    elif interval == '8h':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (80 * 60 * 60 * 1000)  # 80 hours before (10 * 8h)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (8 * 60 * 60 * 1000)  # 8 hours after
    elif interval == '12h':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (120 * 60 * 60 * 1000)  # 120 hours before (10 * 12h)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (12 * 60 * 60 * 1000)  # 12 hours after
    elif interval == '1d':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (10 * 24 * 60 * 60 * 1000)  # 10 days before
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (24 * 60 * 60 * 1000)  # 1 day after
    elif interval == '3d':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (30 * 24 * 60 * 60 * 1000)  # 30 days before (10 * 3d)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (3 * 24 * 60 * 60 * 1000)  # 3 days after
    elif interval == '1w':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (10 * 7 * 24 * 60 * 60 * 1000)  # 10 weeks before
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (7 * 24 * 60 * 60 * 1000)  # 1 week after
    elif interval == '1M':
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (10 * 30 * 24 * 60 * 60 * 1000)  # ~10 months before
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (30 * 24 * 60 * 60 * 1000)  # ~1 month after
    else:
        # Default fallback
        start_time_ms = int(target_dt_utc.timestamp() * 1000) - (10 * 60 * 1000)
        end_time_ms = int(target_dt_utc.timestamp() * 1000) + (60 * 1000)

    client = setup_binance_client()
    try:
        klines = client.futures_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time_ms,
            end_time=end_time_ms
        )
    except BinanceAPIException as e:
        print(f"Error fetching klines: {e}")
        return None

    if not klines:
        print("No data received.")
        return None

    # Find the exact candle for the target datetime with interval-specific matching
    target_candle_index = -1
    for i, kline in enumerate(klines):
        kline_open_time_utc = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc)
        
        # For different intervals, we need to match differently
        if interval in ['1s', '1m']:
            # Match by exact time
            target_resolution = timedelta(seconds=1) if interval == '1s' else timedelta(minutes=1)
            if abs(kline_open_time_utc - target_dt_utc) < target_resolution:
                target_candle_index = i
                break
        elif interval in ['3m', '5m', '15m', '30m']:
            # Match by minute boundaries
            interval_minutes = int(interval[:-1])
            target_minute = target_dt_utc.minute
            kline_minute = kline_open_time_utc.minute
            if (kline_open_time_utc.replace(minute=0, second=0, microsecond=0) == 
                target_dt_utc.replace(minute=0, second=0, microsecond=0) and
                kline_minute == target_minute):
                target_candle_index = i
                break
        elif interval in ['1h', '2h', '6h', '8h', '12h']:
            # Match by hour boundaries
            if interval == '1h':
                if kline_open_time_utc.replace(minute=0, second=0, microsecond=0) == target_dt_utc.replace(minute=0, second=0, microsecond=0):
                    target_candle_index = i
                    break
            else:
                interval_hours = int(interval[:-1])
                if (kline_open_time_utc.replace(minute=0, second=0, microsecond=0).hour % interval_hours == 
                    target_dt_utc.replace(minute=0, second=0, microsecond=0).hour % interval_hours and
                    kline_open_time_utc.date() == target_dt_utc.date()):
                    target_candle_index = i
                    break
        elif interval in ['1d', '3d']:
            # Match by day boundaries
            if interval == '1d':
                if kline_open_time_utc.date() == target_dt_utc.date():
                    target_candle_index = i
                    break
            else:  # 3d
                days_diff = (target_dt_utc.date() - kline_open_time_utc.date()).days
                if days_diff % 3 == 0:
                    target_candle_index = i
                    break
        elif interval in ['1w', '1M']:
            # Match by week/month boundaries
            if interval == '1w':
                if (kline_open_time_utc.isocalendar()[1] == target_dt_utc.isocalendar()[1] and
                    kline_open_time_utc.year == target_dt_utc.year):
                    target_candle_index = i
                    break
            else:  # 1M
                if (kline_open_time_utc.month == target_dt_utc.month and
                    kline_open_time_utc.year == target_dt_utc.year):
                    target_candle_index = i
                    break
    
    if target_candle_index == -1:
        print(f"No {interval} candle found for the specified datetime: {target_datetime_str}")
        return None
    
    # Convert all candles to Heikin Ashi (we need previous candles for proper calculation)
    ha_candles = convert_to_heikin_ashi(klines)
    
    # Return the Heikin Ashi candle for the target datetime
    return ha_candles[target_candle_index]

def print_heikin_ashi_candle(candle):
    """
    Print Heikin Ashi candle data in a formatted way.
    """
    if not candle:
        print("No candle data available.")
        return
    
    # Extract date and time separately
    datetime_obj = datetime.strptime(candle['open_time'], '%Y-%m-%d %H:%M:%S')
    date_str = datetime_obj.strftime('%d-%m-%Y')  # Format: dd-mm-YYYY
    time_str = datetime_obj.strftime('%H:%M')     # Format: HH:MM
    
    print(f"Date: {date_str}")
    print(f"Time: {time_str}")
    print("Heikin Ashi Candle:")
    print(f"  Open:  {format_to_two_decimals(candle['ha_open'])}")
    print(f"  High:  {format_to_two_decimals(candle['ha_high'])}")
    print(f"  Low:   {format_to_two_decimals(candle['ha_low'])}")
    print(f"  Close: {format_to_two_decimals(candle['ha_close'])}")

def main():
    """
    Example usage: Get Heikin Ashi data for a specific datetime
    """
    # Configuration
    symbol = 'BTCUSDT'      # Trading pair
    interval = '1m'         # 1 minute candles
    
    # Your specific datetime example
    target_datetime = '19-06-2025 20:18'  # Format: dd-mm-YYYY HH:MM
    
    print(f"Fetching Heikin Ashi data for {symbol} at {target_datetime}...")
    
    # Get the Heikin Ashi candle for the specific datetime
    ha_candle = get_heikin_ashi_by_datetime(symbol, interval, target_datetime)
    
    # Print the result
    print_heikin_ashi_candle(ha_candle)
    
    # You can also access individual values like this:
    if ha_candle:
        print(f"\nQuick access:")
        print(f"HA Open: {format_to_two_decimals(ha_candle['ha_open'])}")
        print(f"HA High: {format_to_two_decimals(ha_candle['ha_high'])}")
        print(f"HA Low: {format_to_two_decimals(ha_candle['ha_low'])}")
        print(f"HA Close: {format_to_two_decimals(ha_candle['ha_close'])}")

if __name__ == "__main__":
    # main()
    
    # You can also call it directly like this:
    ha_data = get_heikin_ashi_by_datetime('BTCUSDT', '1m', '19-06-2025 20:31')
    # print_heikin_ashi_candle(ha_data)
    print(ha_data)