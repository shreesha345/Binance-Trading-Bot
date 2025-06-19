# Table/printing functions for websocket client

def print_ohlcv_table_with_signals(data, show_heikin_ashi=True):
    print("=" * 120)
    header = f"{'Time':<8} {'Symbol':<10}"
    if show_heikin_ashi:
        header += f" {'HA_Open':<10} {'HA_High':<10} {'HA_Low':<10} {'HA_Close':<10}"
    else:
        header += f" {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10}"
    header += f" {'Signal':<6} {'Entry':<10} {'SL':<10}"
    print(header)
    print("=" * 120)
    for row in data:
        signal = row.get('signal', 'HOLD')
        entry = row.get('entry', '-')
        stop_loss = row.get('stop_loss', '-')
        entry_str = f"{entry:.2f}" if isinstance(entry, (int, float)) else "-"
        sl_str = f"{stop_loss:.2f}" if isinstance(stop_loss, (int, float)) else "-"
        line = f"{row['time']:<8} {row['symbol']:<10}"
        if show_heikin_ashi:
            line += f" {row.get('ha_open', '-'):<10.2f} {row.get('ha_high', '-'):<10.2f}"
            line += f" {row.get('ha_low', '-'):<10.2f} {row.get('ha_close', '-'):<10.2f}"
        else:
            line += f" {row['open']:<10.2f} {row['high']:<10.2f}"
            line += f" {row['low']:<10.2f} {row['close']:<10.2f}"
        line += f" {signal:<6} {entry_str:<10} {sl_str:<10}"
        print(line)
