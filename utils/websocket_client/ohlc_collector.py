import asyncio
from datetime import datetime
from .ws_listener import ohlc_listener_futures_ws
from .ha_utils import get_historical_ha_data, align_time_to_interval
from .clear_screen import clear_screen
from .display import print_ohlcv_table_with_signals
from .heikin_ashi import calculate_heikin_ashi
from basic_strategy import generate_ha_signal, reset_position, set_historical_processing
from utils.config import QUANTITY, BUY_OFFSET, SELL_OFFSET

def format_row_with_ha_signal(kline, symbol, previous_ha_candle):
    # Create base candle data
    row_data = {
        "symbol": symbol.upper(),
        "time": datetime.fromtimestamp(int(kline['t'])/1000).strftime('%H:%M'),
        "open": float(kline['o']),
        "high": float(kline['h']),
        "low": float(kline['l']),
        "close": float(kline['c']),
        "timestamp": int(kline['t'])
    }
    
    # Calculate Heikin Ashi values
    ha_values = calculate_heikin_ashi(row_data, previous_ha_candle)
    row_data.update(ha_values)
    
    # Generate signal using our new unified function
    current_candle = {
        'ha_open': row_data['ha_open'],
        'ha_high': row_data['ha_high'],
        'ha_low': row_data['ha_low'],
        'ha_close': row_data['ha_close']
    }
    
    signal, position = generate_ha_signal(previous_ha_candle, current_candle, 
                                         QUANTITY, BUY_OFFSET, SELL_OFFSET)
    
    # Instead of calculating entry/SL separately, use placeholder values
    # These could be calculated based on signal if needed
    entry = row_data['close'] if signal == 'BUY' else '-'
    stop_loss = row_data['close'] * 0.95 if signal == 'BUY' else '-'
    
    row_data.update({
        'signal': signal,
        'entry': entry,
        'stop_loss': stop_loss,
        'position': position
    })
    
    return row_data

def process_historical_data(historical_data):
    # Reset position before processing historical data
    reset_position()
    
    # Set flag to indicate we're processing historical data
    set_historical_processing(True)
    
    processed_data = []
    previous_ha_candle = None
    
    for i, candle in enumerate(historical_data):
        if i == 0:
            # For the first candle, we don't have a previous candle
            signal, position = generate_ha_signal(None, {
                'ha_open': candle['ha_open'],
                'ha_high': candle['ha_high'],
                'ha_low': candle['ha_low'],
                'ha_close': candle['ha_close']
            }, QUANTITY, BUY_OFFSET, SELL_OFFSET)
        else:
            # For subsequent candles, use the previous processed candle
            previous = {
                'ha_open': processed_data[i-1]['ha_open'],
                'ha_high': processed_data[i-1]['ha_high'],
                'ha_low': processed_data[i-1]['ha_low'],
                'ha_close': processed_data[i-1]['ha_close']
            }
            signal, position = generate_ha_signal(previous, {
                'ha_open': candle['ha_open'],
                'ha_high': candle['ha_high'],
                'ha_low': candle['ha_low'],
                'ha_close': candle['ha_close']
            }, QUANTITY, BUY_OFFSET, SELL_OFFSET)
        
        # For historical data, we'll always have HOLD signals
        # but calculate entry/SL as if it were a real signal based on HA patterns
        
        # Simulated entry and stop loss (won't actually trigger trades)
        entry = '-'
        stop_loss = '-'
        
        # Update candle with signal info (even though signal will be HOLD)
        candle.update({
            'signal': signal,
            'entry': entry,
            'stop_loss': stop_loss,
            'position': position,
            'historical': True
        })
        
        processed_data.append(candle)
        previous_ha_candle = {
            'ha_open': candle['ha_open'],
            'ha_high': candle['ha_high'],
            'ha_low': candle['ha_low'],
            'ha_close': candle['ha_close']
        }
    
    # Reset flag after processing historical data
    set_historical_processing(False)
    
    return processed_data, previous_ha_candle

async def ohlc_strategy_collector(symbol: str, interval: str, testnet: bool = False):
    display_data = []
    show_heikin_ashi = True
    last_candle_time = None
    try:
        # Get historical data and initialize previous_ha_candle
        historical_raw_data, raw_previous_ha_candle = await get_historical_ha_data(symbol, interval, 5)
        
        if historical_raw_data:
            # Process historical data with our new signal function
            historical_ha_data, previous_ha_candle = process_historical_data(historical_raw_data)
            
            # Add the latest historical candle to display data
            latest_historical = historical_ha_data[-1]
            display_data.append(latest_historical)
            
            # Show initial data
            clear_screen()
            print_ohlcv_table_with_signals([latest_historical], show_heikin_ashi)
        else:
            previous_ha_candle = None
        
        async def on_kline(kline):
            nonlocal previous_ha_candle, last_candle_time
            
            # Skip if candle is not closed yet
            if not kline.get('x'):
                return
                
            # Process timestamp and align to interval
            candle_time = int(kline['t'])
            candle_datetime = datetime.fromtimestamp(candle_time / 1000)
            aligned_candle_time = align_time_to_interval(candle_datetime, interval)
            
            # Skip if candle time doesn't align with interval
            if candle_datetime.replace(second=0, microsecond=0) != aligned_candle_time:
                return
                
            # Skip duplicate candles
            if last_candle_time == candle_time:
                return
                
            # Skip if candle is older than our latest historical candle
            if historical_raw_data and candle_time <= historical_raw_data[-1]['timestamp']:
                return
                
            last_candle_time = candle_time
            
            # Format the candle data with our new signal function
            formatted_candle = format_row_with_ha_signal(kline, symbol, previous_ha_candle)
            formatted_candle['historical'] = False
            
            # Add to display data
            display_data.append(formatted_candle)
            
            # Update previous_ha_candle for next iteration
            previous_ha_candle = {
                'ha_open': formatted_candle['ha_open'],
                'ha_high': formatted_candle['ha_high'],
                'ha_low': formatted_candle['ha_low'],
                'ha_close': formatted_candle['ha_close']
            }
            
            # Update display
            clear_screen()
            print_ohlcv_table_with_signals(display_data, show_heikin_ashi)
            
        # Start websocket listener
        await ohlc_listener_futures_ws(symbol, interval, on_kline, testnet=testnet)
        
    except KeyboardInterrupt:
        print("\n🔄 Shutting down gracefully...")
        raise
    except Exception as e:
        print(f"\n❌ Error in strategy collector: {e}")
        raise
