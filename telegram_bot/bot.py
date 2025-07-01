from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
from dotenv import load_dotenv
import asyncio
import threading
import time
from typing import Dict, Any
import logging
import tempfile
import re
import json
from datetime import datetime

# Create a dedicated logger for chat messages
chat_logger = logging.getLogger('chat_messages')
chat_logger.setLevel(logging.INFO)

# No need to create logs directory since we're storing everything in telegram_bot folder

# No need to explicitly create telegram_bot directory since we're already in it
# and using os.path.dirname(__file__) for the file path

# Create a file handler for the chat log
chat_log_file = os.path.join(os.path.dirname(__file__), 'telegram_chat.log')
chat_file_handler = logging.FileHandler(chat_log_file)
chat_file_handler.setLevel(logging.INFO)

# Create a formatter for the chat logs
chat_formatter = logging.Formatter('%(asctime)s - %(message)s')
chat_file_handler.setFormatter(chat_formatter)

# Add the handler to the logger
chat_logger.addHandler(chat_file_handler)

def log_message(message_type, chat_id, username, chat_type, message_text):
    """Log sent and received messages to a dedicated log file and JSON storage"""
    try:
        # Create timestamp with date and time
        timestamp = datetime.now().isoformat()
        
        # Prepare log entry
        log_data = {
            "timestamp": timestamp,
            "date": timestamp.split("T")[0],
            "time": timestamp.split("T")[1].split(".")[0],
            "type": message_type,  # "RECEIVED" or "SENT"
            "chat_id": chat_id,
            "username": username,
            "chat_type": chat_type,  # "private", "group", "supergroup", etc.
            "message": message_text
        }
        
        # Log to regular log file
        chat_logger.info(json.dumps(log_data))
        
        # Also store in JSON file
        json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')  # Store in telegram_bot folder
        
        # Load existing messages or create new structure
        try:
            if os.path.exists(json_log_file) and os.path.getsize(json_log_file) > 0:
                with open(json_log_file, 'r', encoding='utf-8') as f:
                    chat_history = json.load(f)
            else:
                chat_history = {"messages": []}
        except json.JSONDecodeError:
            # If the file is corrupted, start fresh
            chat_history = {"messages": []}
            
        # Add new message to history
        chat_history["messages"].append(log_data)
        
        # Save updated history
        with open(json_log_file, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, indent=2, ensure_ascii=False)
            
        print(f"✅ Logged {message_type} message for chat_id: {chat_id}")
    except Exception as e:
        print(f"❌ Error logging message: {e}")

try:
    # Import the interface to communicate with the main trading bot
    # This maintains separation between telegram_bot and trading functionality
    import server_call
    SERVER_CALL_AVAILABLE = True
    print("✅ server_call module imported successfully")
except ImportError as e:
    print(f"❌ Failed to import server_call: {e}")
    SERVER_CALL_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram bot token (set this as environment variable)
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    print("❌ Warning: TELEGRAM_BOT_TOKEN not found. Please set it in your environment variables")

# In-memory notification state
notify_users: Dict[int, Dict[str, Any]] = {}

def format_filled_order(order):
    """Format filled order for /notify as per requirements"""
    meta = order.get('meta', {})
    order_type = meta.get('order_type', order.get('side', 'N/A')).upper()
    filled_price = meta.get('filled_price', order.get('avgPrice', order.get('price', 'N/A')))
    symbol = order.get('symbol', meta.get('symbol', 'N/A'))
    quantity = order.get('origQty', order.get('executedQty', 'N/A'))
    orig_type = order.get('origType', 'N/A')
    stop_price = order.get('stopPrice', 'N/A')
    position_side = meta.get('position_side', order.get('positionSide', 'N/A'))
    recorded_at = meta.get('recorded_at', order.get('saved_at', order.get('updateTime', 'N/A')))

    # Color and emoji for order type
    if order_type == 'SELL':
        type_emoji = '🔴'
    elif order_type == 'BUY':
        type_emoji = '🟢'
    else:
        type_emoji = '⚪️'

    # Format recorded_at as readable date/time if possible
    try:
        from datetime import datetime
        if recorded_at and isinstance(recorded_at, str) and 'T' in recorded_at:
            dt = datetime.fromisoformat(recorded_at)
            recorded_at_fmt = dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            recorded_at_fmt = str(recorded_at)
    except Exception:
        recorded_at_fmt = str(recorded_at)

    return (
        f"{type_emoji} *Order Filled*\n"
        f"*Symbol:* {symbol}\n"
        f"*Type:* {order_type}\n"
        f"*Position:* {position_side}\n"
        f"*Filled Price:* {filled_price}\n"
        f"*Quantity:* {quantity}\n"
        f"*Order Type:* {orig_type}\n"
        f"*Stop Price:* {stop_price}\n"
        f"*Time:* {recorded_at_fmt}"
    )

async def send_telegram_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message: str):
    """Helper function to send Telegram messages with proper error handling"""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='Markdown',
            read_timeout=30,
            write_timeout=30,
            connect_timeout=30
        )
        print(f"✅ Message sent successfully to chat_id: {chat_id}")
        log_message("SENT", chat_id, "", "private", message)  # Log sent message
        return True
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        # Try sending without markdown as fallback
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=None,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30
            )
            print(f"✅ Fallback message sent to chat_id: {chat_id}")
            log_message("SENT", chat_id, "", "private", message)  # Log sent message
            return True
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")
            return False

def poll_filled_orders_sync(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Synchronous function to poll filled orders (runs in thread)"""
    last_order_id = None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while notify_users.get(chat_id, {}).get("notifying", False):
        try:
            if not SERVER_CALL_AVAILABLE:
                print("❌ server_call not available, stopping notifications")
                break
                
            # Use the live update endpoint for the latest order
            data = server_call.get_current_order_book()
            filled_orders = data.get("filled_orders", [])
            if filled_orders:
                # Always get only the latest (most recent) order
                latest = max(filled_orders, key=lambda o: (
                    o.get("orderId") or 0,
                    o.get("saved_at") or o.get("updateTime") or 0
                ))
                # Use a robust unique order_id string
                meta = latest.get("meta", {})
                order_id = str(latest.get("orderId") or latest.get("saved_at") or meta.get("recorded_at") or "")
                print(f"[Notify] Checking order_id: {order_id}, last_order_id: {last_order_id}")
                if order_id and order_id != last_order_id:
                    last_order_id = order_id
                    msg = format_filled_order(latest)
                    print(f"[Notify] Sending notification for order_id: {order_id}")
                    loop.run_until_complete(
                        send_telegram_message(context, chat_id, msg)
                    )
            time.sleep(10)
        except Exception as e:
            print(f"❌ Notify error: {e}")
            time.sleep(10)
    
    loop.close()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - same as help"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/start")
    
    help_message = (
        "🎉 *Welcome to Trading Bot!*\n\n"
        "🤖 *Trading Commands:*\n"
        "🚀 /start\\_bot - Start trading\n"
        "🛑 /stop\\_bot - Stop trading\n"
        "📊 /status - Check bot status\n"
        "⚙️ /settings - Update config\n\n"
        "🔔 *Notifications:*\n"
        "🔔 /notify - Enable notifications\n"
        "🔕 /stop\\_notify - Disable notifications\n\n"
        " /total\\_messages - View message stats\n\n"
        "📝 *Settings Format:*\n"
        "`interval,symbol,quantity,buy_offset,sell_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`\n\n"
        "❓ /help - Full command list"
    )
    
    try:
        await update.message.reply_text(help_message, parse_mode='Markdown')
        print(f"✅ /start command sent successfully to {update.effective_chat.id}")
        log_message("SENT", update.effective_chat.id, "", "private", help_message)  # Log sent message
    except Exception as e:
        print(f"❌ Error sending /start response: {e}")
        # Fallback to plain text
        try:
            await update.message.reply_text("🎉 Welcome! Use /help for commands.", parse_mode=None)
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - complete command list"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/help")
    
    help_message = (
        "📖 *Complete Command List:*\n\n"
        "🤖 *Trading:*\n"
        "🚀 /start\\_bot - Start the trading bot\n"
        "🛑 /stop\\_bot - Stop the trading bot\n"
        "📊 /status - Check current bot status\n"
        "⚙️ /settings - Update trading configuration\n\n"
        "🔔 *Notifications:*\n"
        "🔔 /notify - Enable order fill notifications\n"
        "🔕 /stop\\_notify - Disable notifications\n\n"
        "� *Message Statistics:*\n"
        "📊 /total\\_messages - View message count statistics\n\n"
        "📝 *Settings Format:*\n"
        "`candle_interval,symbol,quantity,buy_offset,sell_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`"
    )
    
    try:
        await update.message.reply_text(help_message, parse_mode='Markdown')
        print(f"✅ /help command sent successfully to {update.effective_chat.id}")
        log_message("SENT", update.effective_chat.id, "", "private", help_message)  # Log sent message
    except Exception as e:
        print(f"❌ Error sending /help response: {e}")
        # Fallback to plain text
        try:
            await update.message.reply_text("📖 Commands: /start_bot, /stop_bot, /status, /settings, /notify", parse_mode=None)
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")

async def start_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start_bot command"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/start_bot")
    
    if not SERVER_CALL_AVAILABLE:
        response_message = "❌ Trading bot service is not available. Please check server connection."
    else:
        try:
            result = server_call.control_bot_start()
            response_message = f"🚀 *Bot Started Successfully*\nStatus: {result.get('status', 'Started')}"
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            response_message = f"❌ Error starting bot: {str(e)}"
    
    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)  # Log sent message

async def stop_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop_bot command"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/stop_bot")
    
    if not SERVER_CALL_AVAILABLE:
        response_message = "❌ Trading bot service is not available. Please check server connection."
    else:
        try:
            result = server_call.control_bot_stop()
            response_message = f"🛑 *Bot Stopped Successfully*\nStatus: {result.get('status', 'Stopped')}"
        except Exception as e:
            print(f"❌ Error stopping bot: {e}")
            response_message = f"❌ Error stopping bot: {str(e)}"
    # Stop notifications for this user as well
    if notify_users.get(chat_id, {}).get("notifying", False):
        notify_users[chat_id]["notifying"] = False
    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)  # Log sent message

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/status")
    
    if not SERVER_CALL_AVAILABLE:
        response_message = "❌ Trading bot service is not available. Please check server connection."
    else:
        try:
            result = server_call.get_bot_status()
            is_running = result.get('running', False)
            status_emoji = "🟢" if is_running else "🔴"
            response_message = f"{status_emoji} *Bot Status*\nRunning: {'Yes' if is_running else 'No'}"
        except Exception as e:
            print(f"❌ Error getting bot status: {e}")
            response_message = f"❌ Error getting bot status: {str(e)}"
    
    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)  # Log sent message

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/settings")

    response_message = (
        "⚙️ *Trading Settings Configuration*\n\n"
        "Please send your settings in the following format:\n"
        "`candle_interval,symbol,quantity,buy_long_offset,sell_long_offset`\n\n"
        "📝 Example:\n"
        "`1m,BTCUSDT,0.01,10,10`\n\n"
        "Where:\n"
        "• Candle Interval: e.g., 1m, 5m, 1h\n"
        "• Symbol: Trading pair (e.g., BTCUSDT)\n"
        "• Quantity: Trade amount\n"
        "• Buy offset: Price offset for buy orders\n"
        "• Sell offset: Price offset for sell orders"
    )

    # Initialize user state if not exists
    if chat_id not in notify_users:
        notify_users[chat_id] = {}
    notify_users[chat_id]["awaiting_settings"] = True

    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)  # Log sent message

async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /notify command"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/notify")
    
    if not SERVER_CALL_AVAILABLE:
        response_message = "❌ Trading bot service is not available. Notifications cannot be enabled."
    else:
        # Initialize user state if not exists
        if chat_id not in notify_users:
            notify_users[chat_id] = {}
            
        if not notify_users[chat_id].get("notifying", False):
            notify_users[chat_id]["notifying"] = True
            t = threading.Thread(
                target=poll_filled_orders_sync, 
                args=(chat_id, context), 
                daemon=True
            )
            t.start()
            response_message = "🔔 *Notifications Enabled*\nYou will now receive filled order notifications every 10 seconds."
        else:
            response_message = "🔔 *Already Enabled*\nNotifications are already active for your account."
    
    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)  # Log sent message

async def stop_notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop_notify command"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/stop_notify")
    
    if notify_users.get(chat_id, {}).get("notifying", False):
        notify_users[chat_id]["notifying"] = False
        response_message = "🔕 *Notifications Disabled*\nYou will no longer receive filled order notifications."
    else:
        response_message = "🔕 *Already Disabled*\nNotifications were not enabled for your account."
    
    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)  # Log sent message

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle non-command messages"""
    chat_id = update.effective_chat.id
    message_text = update.message.text.strip()

    print(f"📥 Received message: '{message_text}' from chat_id: {chat_id}")
    log_message("RECEIVED", chat_id, update.message.from_user.username, "private", message_text)  # Log received message

    # Check if user is awaiting settings input
    if notify_users.get(chat_id, {}).get("awaiting_settings", False):
        if not SERVER_CALL_AVAILABLE:
            response_message = "❌ Trading bot service is not available. Please check server connection."
            notify_users[chat_id]["awaiting_settings"] = False
        else:
            try:
                parts = [x.strip() for x in message_text.split(",")]
                if len(parts) != 5:
                    raise ValueError("Please provide exactly 5 values: candle_interval,symbol,quantity,buy_long_offset,sell_long_offset")

                candle_interval, symbol, quantity, buy_long_offset, sell_long_offset = parts

                # Use update_trading_config to add the data
                result = server_call.update_trading_config(
                    candle_interval=candle_interval,
                    symbol_name=symbol,
                    quantity=quantity,
                    buy_long_offset=buy_long_offset,
                    sell_long_offset=sell_long_offset
                )

                response_message = (
                    f"✅ *Settings Updated Successfully*\n\n"
                    f"*Candle Interval:* {candle_interval}\n"
                    f"*Symbol:* {symbol}\n"
                    f"*Quantity:* {quantity}\n"
                    f"*Buy Offset:* {buy_long_offset}\n"
                    f"*Sell Offset:* {sell_long_offset}\n\n"
                )
                notify_users[chat_id]["awaiting_settings"] = False

            except ValueError as ve:
                response_message = (
                    f"❌ *Invalid Format*\n{str(ve)}\n\n"
                    "Please try again with: candle_interval,symbol,quantity,buy_long_offset,sell_long_offset"
                )
            except Exception as e:
                print(f"❌ Error updating settings: {e}")
                response_message = f"❌ Error updating settings: {str(e)}"

        await update.message.reply_text(response_message, parse_mode='Markdown')
        return

    # Check if the message is a greeting
    greetings = ['hi', 'hello', 'hey', 'hola', 'namaste']
    if message_text.lower() in greetings:
        await start_command(update, context)
        return
    
    # Handle other messages
    response_message = (
        "👋 I didn't understand that message.\n\n"
        "Try using:\n"
        "• 'hi' or 'hello' for welcome message\n"
        "• /help for all available commands\n"
        "• /start\\_bot to begin trading\n"
        "• /status to check bot status"
    )
    
    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)  # Log sent message

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.warning(f'Update {update} caused error {context.error}')

async def total_messages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /total_messages command to show message counts"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/total_messages")
    
    # Read message history directly from JSON file
    try:
        json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')  # Read from telegram_bot folder
        
        if not os.path.exists(json_log_file) or os.path.getsize(json_log_file) == 0:
            messages = []
        else:
            with open(json_log_file, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
                messages = chat_history.get("messages", [])
                
            # Filter by chat_id
            messages = [msg for msg in messages if str(msg.get("chat_id")) == str(chat_id)]
    except Exception as e:
        print(f"❌ Error retrieving chat history: {e}")
        messages = []
    
    # Count messages
    total_messages = len(messages)
    total_sent = sum(1 for msg in messages if msg.get("type") == "SENT")
    total_received = sum(1 for msg in messages if msg.get("type") == "RECEIVED")
    
    # Get date of first and last message
    first_message_date = "N/A"
    last_message_date = "N/A"
    
    if messages:
        try:
            first_msg = messages[0]
            first_message_date = f"{first_msg.get('date', 'N/A')} {first_msg.get('time', '')}"
            
            last_msg = messages[-1]
            last_message_date = f"{last_msg.get('date', 'N/A')} {last_msg.get('time', '')}"
        except (IndexError, KeyError):
            pass
    
    response_message = (
        "📊 *Message Statistics Summary*\n\n"
        f"*Total Messages:* {total_messages}\n"
        f"*Messages Sent:* {total_sent}\n"
        f"*Messages Received:* {total_received}\n\n"
        f"*First Message:* {first_message_date}\n"
        f"*Latest Message:* {last_message_date}"
    )
    
    await update.message.reply_text(response_message, parse_mode='Markdown')
    log_message("SENT", update.effective_chat.id, "", "private", response_message)

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    
    print("=" * 50)
    print("🚀 Starting Telegram Trading Bot")
    print("=" * 50)
    print(f"🤖 Bot Token: {'✅ Set' if BOT_TOKEN else '❌ Missing'}")
    print(f"🔧 Server Call: {'✅ Available' if SERVER_CALL_AVAILABLE else '❌ Not Available'}")
    print("=" * 50)
    print("💡 All files and logs are stored in telegram_bot folder")
    print("💡 This bot communicates with the trading bot via the server_call interface")
    print("=" * 50)
    print("💡 Available Commands:")
    print("   /start, /help, /start_bot, /stop_bot, /status")
    print("   /settings, /notify, /stop_notify, /total_messages")
    print("=" * 50)
    
    # Create the Application with timeouts
    application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start_bot", start_bot_command))
    application.add_handler(CommandHandler("stop_bot", stop_bot_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("notify", notify_command))
    application.add_handler(CommandHandler("stop_notify", stop_notify_command))
    application.add_handler(CommandHandler("total_messages", total_messages_command))
    
    # Add message handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    print("🚀 Bot is starting...")
    print("💡 Send /start to begin!")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()