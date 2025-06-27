# Table/printing functions for websocket client
import io
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.logger import get_colored_signal, get_colored_position

# ANSI color codes
GREEN = '\033[92m'   # Green for BUY signals and LONG positions
RED = '\033[91m'     # Red for SELL signals
GREY = '\033[90m'    # Light grey for HOLD signals and NONE positions
RESET = '\033[0m'    # Reset color

def print_ohlcv_table_with_signals(data, show_heikin_ashi=True, return_output=False):
    # If return_output is True, redirect stdout to a string buffer
    if return_output:
        old_stdout = sys.stdout
        output_buffer = io.StringIO()
        sys.stdout = output_buffer
    
    # Fixed column widths
    col_widths = {
        'time': 8,
        'symbol': 10,
        'ohlc': 10,
        'signal': 10,
        'entry': 10,
        'sl': 10,
        'position': 10
    }
    
    # Print table header
    print("=" * 120)
    header = f"{'Time':<{col_widths['time']}} {'Symbol':<{col_widths['symbol']}}"
    if show_heikin_ashi:
        header += f" {'HA_Open':<{col_widths['ohlc']}} {'HA_High':<{col_widths['ohlc']}} {'HA_Low':<{col_widths['ohlc']}} {'HA_Close':<{col_widths['ohlc']}}"
    else:
        header += f" {'Open':<{col_widths['ohlc']}} {'High':<{col_widths['ohlc']}} {'Low':<{col_widths['ohlc']}} {'Close':<{col_widths['ohlc']}}"
    header += f" {'Signal':<{col_widths['signal']}}   {'Entry':<{col_widths['entry']}}   {'SL':<{col_widths['sl']}} {'POSITION':<{col_widths['position']}}"
    print(header)
    print("=" * 120)
    
    for row in data:
        signal = row.get('signal', 'HOLD')
        entry = row.get('entry')
        stop_loss = row.get('stop_loss')
        position = row.get('position', '-')        # Format strings with proper spacing
        entry_str = f"{entry:.2f}" if isinstance(entry, (int, float)) and entry is not None else "-"
        sl_str = f"{stop_loss:.2f}" if isinstance(stop_loss, (int, float)) and stop_loss is not None else "-"
        
        # Format position display (LONG or NONE) with color
        position_str = position if position else 'NONE'
          
        # Get colored versions using our logger helper functions
        colored_signal = get_colored_signal(signal)
        colored_position = get_colored_position(position_str)
        
        # Build the line
        line = f"{row['time']:<{col_widths['time']}} {row['symbol']:<{col_widths['symbol']}}"
        if show_heikin_ashi:
            line += f" {row.get('ha_open', '-'):<{col_widths['ohlc']}.2f} {row.get('ha_high', '-'):<{col_widths['ohlc']}.2f}"
            line += f" {row.get('ha_low', '-'):<{col_widths['ohlc']}.2f} {row.get('ha_close', '-'):<{col_widths['ohlc']}.2f}"
        else:
            line += f" {row['open']:<{col_widths['ohlc']}.2f} {row['high']:<{col_widths['ohlc']}.2f}"
            line += f" {row['low']:<{col_widths['ohlc']}.2f} {row['close']:<{col_widths['ohlc']}.2f}"
            
        # Fixed width columns with padding for signal and position text only (not ANSI codes)
        padding_signal = " " * (col_widths['signal'] - len(signal))
        padding_entry = " " * (col_widths['entry'] - len(entry_str))
        padding_sl = " " * (col_widths['sl'] - len(sl_str))
        padding_position = " " * (col_widths['position'] - len(position_str))
        
        # Add signal, entry, SL, and position with proper spacing
        line += f" {colored_signal}{padding_signal}   {entry_str}{padding_entry}   {sl_str}{padding_sl} {colored_position}{padding_position}"
        print(line)
    
    # If return_output is True, get the output and restore stdout
    if return_output:
        output = output_buffer.getvalue()
        sys.stdout = old_stdout
        return output
