def generate_signal(ohlc_data):
    """
    Basic strategy: Generate BUY signal when close price is an even number
    
    Args:
        ohlc_data (dict): Dictionary containing OHLC data with keys:
            - open, high, low, close (float values)
            - symbol, time (string values)
    
    Returns:
        str: 'BUY' if close price is even, 'HOLD' otherwise
    """
    close_price = float(ohlc_data['close'])
    
    # Check if the integer part of close price is even
    if int(close_price) % 2 == 0:
        return 'BUY'
    else:
        return 'HOLD'

def calculate_entry_sl(ohlc_data, signal):
    """
    Calculate entry price and stop loss based on signal
    
    Args:
        ohlc_data (dict): OHLC data
        signal (str): Trading signal ('BUY' or 'HOLD')
    
    Returns:
        dict: Entry price and stop loss levels
    """
    if signal == 'BUY':
        entry = ohlc_data['close']
        stop_loss = ohlc_data['low']
        return {
            'entry': entry,
            'stop_loss': stop_loss
        }
    else:
        return {
            'entry': None,
            'stop_loss': None
        }