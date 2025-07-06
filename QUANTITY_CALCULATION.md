# Price-Based Quantity Calculation

The trading bot now supports calculating order quantity based on a fixed USDT price value instead of just using fixed quantity or percentage-based calculation.

## Available Quantity Calculation Modes

1. **Fixed Quantity** (`quantity_type = "fixed"`): 
   - Uses a fixed quantity value directly
   - Set the `quantity` parameter to the desired fixed quantity

2. **Percentage-Based** (`quantity_type = "percentage"`):
   - Calculates quantity based on a percentage of your available balance
   - Set the `quantity_percentage` parameter to the desired percentage (1-100)

3. **Price-Based** (`quantity_type = "price"`):
   - Calculates quantity to match a specific USDT value
   - Set the `price_value` parameter to the desired USDT amount
   - For example, setting `price_value = "10"` will calculate a quantity that equals 10 USDT worth of the asset

## Leverage Support

You can now set the leverage for trading:

- Set the `leverage` parameter to your desired leverage value (1-125 depending on the asset)
- The leverage will affect the quantity calculation in all modes
- Higher leverage will result in larger positions with the same amount of capital

## Examples

### Fixed Quantity Example
```json
{
  "quantity_type": "fixed",
  "quantity": "0.1",
  "leverage": "3"
}
```
This will use a fixed quantity of 0.1 ETH (for ETHUSDT) with 3x leverage.

### Percentage-Based Example
```json
{
  "quantity_type": "percentage",
  "quantity_percentage": "5",
  "leverage": "5"
}
```
This will use 5% of your available balance with 5x leverage.

### Price-Based Example
```json
{
  "quantity_type": "price",
  "price_value": "10",
  "leverage": "2"
}
```
This will calculate a quantity that equals 10 USDT worth of the asset with 2x leverage.

## Telegram Bot Commands

The bot has been updated to support the new quantity calculation methods and leverage settings via the Telegram interface.

### Using the /settings Command

The `/settings` command now accepts 6 parameters in CSV format:
```
candle_interval,symbol,quantity_spec,buy_long_offset,sell_long_offset,leverage
```

Where:
- `candle_interval`: Candlestick interval (e.g., "1m", "5m", "1h")
- `symbol`: Trading pair symbol (e.g., "BTCUSDT")
- `quantity_spec`: Quantity specification with type indicator:
  - Fixed quantity: Just the number (e.g., "0.01")
  - Percentage: Number with % (e.g., "5%")
  - Price-based: Number with $ (e.g., "10$")
- `buy_long_offset`: Buy order offset
- `sell_long_offset`: Sell order offset
- `leverage`: Trading leverage (e.g., "3" for 3x leverage)

### Examples

1. **Fixed Quantity**: `1m,BTCUSDT,0.01,10,10,1`
2. **Percentage-Based**: `1m,BTCUSDT,5%,10,10,3`
3. **Price-Based**: `1m,BTCUSDT,10$,10,10,5`

### Checking Current Settings

Use the `/status` command to view your current trading configuration, including the quantity type, amount, and leverage settings.

## Note

- The quantity calculation respects the precision requirements of the asset
- Higher leverage increases risk - be careful when using high leverage values
- When using price-based quantity, the bot will always try to use the exact USDT amount specified
