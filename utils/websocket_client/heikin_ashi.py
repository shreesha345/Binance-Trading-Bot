def calculate_heikin_ashi(current, previous=None):
    if previous is None:
        ha_open = current['open']
        ha_close = (current['open'] + current['high'] + current['low'] + current['close']) / 4
    else:
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
