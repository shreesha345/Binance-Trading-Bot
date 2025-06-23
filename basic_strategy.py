# Global state to track position
_position = 'NONE'  # Initialize as 'NONE' instead of None
_processing_historical = False  # Flag to indicate if we're processing historical data

def set_historical_processing(is_historical):
    """
    Set whether we're currently processing historical data
    
    Args:
        is_historical (bool): True if processing historical data
    """
    global _processing_historical
    _processing_historical = is_historical

def generate_ha_signal(previous_candle, current_candle, quantity, buy_offset, sell_offset):
    """
    Single function responsible for all signal logic based on Heikin Ashi candles
    
    Args:
        previous_candle (dict): Previous Heikin Ashi candle with keys:
            - ha_open, ha_high, ha_low, ha_close (float values)
        current_candle (dict): Current Heikin Ashi candle with keys:
            - ha_open, ha_high, ha_low, ha_close (float values)
        quantity (float): Trading quantity from config
        buy_offset (float): Buy price offset from config
        sell_offset (float): Sell price offset from config
    
    Returns:
        tuple: (action, position) where:
            - action is 'BUY', 'SELL', or 'HOLD'
            - position is 'LONG' or 'NONE'
    """
    global _position, _processing_historical
    
    # Default to holding current position
    action = "HOLD"
    
    # If we're processing historical data, don't generate actual trade signals
    if _processing_historical:
        return action, _position
        
    # If there's no previous candle, just hold
    if not previous_candle:
        return action, _position
    
    # Get current Heikin Ashi values
    ha_open = float(current_candle['ha_open'])
    ha_close = float(current_candle['ha_close'])
    ha_high = float(current_candle['ha_high'])
    ha_low = float(current_candle['ha_low'])
    
    # Get previous Heikin Ashi values
    prev_ha_open = float(previous_candle['ha_open'])
    prev_ha_close = float(previous_candle['ha_close'])
    
    # Basic strategy: Buy when current candle close is higher than open (bullish)
    # and previous candle was also bullish
    if _position == 'NONE' and ha_close > ha_open and prev_ha_close > prev_ha_open:
        _position = 'LONG'
        action = 'BUY'
    
    # Sell when current candle close is lower than open (bearish)
    # and we're in a long position
    elif _position == 'LONG' and ha_close < ha_open:
        action = 'SELL'
        _position = 'NONE'
    
    # Apply the buy/sell offsets if needed for more sophisticated entry/exit
    # This is a placeholder - you can expand this with your own logic
    
    return action, _position

def reset_position():
    """
    Reset the position tracking (useful for testing or restarting)
    """
    global _position
    _position = 'NONE'