# Binance Trading Bot

This bot is an automated trading system for Binance Futures, written in Python. It connects to Binance via API and can operate in both testnet and live modes. The bot implements a strategy using Heikin Ashi candles and listens to live kline (OHLC) data via Binance WebSocket.

## Key Features

- **Automated Long/Short Orders**: Places and manages long and short futures orders automatically, using either a fixed quantity or percentage of available balance.
- **Percentage-Based Trading**: Option to trade with a percentage of your available balance instead of a fixed quantity, providing better risk management.
- **Heikin Ashi Strategy**: Uses Heikin Ashi candles to calculate buy/sell signals, entering trades at HA_High + offset (for buys) and exiting/stop loss at HA_Low - offset (for sells).
- **Stateful Order Management**: Tracks open and filled orders, manages position state (NONE, LONG, SHORT, etc.), and logs filled order details.
- **Balance Checking**: Can check and display your futures account balance and trading status (live or test mode).
- **Tick Size Management**: Rounds prices to valid Binance tick sizes to prevent order rejection.
- **Resilient WebSocket Listener**: Handles automatic reconnections to Binance WebSocket for continuous data streaming.
- **Order Book Logging**: Saves order execution details for record-keeping and performance analysis.
- **Environment-Based Configuration**: API keys, trade quantity, and mode (test/live) are loaded from environment variables for security and flexibility.
- **Telegram Bot Integration**: Includes a Telegram bot with payment integration via Razorpay for subscription-based access.

## Trading Strategy: Detailed Explanation

The bot implements a trading strategy based on Heikin Ashi (HA) candles, which are a modified form of traditional Japanese candlesticks designed to filter market noise and highlight trends.

### Heikin Ashi Calculation

Heikin Ashi candles are calculated as follows:

- **HA Close** = (Open + High + Low + Close) / 4
- **HA Open** = (Previous HA Open + Previous HA Close) / 2
- **HA High** = Max(High, HA Open, HA Close)
- **HA Low** = Min(Low, HA Open, HA Close)

For the first candle, regular Open is used as HA Open.

### Entry Strategy (Buy Signal)

The bot enters a long position when the price crosses above a threshold determined by:

- **Buy Price** = Current candle's HA_High + BUY_OFFSET
- **Stop Limit** = Current candle's HA_High

This creates a stop-limit order that triggers when the price rises above the HA_High of the current candle plus the configured offset. The order becomes a limit order at the HA_High price, ensuring the entry is at a reasonable price point.

This strategy aims to catch upward breakouts when price momentum is strong enough to break above the Heikin Ashi high.

### Exit Strategy (Stop Loss)

Once in a position, the bot places a stop-loss order at:

- **Sell Price** = Current candle's HA_Low - SELL_OFFSET
- **Stop Limit** = Current candle's HA_Low - SELL_OFFSET

The stop-loss is updated with each new candle, allowing it to trail upward as the price moves favorably but preventing it from moving down if the price retraces.

### Order Management Logic

1. **At Each New Candle:**
   - If no position exists, the bot cancels any unfilled buy orders from previous candles
   - It places a new buy order based on the current candle's HA_High + BUY_OFFSET
   - If a position exists, it updates the stop-loss order to the current candle's HA_Low - SELL_OFFSET

2. **Position Tracking:**
   - The bot maintains a state machine tracking position states: NONE, LONG, CLOSED_LONG
   - When a buy order is filled, state changes to LONG
   - When a sell/stop order is filled, state changes to CLOSED_LONG for one candle, then reverts to NONE

3. **Tick Size Management:**
   - All prices are adjusted to match Binance's tick size requirements using `math.floor(price / tick_size) * tick_size`
   - This prevents order rejection due to invalid price levels

4. **Partially Filled Orders:**
   - The bot handles partially filled orders by waiting for them to complete
   - If an order remains partially filled after multiple check attempts, the bot manages the filled portion

5. **Position Verification:**
   - Periodically verifies with Binance that the tracked position matches the actual exchange position
   - If discrepancies are found, the bot reconciles its state with the exchange

### Risk Management

1. **Quantity Control:**
   - Trade with either fixed quantity or percentage of account balance
   - Percentage-based trading automatically adjusts position size based on account value

2. **Order Placement Verification:**
   - Before placing stop orders, verifies current market price to avoid "would immediately trigger" errors
   - Implements fallback mechanisms when price checks fail

3. **Error Handling:**
   - Detailed error logging for troubleshooting
   - Robust reconnection logic for WebSocket interruptions

## How It Works

1. **Connects to Binance** (testnet or mainnet, based on configuration).
2. **Listens to kline (candlestick) data** for a configured symbol and interval.
3. **Places buy orders** at HA_High + offset and **sell/stop orders** at HA_Low - offset at the start of each candle.
4. **Manages open orders** (cancels, updates, or waits for fill as needed).
5. **Tracks trading state** (active position, filled prices, order status).
6. **Logs results** to order_book.json for reference.

## Trading Configuration

The bot's trading behavior can be configured in the `api/trading_config.json` file:

- `symbol_name`: The trading pair (e.g., "ETHUSDT")
- `quantity_type`: Trading quantity mode ("fixed" or "percentage")
- `quantity`: Fixed quantity when using fixed mode (e.g., "1" for 1 ETH)
- `quantity_percentage`: Percentage of available balance to use when in percentage mode (e.g., "5" for 5%)
- `sell_long_offset`: Price offset for sell/stop orders (in quote currency units, e.g., "1" for $1 on ETHUSDT)
- `buy_long_offset`: Price offset for buy orders (in quote currency units, e.g., "1" for $1 on ETHUSDT)
- `candle_interval`: Candlestick interval (e.g., "1m", "5m", "15m", "1h", "4h", "1d")

## Environment Configuration

The bot uses environment variables for sensitive configuration:

- `MODE`: Set to "test" or "true" for testnet, "live" or "false" for mainnet
- `BINANCE_API_KEY`: Your Binance API key for mainnet
- `BINANCE_API_SECRET`: Your Binance API secret for mainnet
- `BINANCE_TESTNET_API_KEY`: Your Binance API key for testnet
- `BINANCE_TESTNET_SECRET_KEY`: Your Binance API secret for testnet

## Telegram Bot and Payment Integration

The bot includes a Telegram bot component that allows users to access the trading functionality through Telegram and handles subscription payments via Razorpay.

### Telegram Bot Features

- **User Authentication**: Manages user access based on subscription status
- **Payment Management**: Integrates with Razorpay for subscription payments
- **Command Interface**: Allows users to control the trading bot through Telegram commands
- **Subscription Tracking**: Manages subscription cycles and payment reminders

### Payment System

The payment system uses Razorpay for processing subscription payments with the following components:

1. **Payment Creation**:
   - Generates payment links with detailed breakdowns of costs
   - Includes server costs, messaging costs, and support fees
   - Handles processing fees and taxes transparently

2. **Payment Verification**:
   - Verifies payment status with Razorpay API
   - Updates subscription cycle upon successful payment
   - Manages payment history for tracking

3. **Subscription Management**:
   - Tracks subscription periods with due dates
   - Sends payment reminders when subscriptions are due
   - Enforces service restrictions for overdue accounts

4. **Customer Data Management**:
   - Securely stores customer details for payment processing
   - Supports name, email, and phone number for payment links
   - Provides functions to manage customer information

### Payment Cycle

The subscription system operates on a configurable payment cycle:

1. **Initial Payment**: First payment activates the service
2. **Regular Billing**: Subsequent bills generated on a fixed cycle (default 28 days)
3. **Grace Period**: Short period after due date where service remains active
4. **Service Restriction**: Trading functionality limited if payment is significantly overdue

### File Structure

- `telegram_bot/bot.py`: Main Telegram bot implementation
- `telegram_bot/razerpay.py`: Razorpay payment integration
- `telegram_bot/server_call.py`: Communication with the trading server
- `telegram_bot/payments.json`: Payment amount configuration
- `telegram_bot/payment_cycle.json`: Payment history tracking
- `telegram_bot/payment_links.json`: Generated payment link storage
- `telegram_bot/customer_details.json`: Customer information storage

## Installation and Setup

### Prerequisites

- Python 3.9+
- Binance account with API access
- Razorpay account (for payment processing)
- Telegram Bot Token (for Telegram integration)

### Environment Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/binance-trading-bot.git
   cd binance-trading-bot
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following variables:
   ```
   # Mode: 'test' or 'live'
   MODE=test
   
   # Binance API keys
   BINANCE_API_KEY=your_mainnet_api_key
   BINANCE_API_SECRET=your_mainnet_api_secret
   BINANCE_TESTNET_API_KEY=your_testnet_api_key
   BINANCE_TESTNET_SECRET_KEY=your_testnet_api_secret
   
   # Razorpay API keys (if using payment system)
   RAZORPAY_API_KEY=your_razorpay_live_key
   RAZORPAY_API_SECRET=your_razorpay_live_secret
   RAZORPAY_TEST_API_KEY=your_razorpay_test_key
   RAZORPAY_TEST_API_SECRET=your_razorpay_test_secret
   
   # Telegram Bot (if using Telegram integration)
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

### Running the Bot

1. Start the main trading bot:
   ```
   python main.py
   ```

2. Start the Telegram bot (if using):
   ```
   python telegram_bot/bot.py
   ```

You can also use Docker to run the bot with the provided Dockerfile and docker-compose.yml.
