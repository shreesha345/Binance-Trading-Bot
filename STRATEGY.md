# Trading Strategy Documentation

This document provides a detailed explanation of the trading strategy implemented in this Binance Trading Bot.

## Heikin Ashi Strategy Overview

The bot implements a trading strategy based on Heikin Ashi (HA) candles. Heikin Ashi, which means "average bar" in Japanese, is a modified candlestick charting technique designed to filter out market noise and better identify trends.

## Heikin Ashi Calculation

Unlike traditional candlesticks that use open, high, low, and close (OHLC) values directly from the market, Heikin Ashi candles are calculated using the following formulas:

- **HA Close** = (Open + High + Low + Close) / 4
- **HA Open** = (Previous HA Open + Previous HA Close) / 2
- **HA High** = Max(High, HA Open, HA Close)
- **HA Low** = Min(Low, HA Open, HA Close)

For the first candle in a series:
- **HA Open** = Open (uses regular Open price)
- **HA Close** = (Open + High + Low + Close) / 4
- **HA High** = Max(High, HA Open, HA Close)
- **HA Low** = Min(Low, HA Open, HA Close)

The resulting Heikin Ashi candles typically have a smoother appearance than regular candlesticks, making it easier to identify the prevailing trend.

## Strategy Logic

### Entry Criteria (Buy Signal)

The bot enters a long position using a stop-limit order with the following parameters:

- **Stop Price (Trigger)** = Current candle's HA_High + BUY_OFFSET
- **Limit Price** = Current candle's HA_High

This creates an order that:
1. Is triggered when the price rises above the HA_High plus the configured offset
2. Executes as a limit order at the HA_High price

The strategy aims to catch upward breakouts when price momentum is strong enough to break above the Heikin Ashi high. The BUY_OFFSET parameter helps filter out minor price fluctuations above the HA_High by requiring a more substantial breakout before entering a position.

### Exit Criteria (Stop Loss)

Once in a position, the bot places a stop-loss order at:

- **Stop Price (Trigger)** = Current candle's HA_Low - SELL_OFFSET
- **Limit Price** = Current candle's HA_Low - SELL_OFFSET

The stop-loss is updated with each new candle, allowing it to:
1. Trail upward as the price moves favorably
2. Remain fixed if the price retraces (does not move lower)

This approach aims to lock in profits as the price rises while providing a dynamic exit mechanism based on the Heikin Ashi low values.

## Position and Order Management

### Candle-by-Candle Process

For each new candle, the bot performs the following operations:

1. **Calculate new Heikin Ashi values** based on the current candle's OHLC data
2. **Check existing order status:**
   - For unfilled buy orders from previous candles: cancel and create new orders
   - For partially filled orders: monitor until completely filled
   - For filled buy orders: update position state and create stop-loss
3. **Update stop-loss orders** for existing positions based on new HA_Low values
4. **Verify position status** with the exchange to ensure bot state matches reality
5. **Create new orders** for the next candle if conditions are met

### State Machine

The bot uses a state machine to track position status:

- **NONE**: No active position
- **LONG**: In a long position
- **CLOSED_LONG**: Just closed a long position (transitions to NONE after one candle)

This state tracking ensures proper order management and prevents duplicate orders.

### Tick Size Management

To comply with Binance's price precision requirements, all prices are adjusted to match the symbol's tick size:

```python
adjusted_price = math.floor(raw_price / tick_size) * tick_size
```

This prevents order rejection due to invalid price levels and ensures prices are exactly at levels that Binance accepts.

## Risk Management Features

### Position Sizing

The bot supports two methods of determining position size:

1. **Fixed Quantity**: Uses a specific, predefined amount for each trade
   - Configured via the `quantity` parameter in trading_config.json
   - Example: Always trade 0.01 ETH regardless of account size

2. **Percentage-Based**: Calculates position size as a percentage of available balance
   - Configured via the `quantity_percentage` parameter in trading_config.json
   - Example: Trade with 5% of available balance
   - Automatically adjusts position size as account value changes

Percentage-based trading provides better risk management as it:
- Scales position size with account growth/decline
- Maintains consistent risk exposure relative to account size
- Prevents overexposure during drawdowns

### Error Handling and Recovery

The bot implements several safety mechanisms:

1. **Order Verification**: Verifies orders with the exchange after placement
2. **Position Reconciliation**: Periodically checks that the bot's internal state matches the actual exchange position
3. **Multiple Order Status Checks**: For partially filled orders, checks multiple times before taking action
4. **Market Price Verification**: Before placing stop orders, verifies the current market price to avoid "would immediately trigger" errors

## Strategy Parameters and Optimization

The strategy can be fine-tuned using the following parameters:

### Critical Parameters

- **BUY_OFFSET**: How far above the HA_High to place buy stop orders
  - Higher values: More confirmation required, potentially fewer false signals
  - Lower values: Earlier entries, potentially more false signals

- **SELL_OFFSET**: How far below the HA_Low to place stop-loss orders
  - Higher values: More room for price fluctuation, potentially larger losses
  - Lower values: Tighter stops, potentially more premature exits

### Other Parameters

- **CANDLE_INTERVAL**: The timeframe for candles (e.g., "1m", "5m", "15m", "1h")
  - Shorter intervals: More signals, higher trading frequency
  - Longer intervals: Fewer signals, lower trading frequency

- **QUANTITY_TYPE** and related parameters: Control position sizing as described above

## Performance Considerations

The strategy tends to perform well in trending markets but may experience:

1. **Whipsaws in Ranging Markets**: Multiple small losses when price oscillates in a range
2. **Delayed Entries in Strong Trends**: May miss initial moves as it waits for confirmation
3. **Variable Stop Distances**: Stop-loss distance can vary based on Heikin Ashi calculation

## Logs and Monitoring

The strategy logs detailed information about:

1. **Order Placement**: When and why orders are created
2. **Order Status Changes**: Updates on fills, cancellations, etc.
3. **Position Management**: Changes in position state
4. **Error Conditions**: Any issues encountered during execution

These logs are essential for:
- Troubleshooting issues
- Validating strategy performance
- Understanding trade decisions
- Improving the strategy over time

## Implementation Details

The strategy is implemented in the following key files:

- `utils/websocket_client/strategy.py`: Core strategy logic
- `utils/websocket_client/heikin_ashi.py`: Heikin Ashi calculation
- `utils/buy_sell_handler.py`: Order execution functions
- `utils/bot_state.py`: Position and order state tracking
- `utils/config.py`: Configuration loading and management

The implementation carefully handles edge cases like:
- Partially filled orders
- Exchange disconnections
- Invalid price levels
- Order rejection
- Position verification

## Configuration and Customization

Users can customize the strategy by modifying the following:

1. **Trading Configuration** (`api/trading_config.json`):
   - Trading pair selection
   - Position sizing approach
   - Buy and sell offsets
   - Candle interval

2. **Environment Variables**:
   - Test/live mode selection
   - API credentials
   - Other global settings

This allows for significant customization without modifying the core strategy code.
