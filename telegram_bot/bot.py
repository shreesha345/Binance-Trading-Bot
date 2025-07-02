from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta, timezone
import pytz
from dotenv import load_dotenv
from typing import Dict, Any
import threading
import logging
import asyncio
import tempfile    
import time
import json
import os
import random
import string

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
        "📊 *Statistics & Info:*\n"
        "📊 /total\\_messages - View message count statistics\n"
        "💰 /payments - View payment details\n"
        "💳 /payment\\_made - Record a completed payment\n"
        "❌ /cancel\\_payment - Cancel an ongoing payment process\n\n"
        "📝 *Settings Format:*\n"
        "`candle_interval,symbol,quantity,buy_offset,sell_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`\n\n"
        "⚠️ *Payment System:*\n"
        "• Payment is due on the specified due date\n"
        "• You have 1 extra day after the due date to make payment\n" 
        "• If payment is not made, only /help, /payments, /payment\\_made, /total\\_messages, and /cancel\\_payment will work\n"
        "• All other commands will be blocked until payment is made"
    )

# Create a dedicated logger for chat messages
chat_logger = logging.getLogger('chat_messages')
chat_logger.setLevel(logging.INFO)

# No need to create logs directory since we're storing everything in telegram_bot folder

# No need to explicitly create telegram_bot directory as it already exists
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
        "📊 /total\\_messages - View message stats\n"
        "💰 /payments - View payment details\n"
        "💳 /payment\\_made - Record a payment\n"
        "❌ /cancel\\_payment - Cancel payment process\n\n"
        "📝 *Settings Format:*\n"
        "`interval,symbol,quantity,buy_long_offset,sell_long_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`\n\n"
        "⚠️ *Payment System:*\n"
        "• Payment is due on the specified due date\n"
        "• You have 1 extra day after due date to pay\n" 
        "• If payment is overdue, most commands are blocked\n\n"
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
        "📊 *Statistics & Info:*\n"
        "📊 /total\\_messages - View message count statistics\n"
        "💰 /payments - View payment details\n"
        "💳 /payment\\_made - Record a completed payment\n"
        "❌ /cancel\\_payment - Cancel an ongoing payment process\n\n"
        "📝 *Settings Format:*\n"
        "`candle_interval,symbol,quantity,buy_long_offset,sell_long_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`\n\n"
        "⚠️ *Payment System:*\n"
        "• Payment is due on the specified due date\n"
        "• You have 1 extra day after the due date to make payment\n" 
        "• If payment is not made, only /help, /payments, /payment\\_made, /total\\_messages, and /cancel\\_payment will work\n"
        "• All other commands will be blocked until payment is made"
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

async def payments_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /payments command to show payment details with message usage"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/payments")
    
    # Read payment details from JSON file
    try:
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        
        if not os.path.exists(payments_file) or os.path.getsize(payments_file) == 0:
            response_message = "❌ Payment information is not available."
        else:
            with open(payments_file, 'r', encoding='utf-8') as f:
                payment_data = json.load(f)
                
            # Extract payment details
            server_cost = payment_data.get("server_cost", 0)
            server_commission = payment_data.get("server_commission", 0)
            per_message_cost = payment_data.get("per_message_cost", 1)  # Read from payments.json
            message_monthly_cost = payment_data.get("message_monthly_cost", 0)
            support_cost = payment_data.get("support_cost", 0)
            
            # Calculate total server cost (including commission)
            total_server_cost = server_cost + server_commission
            
            # Calculate message statistics for the current cycle
            json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')
            
            # Load payment cycle information
            payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
            
            try:
                if os.path.exists(payment_cycle_file) and os.path.getsize(payment_cycle_file) > 0:
                    with open(payment_cycle_file, 'r', encoding='utf-8') as f:
                        payment_cycle = json.load(f)
                    
                    # Extract payment dates - support both legacy and new format
                    last_payment_date_str = payment_cycle.get("last_payment_date", "")
                    
                    # Get next bill date and due date, handling both old and new formats
                    next_bill_date_str = payment_cycle.get("next_bill_date", payment_cycle.get("next_payment_date", ""))
                    due_date_str = payment_cycle.get("due_date", "")
                    
                    # Get payment cycle days
                    payment_cycle_days = payment_cycle.get("payment_cycle_days", 28)
                    
                    # Parse dates using IST timezone
                    if last_payment_date_str:
                        last_payment_date = string_to_ist(last_payment_date_str)
                    else:
                        last_payment_date = get_ist_now() - timedelta(days=payment_cycle_days)
                    
                    # If due_date is provided, use it, otherwise calculate it
                    if due_date_str:
                        due_date = string_to_ist(due_date_str)
                    elif next_bill_date_str:
                        next_bill_date = string_to_ist(next_bill_date_str)
                        due_date = next_bill_date - timedelta(days=1)
                    else:
                        due_date = calculate_due_date(last_payment_date, payment_cycle_days)
                else:
                    # Default to last 28 days if file doesn't exist
                    payment_cycle_days = payment_data.get("payment_cycle_days", 28)
                    last_payment_date = get_ist_now() - timedelta(days=payment_cycle_days)
                    due_date = calculate_due_date(last_payment_date, payment_cycle_days)
            except Exception as e:
                print(f"❌ Error loading payment cycle: {e}")
                # Default to last 28 days if there was an error
                payment_cycle_days = payment_data.get("payment_cycle_days", 28)
                last_payment_date = get_ist_now() - timedelta(days=payment_cycle_days)
                due_date = calculate_due_date(last_payment_date, payment_cycle_days)
            
            # Get current date for comparison (in IST)
            current_date = get_ist_now()
            
            # Calculate days remaining until due date
            days_remaining = (due_date - current_date).days
            days_remaining = max(0, days_remaining)  # Ensure non-negative
            
            # Get detailed payment status
            is_overdue, status_message = get_payment_status_info()
            
            # Get total message count in the current cycle
            messages_in_cycle = 0
            if os.path.exists(json_log_file) and os.path.getsize(json_log_file) > 0:
                with open(json_log_file, 'r', encoding='utf-8') as f:
                    chat_history = json.load(f)
                    all_messages = chat_history.get("messages", [])
                    
                    # Count messages in the current cycle up to (but not including) due date
                    for msg in all_messages:
                        try:
                            msg_timestamp = string_to_ist(msg.get("timestamp", ""))
                            
                            # Include messages between last payment and due date (excluding due date)
                            if msg_timestamp >= last_payment_date:
                                # Reset time components to compare only dates
                                msg_date = msg_timestamp.replace(hour=0, minute=0, second=0, microsecond=0).date()
                                due_date_only = due_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
                                
                                if msg_date < due_date_only:
                                    messages_in_cycle += 1
                        except (ValueError, TypeError) as e:
                            print(f"❌ Error processing message timestamp: {e}")
                            continue
            
            # Calculate message cost examples
            messages_for_1_rupee = int(1 / per_message_cost) if per_message_cost > 0 else 0
            messages_for_2_rupees = int(2 / per_message_cost) if per_message_cost > 0 else 0
            
            # Calculate current cost based on message usage
            current_message_cost = messages_in_cycle * per_message_cost
            
            # Update message_monthly_cost based on the current billing cycle messages
            message_monthly_cost = current_message_cost  # Use the actual message cost for this cycle
            
            # Format payment dates for display
            last_payment_display = last_payment_date.strftime("%Y-%m-%d")
            due_date_display = due_date.strftime("%Y-%m-%d")
            
            # Calculate total cost (including message cost for this cycle)
            total_overall_cost = total_server_cost + message_monthly_cost + support_cost
            
            # Format response with emojis and message usage information
            response_message = (
                "💰 *Payment Details* 💰\n\n"
                f"🖥️ *Server Costs*\n"
                f"  • Server Cost: ₹{total_server_cost:.2f}\n\n"
                f"📱 *Messaging*\n"
                f"  • Total Messages: {messages_in_cycle}\n"
                f"  • Per Message Cost: ₹{per_message_cost:.2f}\n"
                f"  • Total Message Cost: ₹{message_monthly_cost:.2f}\n\n"
                f"👨‍💻 *Support*\n"
                f"  • Support Cost: ₹{support_cost:.2f}\n\n"
                f"📆 *Payment Cycle*\n"
                f"  • Last Payment: {last_payment_display}\n"
                f"  • Payment Due Date: {due_date_display}\n"
                f"  • Days Remaining: {days_remaining}\n"
                f"  • Cycle Length: {payment_cycle_days} days\n"
                f"  • Status: {status_message}\n\n"
                f"----------------------------------------\n"
                f"💳 *Total Cost: ₹{total_overall_cost:.2f}*\n"
                f"----------------------------------------\n\n"
                f"ℹ️ Message costs are calculated based on the usage during your {payment_cycle_days}-day billing cycle."
            )
            
            # Add overdue warning as a separate message if needed
            if is_overdue:
                response_message += "\n\n⚠️ *PAYMENT OVERDUE* - Most bot commands are blocked until payment is made. Use /payment\\_made to make a payment."
    except Exception as e:
        print(f"❌ Error retrieving payment information: {e}")
        response_message = f"❌ Error retrieving payment information: {str(e)}"
    
    try:
        await update.message.reply_text(response_message, parse_mode='Markdown')
        log_message("SENT", update.effective_chat.id, "", "private", response_message)
    except Exception as markdown_error:
        print(f"❌ Error sending message with Markdown: {markdown_error}")
        # Try to send without markdown as fallback
        try:
            # Remove all markdown formatting
            plain_response = response_message.replace("*", "")
            await update.message.reply_text(plain_response, parse_mode=None)
            log_message("SENT", update.effective_chat.id, "", "private", plain_response)
        except Exception as fallback_error:
            print(f"❌ Error sending fallback message: {fallback_error}")

async def payment_made_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /payment_made command to generate a payment QR code with breakdown"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/payment_made")
    
    try:
        # Calculate the current total cost to store with the payment record
        # Read payment details from JSON file
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        
        if not os.path.exists(payments_file):
            # Create a default payments file if it doesn't exist
            payment_data = {
                "server_cost": 500,
                "server_commission": 50,
                "per_message_cost": 1,  # Default value - read from the file
                "message_monthly_cost": 100,
                "support_cost": 100,
                "payment_cycle_days": 28
            }
            with open(payments_file, 'w', encoding='utf-8') as f:
                json.dump(payment_data, f, indent=2, ensure_ascii=False)
        else:
            # Get payment data
            try:
                with open(payments_file, 'r', encoding='utf-8') as f:
                    payment_data = json.load(f)
            except Exception as e:
                print(f"❌ Error reading payments file: {e}")
                # Create a default payment data structure
                payment_data = {
                    "server_cost": 500,
                    "server_commission": 50,
                    "per_message_cost": 1,
                    "message_monthly_cost": 100,
                    "support_cost": 100,
                    "payment_cycle_days": 28
                }
                
        # Extract payment details
        server_cost = payment_data.get("server_cost", 0)
        server_commission = payment_data.get("server_commission", 0)
        per_message_cost = payment_data.get("per_message_cost", 1)  # Read from payments.json
        message_monthly_cost = payment_data.get("message_monthly_cost", 0)
        support_cost = payment_data.get("support_cost", 0)
        payment_cycle_days = payment_data.get("payment_cycle_days", 28)
        
        # Calculate total server cost (including commission)
        total_server_cost = server_cost + server_commission
        
        # Load payment cycle file and message history
        payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
        json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')
        
        # Initialize or load payment cycle with IST timezone
        if not os.path.exists(payment_cycle_file):
            # Create the file if it doesn't exist - use IST timezone
            current_date = get_ist_now()
            next_bill_date = calculate_next_bill_date(current_date, payment_cycle_days)
            due_date = calculate_due_date(current_date, payment_cycle_days)
            
            payment_cycle = {
                "last_payment_date": current_date.isoformat(),
                "next_bill_date": next_bill_date.isoformat(),
                "due_date": due_date.isoformat(),
                "payment_cycle_days": payment_cycle_days,
                "payment_history": [],
                "current_payment_code": ""
            }
        else:
            # Load existing payment cycle
            with open(payment_cycle_file, 'r', encoding='utf-8') as f:
                payment_cycle = json.load(f)
                if "payment_history" not in payment_cycle:
                    payment_cycle["payment_history"] = []
                
                # Update payment_cycle_days from payments.json if it exists
                payment_cycle["payment_cycle_days"] = payment_cycle_days
                
                # Handle conversion from old format to new format
                if "next_payment_date" in payment_cycle and "next_bill_date" not in payment_cycle:
                    payment_cycle["next_bill_date"] = payment_cycle.pop("next_payment_date")
                
                # Calculate and add due_date if it doesn't exist
                if "due_date" not in payment_cycle:
                    last_payment_date = string_to_ist(payment_cycle["last_payment_date"])
                    due_date = calculate_due_date(last_payment_date, payment_cycle_days)
                    payment_cycle["due_date"] = due_date.isoformat()
                
                # Ensure next_bill_date exists
                if "next_bill_date" not in payment_cycle:
                    last_payment_date = string_to_ist(payment_cycle["last_payment_date"])
                    next_bill_date = calculate_next_bill_date(last_payment_date, payment_cycle_days)
                    payment_cycle["next_bill_date"] = next_bill_date.isoformat()
        
        # Check if payment is allowed on current date
        last_payment_date_str = payment_cycle.get("last_payment_date", "")
        next_bill_date_str = payment_cycle.get("next_bill_date", "") or payment_cycle.get("next_payment_date", "")
        due_date_str = payment_cycle.get("due_date", "")
        
        # If due_date doesn't exist, calculate it
        if not due_date_str and next_bill_date_str:
            due_date = calculate_due_date(string_to_ist(last_payment_date_str), payment_cycle_days)
            due_date_str = due_date.isoformat()
            payment_cycle["due_date"] = due_date_str
        
        # Get current date for informational message
        today = get_ist_now()
        today_date = today.replace(hour=0, minute=0, second=0, microsecond=0).date()
        due_date_dt = string_to_ist(due_date_str)
        due_date_only = due_date_dt.replace(hour=0, minute=0, second=0, microsecond=0).date()
        due_date_display = due_date_dt.strftime("%Y-%m-%d")
        
        # Instead of blocking payment, just show payment status for information
        if today_date < due_date_only:
            # Payment is being made early - just an informational message
            info_message = (
                f"ℹ️ *Payment Information*\n\n"
                f"Your payment is not yet due. The scheduled due date is: {due_date_display}\n\n"
                f"You can still make an early payment, which will be applied to your account."
            )
            await update.message.reply_text(info_message, parse_mode='Markdown')
            log_message("SENT", update.effective_chat.id, "", "private", info_message)
        elif today_date > due_date_only + timedelta(days=1):
            # Payment is overdue - informational message but still allow payment
            info_message = (
                f"ℹ️ *Payment Information*\n\n"
                f"Your payment is currently overdue. The due date was: {due_date_display}\n\n"
                f"Your subscription will be renewed from today for the next billing period."
            )
            await update.message.reply_text(info_message, parse_mode='Markdown')
            log_message("SENT", update.effective_chat.id, "", "private", info_message)
        
        # Calculate message usage in the current payment cycle
        messages_in_cycle = 0
        if os.path.exists(json_log_file) and os.path.getsize(json_log_file) > 0:
            with open(json_log_file, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
                all_messages = chat_history.get("messages", [])
                
                # If there's a last payment date, count messages since then but exclude due date
                if "last_payment_date" in payment_cycle and payment_cycle["last_payment_date"]:
                    try:
                        last_payment_timestamp = string_to_ist(payment_cycle["last_payment_date"])
                        due_date_timestamp = string_to_ist(payment_cycle["due_date"]) if "due_date" in payment_cycle else None
                        
                        for msg in all_messages:
                            try:
                                msg_timestamp = string_to_ist(msg.get("timestamp", ""))
                                
                                # Include messages between last payment and due date (excluding due date)
                                if msg_timestamp >= last_payment_timestamp:
                                    # Reset time components to compare only dates
                                    msg_date = msg_timestamp.replace(hour=0, minute=0, second=0, microsecond=0).date()
                                    due_date_only = due_date_timestamp.replace(hour=0, minute=0, second=0, microsecond=0).date()
                                    
                                    # Only count messages before the due date (not including the due date)
                                    if msg_date < due_date_only:
                                        messages_in_cycle += 1
                            except (ValueError, TypeError) as e:
                                print(f"❌ Error processing message timestamp: {e}")
                                continue
                    except (ValueError, TypeError) as e:
                        print(f"❌ Error processing payment dates: {e}")
                        messages_in_cycle = len(all_messages)
                else:
                    messages_in_cycle = len(all_messages)
        
        # Calculate current message cost
        current_message_cost = messages_in_cycle * per_message_cost
        
        # Update message_monthly_cost based on the current billing cycle messages
        message_monthly_cost = current_message_cost  # Use the actual message cost for this cycle
        
        # Calculate total cost for this payment cycle (including message costs)
        total_cost = total_server_cost + message_monthly_cost + support_cost
        
        # Generate a random payment code (all uppercase with letters and numbers)
        import random
        import string
        payment_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Store the payment code in the payment cycle file for verification later
        payment_cycle["current_payment_code"] = payment_code
        
        # Save updated payment cycle with the payment code
        with open(payment_cycle_file, 'w', encoding='utf-8') as f:
            json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
        
        # Format the cost breakdown message
        cost_breakdown = (
            "💰 *Payment Cost Breakdown* 💰\n\n"
            f"🖥️ *Server Costs*\n"
            f"  • Server Cost: ₹{server_cost + server_commission:.2f}\n\n"
            f"📱 *Messaging*\n"
            f"  • Messages in Cycle: {messages_in_cycle}\n"
            f"  • Per Message Cost: ₹{per_message_cost:.2f}\n"
            f"  • Total Message Cost: ₹{message_monthly_cost:.2f}\n\n"
            f"👨‍💻 *Support*\n"
            f"  • Support Cost: ₹{support_cost:.2f}\n\n"
            f"----------------------------------------\n"
            f"💳 *Total Amount Due: ₹{total_cost:.2f}*\n"
            f"----------------------------------------\n\n"
            "Generating QR code for payment..."
        )
        
        # Send the cost breakdown
        await update.message.reply_text(cost_breakdown, parse_mode='Markdown')
        log_message("SENT", update.effective_chat.id, "", "private", cost_breakdown)
        
        # Generate QR code with the payment code as the message
        if SERVER_CALL_AVAILABLE:
            try:
                # Make sure the QR code directory exists inside telegram_bot folder
                qr_dir = os.path.join(os.path.dirname(__file__), 'qr_codes')
                os.makedirs(qr_dir, exist_ok=True)
                
                # Generate QR code with amount and payment code - use a consistent filename
                qr_save_path = os.path.join(qr_dir, "upi_qr_code.png")
                qr_result = server_call.get_qrcode(
                    amount=int(total_cost),
                    message=payment_code,
                    save_path=qr_save_path
                )
                
                # Send the QR code image to the user
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=open(qr_save_path, "rb"),
                    caption=f"Please scan this QR code to make a payment of ₹{total_cost:.2f}\n\nReference Code: {payment_code}\n\nAfter making the payment, please take a screenshot of the payment confirmation and send it here."
                )
                log_message("SENT", chat_id, "", "private", "Sent QR code for payment")
                
                # Store chat_id in context.user_data to know this user is in payment flow
                context.user_data["awaiting_payment_screenshot"] = True
                context.user_data["payment_code"] = payment_code
                context.user_data["payment_amount"] = total_cost
                
            except Exception as e:
                print(f"❌ Error generating QR code: {e}")
                await update.message.reply_text(f"❌ Error generating QR code: {str(e)}", parse_mode=None)
                log_message("SENT", chat_id, "", "private", f"Error generating QR code: {str(e)}")
        else:
            await update.message.reply_text("❌ Server is not available to generate QR code.", parse_mode='Markdown')
            log_message("SENT", chat_id, "", "private", "Server not available to generate QR code")
            
    except Exception as e:
        print(f"❌ Error in payment flow: {e}")
        await update.message.reply_text(f"❌ Error in payment flow: {str(e)}", parse_mode=None)
        log_message("SENT", update.effective_chat.id, "", "private", f"Error in payment flow: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for photo messages - used in payment flow to process payment screenshots"""
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "[PHOTO]")
    
    # Check if this user is in the payment flow
    if not context.user_data.get("awaiting_payment_screenshot", False):
        await update.message.reply_text("I received your photo, but I'm not expecting a payment screenshot. Use /payment_made to start the payment process.", parse_mode=None)
        log_message("SENT", chat_id, "", "private", "Received unexpected photo")
        return
    
    try:
        # User is in payment flow, download the photo
        photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
        
        # Create a temporary directory inside telegram_bot folder
        temp_dir = os.path.join(os.path.dirname(__file__), 'temp_screenshots')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create a temporary file for the photo - use a consistent filename for each chat_id
        temp_file_path = os.path.join(temp_dir, f"payment_screenshot_{chat_id}.jpg")
        await photo_file.download_to_drive(temp_file_path)
        
        # Let the user know we're processing
        await update.message.reply_text("🔍 Processing your payment screenshot... Please wait.", parse_mode=None)
        log_message("SENT", chat_id, "", "private", "Processing payment screenshot")
        
        if SERVER_CALL_AVAILABLE:
            try:
                # Use the photo_scanner function to extract payment details
                scan_result = server_call.photo_scanner(temp_file_path)
                
                if not scan_result:
                    await update.message.reply_text("❌ Could not extract payment details from the image. Please make sure the payment screenshot is clear and try again.", parse_mode=None)
                    log_message("SENT", chat_id, "", "private", "Failed to extract payment details")
                    return
                
                # Verify the payment details
                payment_amount = scan_result.get("amount")
                payment_recipient = scan_result.get("to", "")
                payment_message = scan_result.get("message", "")
                payment_date = scan_result.get("date", "")
                payment_time = scan_result.get("time", "")
                payment_sender = scan_result.get("from", "")
                payment_upi_id = scan_result.get("upi_transaction_id", "")
                payment_google_id = scan_result.get("google_transaction_id", "")
                
                # Get the expected payment code and amount
                expected_payment_code = context.user_data.get("payment_code", "")
                expected_payment_amount = context.user_data.get("payment_amount", 0)
                expected_recipient = "Shreesha Aithal - shreeshaaithal862-4@oksbi"
                
                # Verify payment details
                verification_issues = []
                
                if payment_message != expected_payment_code:
                    verification_issues.append(f"❌ Payment reference code does not match. Expected: {expected_payment_code}, Found: {payment_message}")
                
                if int(payment_amount) != int(expected_payment_amount):
                    verification_issues.append(f"❌ Payment amount does not match. Expected: ₹{expected_payment_amount:.2f}, Found: ₹{payment_amount}")
                
                if expected_recipient not in payment_recipient:
                    verification_issues.append(f"❌ Payment recipient does not match. Expected: {expected_recipient}, Found: {payment_recipient}")
                
                if verification_issues:
                    # There were issues with the payment verification
                    error_message = "⚠️ Payment Verification Issues\n\n" + "\n".join(verification_issues)
                    await update.message.reply_text(error_message, parse_mode=None)
                    log_message("SENT", chat_id, "", "private", error_message)
                    return
                
                # If we got here, the payment was verified successfully
                # Update the payment cycle
                payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
                json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')
                
                # Load existing payment cycle
                with open(payment_cycle_file, 'r', encoding='utf-8') as f:
                    payment_cycle = json.load(f)
                
                # Calculate message usage in the current payment cycle
                messages_in_cycle = 0
                if os.path.exists(json_log_file) and os.path.getsize(json_log_file) > 0:
                    with open(json_log_file, 'r', encoding='utf-8') as f:
                        chat_history = json.load(f)
                        all_messages = chat_history.get("messages", [])
                        
                        # If there's a last payment date, count messages since then
                        if "last_payment_date" in payment_cycle and payment_cycle["last_payment_date"]:
                            try:
                                last_payment_timestamp = string_to_ist(payment_cycle["last_payment_date"])
                                due_date_timestamp = None
                                
                                # Get or calculate due date
                                if "due_date" in payment_cycle:
                                    due_date_timestamp = string_to_ist(payment_cycle["due_date"])
                                elif "next_bill_date" in payment_cycle:
                                    next_bill_timestamp = string_to_ist(payment_cycle["next_bill_date"])
                                    due_date_timestamp = next_bill_timestamp - timedelta(days=1)
                                else:
                                    due_date_timestamp = calculate_due_date(last_payment_timestamp, payment_cycle.get("payment_cycle_days", 28))
                                
                                # Count messages in the current cycle up to (but not including) due date
                                for msg in all_messages:
                                    try:
                                        msg_timestamp = string_to_ist(msg.get("timestamp", ""))
                                        
                                        # Include messages between last payment and due date (excluding due date)
                                        if msg_timestamp >= last_payment_timestamp:
                                            # Reset time components to compare only dates
                                            msg_date = msg_timestamp.replace(hour=0, minute=0, second=0, microsecond=0).date()
                                            due_date_only = due_date_timestamp.replace(hour=0, minute=0, second=0, microsecond=0).date()
                                            
                                            # Only count messages before the due date (not including the due date)
                                            if msg_date < due_date_only:
                                                messages_in_cycle += 1
                                    except (ValueError, TypeError) as e:
                                        print(f"❌ Error processing message timestamp: {e}")
                                        continue
                            except (ValueError, TypeError) as e:
                                print(f"❌ Error processing payment dates: {e}")
                                messages_in_cycle = len(all_messages)
                        else:
                            messages_in_cycle = len(all_messages)
        
                # Calculate current message cost
                try:
                    payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
                    with open(payments_file, 'r', encoding='utf-8') as f:
                        payment_data = json.load(f)
                except Exception as e:
                    print(f"❌ Error reading payments file: {e}")
                    # Create a default payment data structure
                    payment_data = {
                        "server_cost": 500,
                        "server_commission": 50,
                        "per_message_cost": 1,
                        "message_monthly_cost": 100,
                        "support_cost": 100,
                        "payment_cycle_days": 28
                    }
                
                per_message_cost = payment_data.get("per_message_cost", 1)  # Read from payments.json
                current_message_cost = messages_in_cycle * per_message_cost
                
                # Update message_monthly_cost based on the current billing cycle messages
                message_monthly_cost = current_message_cost  # Use the actual message cost for this cycle
                
                # Update payment dates (in IST)
                current_date = get_ist_now()
                payment_cycle_days = payment_cycle.get("payment_cycle_days", 28)
                
                # Get current payment cycle information
                old_due_date_str = payment_cycle.get("due_date", "")
                old_next_bill_date_str = payment_cycle.get("next_bill_date", "")
                
                # Calculate the base date for the new billing cycle
                # Always use the due date as the base date for calculations
                # This ensures the billing cycle is consistent regardless of when payment is made
                base_date = None
                today = get_ist_now().replace(hour=0, minute=0, second=0, microsecond=0).date()
                
                # If there's a due date and it's not in the future, use it as the base date
                if old_due_date_str:
                    original_due_date = string_to_ist(old_due_date_str)
                    due_date_only = original_due_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
                    
                    # Log for debugging
                    print(f"Original due date: {due_date_only.strftime('%Y-%m-%d')}")
                    print(f"Today's date: {today.strftime('%Y-%m-%d')}")
                    
                    # If due date is in the past or today, use it as base date
                    if due_date_only <= today:
                        base_date = original_due_date
                        print(f"Using due date as base: {due_date_only.strftime('%Y-%m-%d')}")
                
                # If no previous due date or due date is in the future, use current date
                if not base_date:
                    base_date = current_date
                    print(f"Using current date as base: {current_date.strftime('%Y-%m-%d')}")
                
                # Calculate next bill date and due date from the base date
                next_bill_date = calculate_next_bill_date(base_date, payment_cycle_days)
                due_date = calculate_due_date(base_date, payment_cycle_days)
                
                # Log the calculation for debugging
                print(f"Payment received on {current_date.strftime('%Y-%m-%d')}")
                print(f"Base date for calculation: {base_date.strftime('%Y-%m-%d')}")
                print(f"New billing period: {payment_cycle_days} days")
                print(f"Next bill date set to: {next_bill_date.strftime('%Y-%m-%d')}")
                print(f"Due date set to: {due_date.strftime('%Y-%m-%d')}")
                print(f"Next bill date set to: {next_bill_date.strftime('%Y-%m-%d')}")
                print(f"Due date set to: {due_date.strftime('%Y-%m-%d')}")
                
                # Add payment record to history
                payment_record = {
                    "payment_date": current_date.isoformat(),  # Keep for backward compatibility
                    "actual_payment_date": current_date.isoformat(),
                    "billing_start_date": base_date.isoformat(),
                    "messages_count": messages_in_cycle,
                    "message_cost": current_message_cost,
                    "total_message_cost": message_monthly_cost,
                    "total_cost": float(payment_amount),
                    "payment_code": payment_message,
                    "payment_upi_id": payment_upi_id,
                    "payment_google_id": payment_google_id,
                    "payment_sender": payment_sender,
                    "payment_timestamp": f"{payment_date} {payment_time}"
                }
                payment_cycle["payment_history"].append(payment_record)
                
                # Update payment cycle dates
                # Use base_date (due date) as the last_payment_date instead of current_date
                # This ensures the billing cycle is always calculated from the due date
                payment_cycle["last_payment_date"] = base_date.isoformat()
                payment_cycle["next_bill_date"] = next_bill_date.isoformat()
                payment_cycle["due_date"] = due_date.isoformat()
                payment_cycle["current_payment_code"] = ""  # Clear the payment code
                
                # Save updated payment cycle
                with open(payment_cycle_file, 'w', encoding='utf-8') as f:
                    json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
                
                # Format dates for display
                actual_payment_date_display = current_date.strftime("%Y-%m-%d") 
                last_payment_display = base_date.strftime("%Y-%m-%d")  # This is now the base_date
                due_date_display = due_date.strftime("%Y-%m-%d")
                base_date_display = base_date.strftime("%Y-%m-%d")
                
                # Send success message - removed Markdown formatting to prevent parsing errors
                next_bill_date_display = next_bill_date.strftime("%Y-%m-%d")
                success_message = (
                    "✅ Payment Verified Successfully\n\n"
                    "Payment Details\n"
                    f"• Amount: ₹{payment_amount}\n"
                    f"• Date: {payment_date}\n"
                    f"• Time: {payment_time}\n"
                    f"• From: {payment_sender}\n"
                    f"• Reference Code: {payment_message}\n"
                    f"• UPI Transaction ID: {payment_upi_id}\n\n"
                    "Message Usage\n"
                    f"• Total Messages: {messages_in_cycle}\n"
                    f"• Per Message Cost: ₹{per_message_cost:.2f}\n"
                    f"• Total Message Cost: ₹{message_monthly_cost:.2f}\n\n"
                    "Payment Cycle Updated\n"
                    f"• Actual Payment Date: {actual_payment_date_display}\n"
                    f"• Billing Start Date: {last_payment_display}\n"
                    f"• Next Due Date: {due_date_display}\n"
                    f"• Next Bill Date: {next_bill_date_display}\n"
                    f"• Billing Cycle: {payment_cycle.get('payment_cycle_days', 28)} days\n\n"
                    "Your subscription has been renewed for the next billing cycle.\n"
                    "Use /payments to view your updated payment details."
                )
                
                await update.message.reply_text(success_message, parse_mode=None)
                log_message("SENT", chat_id, "", "private", success_message)
                
                # Clear the payment flow state
                context.user_data.pop("awaiting_payment_screenshot", None)
                context.user_data.pop("payment_code", None)
                context.user_data.pop("payment_amount", None)
                
            except Exception as e:
                print(f"❌ Error processing payment screenshot: {e}")
                await update.message.reply_text(f"❌ Error processing payment screenshot: {str(e)}", parse_mode=None)
                log_message("SENT", chat_id, "", "private", f"Error processing payment screenshot: {str(e)}")
        else:
            await update.message.reply_text("❌ Server is not available to process payment screenshot.", parse_mode=None)
            log_message("SENT", chat_id, "", "private", "Server not available to process payment screenshot")
        
        # Clean up the temporary file
        try:
            os.remove(temp_file_path)
        except Exception:
            pass
            
    except Exception as e:
        print(f"❌ Error handling photo: {e}")
        await update.message.reply_text(f"❌ Error handling photo: {str(e)}", parse_mode=None)
        log_message("SENT", chat_id, "", "private", f"Error handling photo: {str(e)}")
        
        # Clear the payment flow state
        context.user_data.pop("awaiting_payment_screenshot", None)
        context.user_data.pop("payment_code", None)
        context.user_data.pop("payment_amount", None)

async def cancel_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel_payment command to cancel ongoing payment process"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/cancel_payment")
    
    try:
        # Check if there's an active payment process for this user
        payment_active = context.user_data.get("awaiting_payment_screenshot", False)
        
        if not payment_active:
            # No active payment process
            response_message = "❌ No active payment process to cancel. Use /payment_made to start a new payment."
            await update.message.reply_text(response_message, parse_mode=None)
            log_message("SENT", chat_id, "", "private", response_message)
            return
        
        # Clear the payment flow state
        context.user_data.pop("awaiting_payment_screenshot", None)
        context.user_data.pop("payment_code", None)
        context.user_data.pop("payment_amount", None)
        
        # Clear the payment code in the payment cycle file
        payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
        
        if os.path.exists(payment_cycle_file):
            try:
                # Load payment cycle data
                with open(payment_cycle_file, 'r', encoding='utf-8') as f:
                    payment_cycle = json.load(f)
                
                # Clear current payment code
                payment_cycle["current_payment_code"] = ""
                
                # Save updated payment cycle
                with open(payment_cycle_file, 'w', encoding='utf-8') as f:
                    json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
                    
                print(f"✅ Cleared payment code for chat_id: {chat_id}")
            except Exception as e:
                print(f"❌ Error clearing payment code: {e}")
        
        # Send cancellation confirmation - ensuring no markdown characters are used
        response_message = "✅ Payment Process Cancelled\n\nThe payment process has been cancelled. Use /payment_made to start a new payment."
        await update.message.reply_text(response_message, parse_mode=None)
        log_message("SENT", chat_id, "", "private", response_message)
        
    except Exception as e:
        print(f"❌ Error cancelling payment: {e}")
        # Ensure error message doesn't contain any Markdown formatting characters
        response_message = f"❌ Error cancelling payment: {str(e)}"
        await update.message.reply_text(response_message, parse_mode=None)
        log_message("SENT", chat_id, "", "private", response_message)

def get_ist_now():
    """Get current datetime in Indian Standard Time (IST)"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def ist_to_string(dt):
    """Convert IST datetime to string format"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def string_to_ist(dt_string):
    """Convert string to IST datetime"""
    ist = pytz.timezone('Asia/Kolkata')
    # Handle both ISO format and custom format strings
    try:
        if 'T' in dt_string:
            dt = datetime.fromisoformat(dt_string)
        else:
            dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
        
        # If the datetime has no timezone info, assume it's in UTC and convert to IST
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc).astimezone(ist)
        return dt
    except (ValueError, TypeError) as e:
        print(f"❌ Error converting date string: {e}")
        return get_ist_now()

def calculate_due_date(start_date, cycle_days):
    """Calculate due date (end of cycle minus 1 day)"""
    ist = pytz.timezone('Asia/Kolkata')
    if isinstance(start_date, str):
        start_date = string_to_ist(start_date)
    
    # Calculate the next bill date (start + cycle_days)
    next_bill_date = start_date + timedelta(days=cycle_days)
    
    # The due date is 1 day before the next bill date
    due_date = next_bill_date - timedelta(days=1)
    
    return due_date

def calculate_next_bill_date(start_date, cycle_days):
    """Calculate next bill date (start + cycle_days)"""
    if isinstance(start_date, str):
        start_date = string_to_ist(start_date)
    
    # Calculate the next bill date (start + cycle_days)
    next_bill_date = start_date + timedelta(days=cycle_days)
    
    return next_bill_date

def can_make_payment(last_payment_date, next_bill_date):
    """Check if payment can be made
    Always returns True - payments are allowed at any time
    When payment is made, the next billing cycle is calculated from the original due date
    """
    # Always allow payments regardless of the date
    return True

def get_payment_status_info():
    """Get current payment status and info message"""
    payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
    if not os.path.exists(payment_cycle_file) or os.path.getsize(payment_cycle_file) == 0:
        return False, "No payment information available"
    
    try:
        with open(payment_cycle_file, 'r', encoding='utf-8') as f:
            payment_cycle = json.load(f)
        
        # Get payment dates
        due_date_str = payment_cycle.get("due_date", "")
        
        if not due_date_str:
            return False, "No due date available"
        
        # Get current date in IST
        today = get_ist_now()
        
        # Convert dates to datetime objects
        due_date = string_to_ist(due_date_str)
        
        # Calculate the day after due date (last allowed payment day)
        day_after_due = due_date + timedelta(days=1)
        
        # Reset time components to compare only dates
        today_date = today.replace(hour=0, minute=0, second=0, microsecond=0).date()
        due_date_only = due_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
        day_after_due_date = day_after_due.replace(hour=0, minute=0, second=0, microsecond=0).date()
        
        # Format dates for display
        due_date_display = due_date_only.strftime("%Y-%m-%d")
        day_after_due_display = day_after_due_date.strftime("%Y-%m-%d")
        
        # Check payment status
        if today_date < due_date_only:
            # Before due date
            days_until = (due_date_only - today_date).days
            return False, f"🟢 Active - Payment due in {days_until} days (on {due_date_display})"
        elif today_date == due_date_only:
            # On due date
            return False, f"🟡 Payment Due Today ({due_date_display})"
        elif today_date == day_after_due_date:
            # Day after due date (last day to pay)
            return False, f"🟠 Last Day to Pay (due date was {due_date_display})"
        else:
            # After day after due date (payment overdue)
            days_overdue = (today_date - day_after_due_date).days
            return True, f"🔴 OVERDUE - Payment was due on {due_date_display}, last day to pay was {day_after_due_display}"
    except Exception as e:
        print(f"❌ Error getting payment status: {e}")
        return False, "Error checking payment status"

def is_payment_overdue():
    """Check if payment is overdue - returns True if payment is overdue, False otherwise"""
    is_overdue, _ = get_payment_status_info()
    return is_overdue

# List of commands that are always allowed, even when payment is overdue
ALLOWED_COMMANDS = [
    "help", 
    "payments", 
    "payment_made",
    "cancel_payment",
    "total_messages"
]

def payment_required(func):
    """Decorator to check if payment is overdue before executing a command"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split()[0][1:] if update.message and update.message.text else ""
        
        # Check if command is in the allowed list
        if command.lower() in ALLOWED_COMMANDS:
            return await func(update, context)
        
        # Check if payment is overdue
        if is_payment_overdue():
            chat_id = update.effective_chat.id
            username = update.effective_user.username if update.effective_user else "unknown"
            chat_type = update.effective_chat.type if update.effective_chat else "private"
            log_message("RECEIVED", chat_id, username, chat_type, update.message.text if update.message else "")
            
            response_message = (
                "🔒 *Payment Required*\n\n"
                "Your payment is overdue. Most commands are locked until payment is made.\n\n"
                "Please use the following commands:\n"
                "• /payments - View payment details\n"
                "• /payment\\_made - Make a payment\n"
                "• /help - Show available commands\n"
                "• /cancel\\_payment - Cancel a payment\n"
                "• /total\\_messages - View message statistics"
            )
            
            await update.message.reply_text(response_message, parse_mode='Markdown')
            log_message("SENT", chat_id, "", "private", response_message)
            return
        
        # If payment is not overdue, execute the command
        return await func(update, context)
    
    return wrapper
def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    
    # Initialize or load payment cycle information
    payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
    
    # Initialize or load payments.json file first to get payment_cycle_days
    payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
    if not os.path.exists(payments_file) or os.path.getsize(payments_file) == 0:
        # Create default payments file
        payment_data = {
            "server_cost": 500,
            "server_commission": 50,
            "per_message_cost": 1,  # Default value - read from the file
            "message_monthly_cost": 100,
            "support_cost": 100,
            "payment_cycle_days": 28
        }
        with open(payments_file, 'w', encoding='utf-8') as f:
            json.dump(payment_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Created payments file with default values")
        payment_cycle_days = 28
    else:
        # Load existing payments file
        try:
            with open(payments_file, 'r', encoding='utf-8') as f:
                payment_data = json.load(f)
            
            # Get payment cycle days
            payment_cycle_days = payment_data.get("payment_cycle_days", 28)
            
            # Add payment_cycle_days if it doesn't exist
            if "payment_cycle_days" not in payment_data:
                payment_data["payment_cycle_days"] = payment_cycle_days
                with open(payments_file, 'w', encoding='utf-8') as f:
                    json.dump(payment_data, f, indent=2, ensure_ascii=False)
                print(f"✅ Added payment_cycle_days to payments file")
                
        except Exception as e:
            print(f"❌ Error updating payment settings: {e}")
            payment_cycle_days = 28
    
    if not os.path.exists(payment_cycle_file) or os.path.getsize(payment_cycle_file) == 0:
        # Create default payment cycle file with IST timestamps
        current_date = get_ist_now()
        next_bill_date = calculate_next_bill_date(current_date, payment_cycle_days)
        due_date = calculate_due_date(current_date, payment_cycle_days)
        
        payment_cycle = {
            "last_payment_date": current_date.isoformat(),
            "next_bill_date": next_bill_date.isoformat(),
            "due_date": due_date.isoformat(),
            "payment_cycle_days": payment_cycle_days,
            "payment_history": [],
            "current_payment_code": ""
        }
        with open(payment_cycle_file, 'w', encoding='utf-8') as f:
            json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
        print(f"✅ Created payment cycle file with start date: {current_date} and cycle days: {payment_cycle_days}")
    else:
        # Payment cycle file exists, check if it needs updates
        try:
            with open(payment_cycle_file, 'r', encoding='utf-8') as f:
                payment_cycle = json.load(f)
                
            # Ensure the payment cycle has all required fields
            if not payment_cycle.get("last_payment_date"):
                payment_cycle["last_payment_date"] = get_ist_now().isoformat()
            
            # Handle conversion from old format to new format
            if "next_payment_date" in payment_cycle and "next_bill_date" not in payment_cycle:
                payment_cycle["next_bill_date"] = payment_cycle.pop("next_payment_date")
            
            if "next_bill_date" not in payment_cycle:
                last_payment = string_to_ist(payment_cycle["last_payment_date"])
                payment_cycle["next_bill_date"] = calculate_next_bill_date(last_payment, payment_cycle_days).isoformat()
            
            if "due_date" not in payment_cycle:
                last_payment = string_to_ist(payment_cycle["last_payment_date"])
                payment_cycle["due_date"] = calculate_due_date(last_payment, payment_cycle_days).isoformat()
            
            # Update payment_cycle_days from payments.json
            if payment_cycle.get("payment_cycle_days") != payment_cycle_days:
                payment_cycle["payment_cycle_days"] = payment_cycle_days
                print(f"✅ Updated payment cycle days to: {payment_cycle_days}")
                
                # Recalculate due_date and next_bill_date if payment_cycle_days changed
                last_payment = string_to_ist(payment_cycle["last_payment_date"])
                payment_cycle["next_bill_date"] = calculate_next_bill_date(last_payment, payment_cycle_days).isoformat()
                payment_cycle["due_date"] = calculate_due_date(last_payment, payment_cycle_days).isoformat()
            
            # Ensure payment_history exists
            if "payment_history" not in payment_cycle:
                payment_cycle["payment_history"] = []
                
            with open(payment_cycle_file, 'w', encoding='utf-8') as f:
                json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Error initializing payment cycle: {e}")
                
        except Exception as e:
            print(f"❌ Error initializing payment cycle: {e}")
    
    # Make sure the QR code directory exists
    qr_dir = os.path.join(os.path.dirname(__file__), 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)
    
    # Initialize or create temp directory for payment screenshots
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Initialize or create whatsappBot directory for QR codes
    whatsapp_dir = "whatsappBot"
    os.makedirs(whatsapp_dir, exist_ok=True)
    
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
    print("   /settings, /notify, /stop_notify, /total_messages, /payments")
    print("   /payment_made, /cancel_payment")
    print("=" * 50)
    
    # Create the Application with timeouts
    application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).build()
    
    # Add command handlers - apply payment_required decorator to commands that should be blocked when payment is overdue
    application.add_handler(CommandHandler("start", payment_required(start_command)))
    application.add_handler(CommandHandler("help", help_command))  # Always allowed
    application.add_handler(CommandHandler("start_bot", payment_required(start_bot_command)))
    application.add_handler(CommandHandler("stop_bot", payment_required(stop_bot_command)))
    application.add_handler(CommandHandler("status", payment_required(status_command)))
    application.add_handler(CommandHandler("settings", payment_required(settings_command)))
    application.add_handler(CommandHandler("notify", payment_required(notify_command)))
    application.add_handler(CommandHandler("stop_notify", payment_required(stop_notify_command)))
    application.add_handler(CommandHandler("total_messages", payment_required(total_messages_command)))
    application.add_handler(CommandHandler("payments", payments_command))  # Always allowed
    application.add_handler(CommandHandler("payment_made", payment_made_command))  # Always allowed
    application.add_handler(CommandHandler("cancel_payment", cancel_payment_command))  # Always allowed
    
    # Add message handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, payment_required(handle_message)))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))  # Allow photo handling regardless of payment status for payment verification
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    print("🚀 Bot is starting...")
    print("💡 Send /start to begin!")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()