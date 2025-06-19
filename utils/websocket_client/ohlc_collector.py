import asyncio
from datetime import datetime
from .ws_listener import ohlc_listener_futures_ws
from .ha_utils import get_historical_ha_data, align_time_to_interval
from .clear_screen import clear_screen
from .display import print_ohlcv_table_with_signals
from .strategy import add_strategy_to_historical_data, format_row_with_strategy

async def ohlc_strategy_collector(symbol: str, interval: str, testnet: bool = False):
    display_data = []
    show_heikin_ashi = True
    last_candle_time = None
    try:
        historical_ha_data, previous_ha_candle = await get_historical_ha_data(symbol, interval, 5)
        if historical_ha_data:
            historical_ha_data = add_strategy_to_historical_data(historical_ha_data)
            latest_historical = historical_ha_data[-1]
            display_data.append(latest_historical)
            clear_screen()
            print_ohlcv_table_with_signals([latest_historical], show_heikin_ashi)
        else:
            previous_ha_candle = None
        async def on_kline(kline):
            nonlocal previous_ha_candle, last_candle_time
            if not kline.get('x'):
                return
            candle_time = int(kline['t'])
            candle_datetime = datetime.fromtimestamp(candle_time / 1000)
            aligned_candle_time = align_time_to_interval(candle_datetime, interval)
            if candle_datetime.replace(second=0, microsecond=0) != aligned_candle_time:
                return
            if last_candle_time == candle_time:
                return
            if historical_ha_data and candle_time <= historical_ha_data[-1]['timestamp']:
                return
            last_candle_time = candle_time
            formatted_candle = format_row_with_strategy(kline, symbol, previous_ha_candle)
            display_data.append(formatted_candle)
            previous_ha_candle = {
                'ha_open': formatted_candle['ha_open'],
                'ha_high': formatted_candle['ha_high'],
                'ha_low': formatted_candle['ha_low'],
                'ha_close': formatted_candle['ha_close']
            }
            clear_screen()
            recent_data = display_data[-5:]
            print_ohlcv_table_with_signals(recent_data, show_heikin_ashi)
        await ohlc_listener_futures_ws(symbol, interval, on_kline, testnet=testnet)
    except KeyboardInterrupt:
        print("\n🔄 Shutting down gracefully...")
        raise
    except Exception as e:
        print(f"\n❌ Error in strategy collector: {e}")
        raise
