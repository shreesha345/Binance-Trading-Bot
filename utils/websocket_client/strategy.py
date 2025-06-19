from basic_strategy import generate_signal, calculate_entry_sl

def add_strategy_to_historical_data(historical_data):
    for candle in historical_data:
        signal = generate_signal(candle)
        levels = calculate_entry_sl(candle, signal)
        candle.update({
            'signal': signal,
            'entry': levels['entry'],
            'stop_loss': levels['stop_loss']
        })
    return historical_data

def format_row_with_strategy(kline, symbol, previous_ha_candle):
    from datetime import datetime
    from .heikin_ashi import calculate_heikin_ashi
    row_data = {
        "symbol": symbol.upper(),
        "time": datetime.fromtimestamp(int(kline['t'])/1000).strftime('%H:%M'),
        "open": float(kline['o']),
        "high": float(kline['h']),
        "low": float(kline['l']),
        "close": float(kline['c']),
        "timestamp": int(kline['t'])
    }
    ha_values = calculate_heikin_ashi(row_data, previous_ha_candle)
    row_data.update(ha_values)
    signal = generate_signal(row_data)
    levels = calculate_entry_sl(row_data, signal)
    row_data.update({
        'signal': signal,
        'entry': levels['entry'],
        'stop_loss': levels['stop_loss']
    })
    return row_data
