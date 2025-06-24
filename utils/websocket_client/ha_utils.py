from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#custom imports
from utils.historical_handler import get_heikin_ashi_by_datetime

def align_time_to_interval(dt, interval):
    # Align time to the start of the interval period
    if interval == '1s':
        return dt.replace(microsecond=0)
    elif interval == '1m':
        return dt.replace(second=0, microsecond=0)
    elif interval == '3m':
        minutes = (dt.minute // 3) * 3
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '5m':
        minutes = (dt.minute // 5) * 5
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '15m':
        minutes = (dt.minute // 15) * 15
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '30m':
        minutes = (dt.minute // 30) * 30
        return dt.replace(minute=minutes, second=0, microsecond=0)
    elif interval == '1h':
        return dt.replace(minute=0, second=0, microsecond=0)
    elif interval == '2h':
        hours = (dt.hour // 2) * 2
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '6h':
        hours = (dt.hour // 6) * 6
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '8h':
        hours = (dt.hour // 8) * 8
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '12h':
        hours = (dt.hour // 12) * 12
        return dt.replace(hour=hours, minute=0, second=0, microsecond=0)
    elif interval == '1d':
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == '3d':
        days_since_epoch = (dt - datetime(1970, 1, 1)).days
        aligned_days = (days_since_epoch // 3) * 3
        aligned_date = datetime(1970, 1, 1) + timedelta(days=aligned_days)
        return aligned_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == '1w':
        days_since_monday = dt.weekday()
        monday = dt - timedelta(days=days_since_monday)
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    elif interval == '1M':
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return dt

async def get_historical_ha_data(symbol: str, interval: str, count: int = 5):
    try:
        historical_ha_data = []
        current_time = datetime.now()
        
        # Align current time to the current interval boundary
        aligned_time = align_time_to_interval(current_time, interval)
        
        for i in range(count, 0, -1):
            # Calculate the target time by subtracting the interval
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
                target_time = aligned_time.replace(month=aligned_time.month - i if aligned_time.month > i else 12 - (i - aligned_time.month), 
                                                 year=aligned_time.year if aligned_time.month > i else aligned_time.year - 1)
            else:
                return [], None                
            # Ensure target time is aligned to the interval boundary
            target_time = align_time_to_interval(target_time, interval)
            
            target_datetime_str = target_time.strftime('%d-%m-%Y %H:%M')
            try:
                ha_data = get_heikin_ashi_by_datetime(symbol, interval, target_datetime_str)
                if ha_data:
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
            except Exception:
                pass
        if not historical_ha_data:
            return [], None
        historical_ha_data.sort(key=lambda x: x['timestamp'])
        last_ha = historical_ha_data[-1]
        previous_ha_values = {
            'ha_open': last_ha['ha_open'],
            'ha_high': last_ha['ha_high'],
            'ha_low': last_ha['ha_low'],
            'ha_close': last_ha['ha_close']
        }
        return historical_ha_data, previous_ha_values
    except Exception:
        return [], None
