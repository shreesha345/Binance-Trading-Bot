## Binance Trading Bot

This bot is an automated trading system for Binance Futures, written in Python. It connects to Binance via API and can operate in both testnet and live modes. The bot implements a strategy using Heikin Ashi candles and listens to live kline (OHLC) data via Binance WebSocket.

### Key Features

- **Automated Long/Short Orders**: Places and manages long and short futures orders automatically, using a configurable quantity.
- **Heikin Ashi Strategy**: Uses Heikin Ashi candles to calculate buy/sell signals, entering trades at HA_High + offset (for buys) and exiting/stop loss at HA_Low - offset (for sells).
- **Stateful Order Management**: Tracks open and filled orders, manages position state (NONE, LONG, SHORT, etc.), and logs filled order details.
- **Balance Checking**: Can check and display your futures account balance and trading status (live or test mode).
- **Tick Size Management**: Rounds prices to valid Binance tick sizes to prevent order rejection.
- **Resilient WebSocket Listener**: Handles automatic reconnections to Binance WebSocket for continuous data streaming.
- **Order Book Logging**: Saves order execution details for record-keeping and performance analysis.
- **Environment-Based Configuration**: API keys, trade quantity, and mode (test/live) are loaded from environment variables for security and flexibility.

### How It Works

1. **Connects to Binance** (testnet or mainnet, based on configuration).
2. **Listens to kline (candlestick) data** for a configured symbol and interval.
3. **Places buy orders** at HA_High + offset and **sell/stop orders** at HA_Low - offset at the start of each candle.
4. **Manages open orders** (cancels, updates, or waits for fill as needed).
5. **Tracks trading state** (active position, filled prices, order status).
6. **Logs results** to order_book.json for reference.
