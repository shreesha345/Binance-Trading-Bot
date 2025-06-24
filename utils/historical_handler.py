from datetime import datetime, timedelta, timezone
import time
import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
from utils.config import MODE, BINANCE_API_KEY, BINANCE_API_SECRET

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
    
    # Align to exact interval boundary by truncating any seconds/microseconds
    if interval == '1m':
        target_dt_local = target_dt_local.replace(second=0, microsecond=0)
    elif interval == '3m':
        minutes = (target_dt_local.minute // 3) * 3
        target_dt_local = target_dt_local.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '5m':
        minutes = (target_dt_local.minute // 5) * 5
        target_dt_local = target_dt_local.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '15m':
        minutes = (target_dt_local.minute // 15) * 15
        target_dt_local = target_dt_local.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '30m':
        minutes = (target_dt_local.minute // 30) * 30
        target_dt_local = target_dt_local.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '1h':
        target_dt_local = target_dt_local.replace(minute=0, second=0, microsecond=0)
    # Add more intervals as needed
    
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
        
        # For all intervals, we want exact matching on interval boundaries
        # Example: for 1m, we want an exact match on minutes with seconds=0
        if interval == '1s':
            if kline_open_time_utc.replace(microsecond=0) == target_dt_utc.replace(microsecond=0):
                target_candle_index = i
                break
        elif interval == '1m':
            if kline_open_time_utc.replace(second=0, microsecond=0) == target_dt_utc.replace(second=0, microsecond=0):
                target_candle_index = i
                break
        elif interval in ['3m', '5m', '15m', '30m']:
            # Extract interval value (e.g., 3 from '3m')
            interval_minutes = int(interval[:-1])
            # Check if both timestamps align to the same interval boundary
            if (kline_open_time_utc.replace(second=0, microsecond=0).minute % interval_minutes == 0 and
                target_dt_utc.replace(second=0, microsecond=0).minute % interval_minutes == 0 and
                kline_open_time_utc.replace(second=0, microsecond=0) == target_dt_utc.replace(second=0, microsecond=0)):
                target_candle_index = i
                break
        elif interval in ['1h', '2h', '6h', '8h', '12h']:
            # For hourly intervals, ensure both timestamps align to the exact hour boundary
            if interval == '1h':
                if (kline_open_time_utc.replace(minute=0, second=0, microsecond=0) == 
                    target_dt_utc.replace(minute=0, second=0, microsecond=0)):
                    target_candle_index = i
                    break
            else:
                # For multi-hour intervals, check if both timestamps align to the same interval boundary
                interval_hours = int(interval[:-1])
                if (kline_open_time_utc.hour % interval_hours == 0 and
                    target_dt_utc.hour % interval_hours == 0 and
                    kline_open_time_utc.replace(minute=0, second=0, microsecond=0) == 
                    target_dt_utc.replace(minute=0, second=0, microsecond=0)):
                    target_candle_index = i
                    break
        elif interval in ['1d', '3d']:
            # For daily intervals, match on day boundaries
            if interval == '1d':
                if (kline_open_time_utc.replace(hour=0, minute=0, second=0, microsecond=0) == 
                    target_dt_utc.replace(hour=0, minute=0, second=0, microsecond=0)):
                    target_candle_index = i
                    break
            else:  # '3d'
                # For 3-day intervals, calculate days from epoch and check if both align to the same 3-day boundary
                days_since_epoch_kline = (kline_open_time_utc - datetime(1970, 1, 1, tzinfo=timezone.utc)).days
                days_since_epoch_target = (target_dt_utc - datetime(1970, 1, 1, tzinfo=timezone.utc)).days
                if (days_since_epoch_kline % 3 == 0 and
                    days_since_epoch_target % 3 == 0 and
                    days_since_epoch_kline == days_since_epoch_target):
                    target_candle_index = i
                    break
        elif interval in ['1w', '1M']:
            # For weekly intervals, ensure both timestamps align to the same week
            if interval == '1w':
                # Use isocalendar to get year and week number
                kline_year, kline_week, _ = kline_open_time_utc.isocalendar()
                target_year, target_week, _ = target_dt_utc.isocalendar()
                
                if kline_year == target_year and kline_week == target_week:
                    target_candle_index = i
                    break
            else:  # '1M'
                # For monthly intervals, ensure both timestamps are in the same month and year
                if (kline_open_time_utc.year == target_dt_utc.year and 
                    kline_open_time_utc.month == target_dt_utc.month):
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
    
    print(f"\n📊 Heikin Ashi Candle for {candle['open_time']} UTC")
    print(f"Symbol: {candle.get('symbol', 'Unknown')}")
    print(f"Volume: {candle['volume']}")
    print(f"Number of Trades: {candle['number_of_trades']}")
    
    print("\nRegular Candle Values:")
    print(f"Open: {candle['regular_open']}")
    print(f"High: {candle['regular_high']}")
    print(f"Low: {candle['regular_low']}")
    print(f"Close: {candle['regular_close']}")
    
    print("\nHeikin Ashi Values:")
    print(f"HA Open: {candle['ha_open']}")
    print(f"HA High: {candle['ha_high']}")
    print(f"HA Low: {candle['ha_low']}")
    print(f"HA Close: {candle['ha_close']}")

# Test the function if run directly
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python historical_handler.py <symbol> <interval> <target_datetime>")
        print("Example: python historical_handler.py BTCUSDT 1m '15-06-2023 12:30'")
        sys.exit(1)
    
    symbol = sys.argv[1]
    interval = sys.argv[2]
    target_datetime = sys.argv[3]
    
    print(f"Fetching Heikin Ashi candle for {symbol} at {target_datetime} with {interval} interval...")
    
    candle = get_heikin_ashi_by_datetime(symbol, interval, target_datetime)
    print_heikin_ashi_candle(candle)
