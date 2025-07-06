# Installation and Configuration Guide

This guide provides detailed instructions for setting up and configuring the Binance Trading Bot.

## System Requirements

- **Operating System**: Linux, Windows, or macOS
- **Python**: Version 3.9 or higher
- **Memory**: Minimum 2GB RAM recommended
- **Storage**: Minimum 1GB free space
- **Network**: Stable internet connection required

## Installation

### Option 1: Standard Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/binance-trading-bot.git
   cd binance-trading-bot
   ```

2. **Create and Activate Virtual Environment**

   **Linux/macOS**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

   **Windows**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Create Environment Configuration**

   Create a `.env` file in the project root directory with the following content:

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

5. **Initialize Order Storage**

   ```bash
   python data/init_order_storage.py
   ```

### Option 2: Docker Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/binance-trading-bot.git
   cd binance-trading-bot
   ```

2. **Create Environment Configuration**

   Create a `.env` file as described in Option 1, Step 4.

3. **Build and Start Docker Containers**

   ```bash
   docker-compose up -d
   ```

   This will build and start both the main trading bot and the Telegram bot (if configured).

## Configuration

### 1. Trading Configuration

Edit the `api/trading_config.json` file to configure trading parameters:

```json
{
    "symbol_name": "ETHUSDT",
    "sell_long_offset": "1",
    "buy_long_offset": "1",
    "quantity": "1",
    "quantity_type": "percentage",
    "quantity_percentage": "5",
    "candle_interval": "1m"
}
```

Parameters explained:

- **symbol_name**: Trading pair to trade (e.g., "ETHUSDT", "BTCUSDT")
- **sell_long_offset**: Price offset for sell/stop orders (in quote currency units)
- **buy_long_offset**: Price offset for buy orders (in quote currency units)
- **quantity_type**: 
  - "fixed": Use a fixed quantity for each trade
  - "percentage": Use a percentage of available balance
- **quantity**: Fixed quantity when using fixed mode (e.g., "1" for 1 ETH)
- **quantity_percentage**: Percentage of available balance to use (e.g., "5" for 5%)
- **candle_interval**: Candlestick interval ("1m", "5m", "15m", "1h", "4h", "1d")

### 2. Binance API Setup

1. **Create Binance Account**

   If you don't have a Binance account, register at [Binance](https://www.binance.com/en/register).

2. **Generate API Keys**

   a. Log in to your Binance account
   b. Navigate to "API Management"
   c. Click "Create API"
   d. Complete the security verification
   e. Set permissions (Enable futures trading, Enable reading, Enable spot & margin trading)
   f. Set restrictions (IP whitelist recommended)
   g. Save the API Key and Secret Key

3. **Generate Testnet API Keys (Recommended for Testing)**

   a. Go to [Binance Futures Testnet](https://testnet.binancefuture.com/)
   b. Register and log in
   c. Generate API Keys following similar steps as above

4. **Update Environment Variables**

   Add your API keys to the `.env` file as shown in the Installation section.

### 3. Telegram Bot Setup (Optional)

1. **Create a Telegram Bot**

   a. Open Telegram and search for "BotFather"
   b. Send the command `/newbot`
   c. Follow the instructions to set a name and username
   d. Save the token provided by BotFather

2. **Update Environment Variables**

   Add your Telegram Bot Token to the `.env` file:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

3. **Configure Bot Permissions** (optional)

   You can configure which Telegram users can access your bot by editing the Telegram bot code. By default, the bot may allow access to anyone who knows the bot's username.

### 4. Razorpay Setup (Optional, for Payment Integration)

1. **Create Razorpay Account**

   Register for a Razorpay account at [Razorpay](https://razorpay.com/).

2. **Generate API Keys**

   a. Log in to your Razorpay Dashboard
   b. Go to Settings > API Keys
   c. Generate a key pair for both live and test modes

3. **Update Environment Variables**

   Add your Razorpay API keys to the `.env` file:
   ```
   RAZORPAY_API_KEY=your_razorpay_live_key
   RAZORPAY_API_SECRET=your_razorpay_live_secret
   RAZORPAY_TEST_API_KEY=your_razorpay_test_key
   RAZORPAY_TEST_API_SECRET=your_razorpay_test_secret
   ```

4. **Configure Payment Settings**

   Edit the `telegram_bot/payments.json` file to set your pricing structure:

   ```json
   {
     "server_cost": 4000,
     "per_message_cost": 1,
     "message_monthly_cost": 0,
     "support_cost": 2000,
     "payment_cycle_days": 28
   }
   ```

## Running the Bot

### Running the Main Trading Bot

```bash
# Standard installation
python main.py

# Or from Docker (if already built with docker-compose)
docker-compose up -d trading-bot
```

### Running the Telegram Bot (Optional)

```bash
# Standard installation
python telegram_bot/bot.py

# Or from Docker (if already built with docker-compose)
docker-compose up -d telegram-bot
```

## Monitoring and Logging

The bot generates several log files:

- **api.log**: API interaction logs
- **errors.log**: Error logs
- **websocket.log**: WebSocket connection and data logs
- **telegram_chat.log**: Telegram bot interaction logs

You can monitor these logs to track the bot's operation:

```bash
# View trading bot logs
tail -f logs/websocket.log

# View error logs
tail -f logs/errors.log

# View Telegram bot logs
tail -f telegram_bot/telegram_chat.log
```

## Troubleshooting

### Common Issues

1. **Connection Issues with Binance API**

   - Check internet connection
   - Verify API keys are correct
   - Ensure IP restrictions (if set) include your server IP
   - Check Binance system status for outages

2. **Order Placement Failures**

   - Check account balance
   - Verify minimum order quantity requirements for the symbol
   - Check for invalid price (outside allowed price range)
   - Look for specific error messages in logs

3. **Telegram Bot Connection Issues**

   - Verify bot token is correct
   - Check internet connection
   - Ensure bot hasn't been blocked by Telegram

4. **Payment Processing Issues**

   - Verify Razorpay API keys
   - Check for timeouts in API calls
   - Verify customer information format

### Getting Help

For additional help:

1. Check the error logs for specific error messages
2. Refer to the Binance API documentation for error codes
3. Search for similar issues in the project's issue tracker
4. Contact the developer through the project's support channels

## Security Recommendations

1. **API Key Security**
   - Never share your API keys
   - Use IP restrictions on your Binance API keys
   - Set the minimum required permissions for your API keys
   - Regularly rotate your API keys

2. **Server Security**
   - Keep your server and software updated
   - Use a firewall to restrict access
   - Implement proper authentication for accessing the server
   - Back up configuration files regularly

3. **Environment Variables**
   - Protect your `.env` file from unauthorized access
   - Don't commit the `.env` file to public repositories
   - Use proper file permissions (chmod 600 .env on Linux/Mac)

4. **Financial Safety**
   - Start with small trade amounts during testing
   - Regularly monitor the bot's activities
   - Set up alerts for unusual activity
   - Have a plan for emergency shutdown

## Maintenance and Updates

1. **Regular Updates**
   - Periodically check for updates to the bot
   - Update dependencies to patch security vulnerabilities
   - Test updates in a staging environment before production

2. **Data Maintenance**
   - Periodically back up order history
   - Clean up old logs to prevent disk space issues
   - Monitor database growth (if applicable)

3. **Performance Optimization**
   - Adjust candle interval based on trading frequency needs
   - Monitor memory and CPU usage
   - Consider server upgrades if performance degrades

## Conclusion

This installation guide should help you set up and configure the Binance Trading Bot successfully. Remember to start with small trade amounts and in testnet mode until you're comfortable with the bot's operation and have verified its performance.

For strategy details, refer to the STRATEGY.md file, and for Telegram bot and payment integration details, refer to the TELEGRAM_PAYMENT.md file.
