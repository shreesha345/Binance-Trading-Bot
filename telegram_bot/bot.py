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
from razerpay import (
    create_payment_link_with_breakdown, check_payment_status, 
    save_customer_details, get_customer_details,
    save_payment_link_info, get_payment_info_by_chat_id,
    verify_payment_and_update_cycle, is_payment_allowed
)

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
        "💰 /payments - View payment details\n\n"
        "💳 *Payment Options:*\n"
        "💳 /pay\\_razer - Make payment with Razorpay\n"
        "✅ /done - Verify completed payment\n\n"
        "📝 *Settings Format:*\n"
        "`candle_interval,symbol,quantity,buy_offset,sell_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`\n\n"
        "⚠️ *Payment System:*\n"
        "• Payment cycle starts from your last payment date\n"
        "• Next bill date is calculated using payment\\_cycle\\_days\n"
        "• Due date is 1 day before the next bill date\n"
        "• Grace period: 1 day after due date for payment\n"
        "• Message costs are calculated per payment cycle\n"
        "• If payment is overdue, bot stops and only allows:\n"
        "  /start, /help, /payments, /pay\\_razer, /done, /cancel, /total\\_messages\n"
        "• All other commands are blocked until payment is made"
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

# Helper functions for date handling and message counting
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

def get_ist_now():
    """Get current time in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def count_messages_for_date_range(chat_id, start_date, end_date):
    """
    Count messages for a specific chat_id within a date range
    
    Args:
        chat_id: The chat ID to filter messages for
        start_date: Start date (inclusive) - can be date or datetime object
        end_date: End date (exclusive) - can be date or datetime object
    
    Returns:
        tuple: (total_messages, sent_messages, received_messages, first_message, last_message, all_messages)
    """
    try:
        json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')
        
        if not os.path.exists(json_log_file) or os.path.getsize(json_log_file) == 0:
            return 0, 0, 0, None, None, []
            
        # Convert date objects to date if they're datetime objects
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        # Read messages from file
        with open(json_log_file, 'r', encoding='utf-8') as f:
            chat_history = json.load(f)
            messages = chat_history.get("messages", [])
        
        # Filter by chat_id
        messages = [msg for msg in messages if str(msg.get("chat_id")) == str(chat_id)]
        
        # Filter by date range
        filtered_messages = []
        for msg in messages:
            try:
                # First try to use the timestamp for consistent datetime handling
                if "timestamp" in msg:
                    msg_timestamp = string_to_ist(msg.get("timestamp", ""))
                    msg_date = msg_timestamp.date()
                else:
                    # Fall back to date field if timestamp not available
                    msg_date = datetime.strptime(msg.get("date", "1970-01-01"), '%Y-%m-%d').date()
                
                # Include start date but exclude end date for cycle counting
                if start_date <= msg_date < end_date:
                    filtered_messages.append(msg)
            except (ValueError, TypeError) as e:
                print(f"❌ Error processing message date in count_messages_for_date_range: {e}")
                continue
        
        # Count messages
        total_messages = len(filtered_messages)
        total_sent = sum(1 for msg in filtered_messages if msg.get("type") == "SENT")
        total_received = sum(1 for msg in filtered_messages if msg.get("type") == "RECEIVED")
        
        # Get first and last message
        first_message = filtered_messages[0] if filtered_messages else None
        last_message = filtered_messages[-1] if filtered_messages else None
        
        return total_messages, total_sent, total_received, first_message, last_message, filtered_messages
        
    except Exception as e:
        print(f"❌ Error counting messages for date range: {e}")
        return 0, 0, 0, None, None, []

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
        "💰 /payments - View payment details\n\n"
        "💳 *Payment Options:*\n"
        "💳 /pay\\_razer - Make payment with Razorpay\n"
        "✅ /done - Verify completed payment\n"
        "❌ /cancel - Cancel payment process\n\n"
        "📝 *Settings Format:*\n"
        "`interval,symbol,quantity,buy_long_offset,sell_long_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`\n\n"
        "⚠️ *Payment System:*\n"
        "• Payment is due on the specified due date\n"
        "• Payments can only be made on or after the due date\n"
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
        "💰 /payments - View payment details\n\n"
        "💳 *Payment System:*\n"
        "💵 /pay\\_razer - Make a payment via Razorpay\n"
        "✅ /done - Verify payment completion\n"
        "❌ /cancel - Cancel an ongoing payment process\n\n"
        "📝 *Settings Format:*\n"
        "`candle_interval,symbol,quantity,buy_long_offset,sell_long_offset`\n"
        "Example: `1m,BTCUSDT,0.01,10,10`\n\n"
        "⚠️ *Payment System:*\n"
        "• Payment is due on the specified due date\n"
        "• Payments can only be made on or after the due date\n"
        "• You have 1 extra day after the due date to make payment\n" 
        "• If payment is not made, only /help, /payments, /pay\\_razer, /done, and /total\\_messages will work\n"
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
        "📊 *Percentage-Based Trading:*\n"
        "Add % to quantity for percentage of balance (e.g., `5%` to use 5% of available balance)\n"
        "`1m,BTCUSDT,5%,10,10`\n\n"
        "Where:\n"
        "• Candle Interval: e.g., 1m, 5m, 1h\n"
        "• Symbol: Trading pair (e.g., BTCUSDT)\n"
        "• Quantity: Trade amount (fixed or percentage with %)\n"
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

    # Check if awaiting customer details for payment
    if notify_users.get(chat_id, {}).get("awaiting_customer_details", False):
        current_field = notify_users[chat_id].get("current_field")
        
        if current_field:
            # Save the provided field
            notify_users[chat_id]["customer_details"][current_field] = message_text
            
            # Update customer details in storage
            save_customer_details(
                chat_id,
                name=notify_users[chat_id]["customer_details"].get("name"),
                email=notify_users[chat_id]["customer_details"].get("email"),
                phone=notify_users[chat_id]["customer_details"].get("phone")
            )
            
            # Check if we have more fields to collect
            missing_fields = notify_users[chat_id]["missing_fields"]
            missing_fields.remove(current_field)
            
            if missing_fields:
                # Ask for the next field
                next_field = missing_fields[0]
                notify_users[chat_id]["current_field"] = next_field
                
                if next_field == "name":
                    message = "Please enter your full name for the payment:\n(You can use /cancel to stop the payment process)"
                elif next_field == "phone":
                    message = "Please enter your phone number with country code (e.g., +919876543210):\n(You can use /cancel to stop the payment process)"
                else:
                    message = f"Please enter your {next_field}:"
                
                await update.message.reply_text(message)
                log_message("SENT", chat_id, "", "private", message)
                return
            else:
                # All fields collected, reset state
                notify_users[chat_id]["awaiting_customer_details"] = False
                
                # Run the pay_razer command again now that we have all details
                await pay_razer_command(update, context)
                return
    
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
                
                # Check if quantity is percentage-based (ends with %)
                quantity_type = "fixed"
                quantity_percentage = "10"  # Default value
                if quantity.endswith('%'):
                    quantity_type = "percentage"
                    quantity_percentage = quantity.rstrip('%')
                    quantity = "1"  # Set a default fallback value for fixed quantity
                
                # Use update_trading_config to add all the data in a single API call
                result = server_call.update_trading_config(
                    candle_interval=candle_interval,
                    symbol_name=symbol,
                    quantity=quantity,
                    buy_long_offset=buy_long_offset,
                    sell_long_offset=sell_long_offset,
                    quantity_type=quantity_type,
                    quantity_percentage=quantity_percentage
                )
                
                # Set display value based on quantity type
                quantity_display = f"{quantity_percentage}% of balance" if quantity_type == "percentage" else quantity

                response_message = (
                    f"✅ *Settings Updated Successfully*\n\n"
                    f"*Candle Interval:* {candle_interval}\n"
                    f"*Symbol:* {symbol}\n"
                    f"*Quantity:* {quantity_display}\n"
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
    """Handle /total_messages command to show message counts with optional date range filtering"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    command_text = update.message.text if update.message else "/total_messages"
    log_message("RECEIVED", chat_id, username, chat_type, command_text)
    
    # Parse date range arguments
    start_date = None
    end_date = None
    date_range_str = ""
    
    if context.args:
        try:
            # Parse start date
            if len(context.args) >= 1:
                start_date = datetime.strptime(context.args[0], '%Y-%m-%d').date()
                date_range_str = f" for {start_date.strftime('%Y-%m-%d')}"
            
            # Parse end date if provided
            if len(context.args) >= 2:
                end_date = datetime.strptime(context.args[1], '%Y-%m-%d').date()
                date_range_str = f" from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            else:
                # If only start date is provided, use it as both start and end
                end_date = start_date
                
        except ValueError:
            await update.message.reply_text(
                "⚠️ *Invalid date format*\n\nPlease use YYYY-MM-DD format.\n\n*Examples:*\n• `/total_messages 2025-07-03` - Show messages for July 3rd\n• `/total_messages 2025-07-01 2025-07-31` - Show messages for July",
                parse_mode='Markdown'
            )
            log_message("SENT", chat_id, "", "private", "Invalid date format error")
            return
    else:
        # No date arguments provided - use current payment cycle
        try:
            # Load payment cycle information from payments.json
            payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
            
            if os.path.exists(payments_file) and os.path.getsize(payments_file) > 0:
                with open(payments_file, 'r', encoding='utf-8') as f:
                    payment_data = json.load(f)
                
                # Extract payment dates
                last_payment_date_str = payment_data.get("last_payment_date", "")
                due_date_str = payment_data.get("due_date", "")
                payment_cycle_days = payment_data.get("payment_cycle_days", 28)
                
                if last_payment_date_str:
                    last_payment_date = string_to_ist(last_payment_date_str)
                    # Convert to date object for filtering
                    start_date = last_payment_date.date()
                    
                    # If due_date is provided, use it, otherwise calculate it
                    if due_date_str:
                        due_date = string_to_ist(due_date_str)
                        end_date = due_date.date()
                    else:
                        due_date = calculate_due_date(last_payment_date, payment_cycle_days)
                        end_date = due_date.date()
                    
                    date_range_str = f" for current payment cycle ({start_date} to {end_date})"
        except Exception as e:
            print(f"❌ Error loading payment cycle: {e}")
            # No filtering for dates if there's an error
    
    # Use the common function to count messages for the date range
    if start_date and end_date:
        total_messages, total_sent, total_received, first_msg, last_msg, messages = count_messages_for_date_range(
            chat_id, start_date, end_date
        )
    else:
        # No date range provided, count all messages
        try:
            json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')
            if not os.path.exists(json_log_file) or os.path.getsize(json_log_file) == 0:
                messages = []
            else:
                with open(json_log_file, 'r', encoding='utf-8') as f:
                    chat_history = json.load(f)
                    messages = chat_history.get("messages", [])
                    # Filter by chat_id
                    messages = [msg for msg in messages if str(msg.get("chat_id")) == str(chat_id)]
                    
            total_messages = len(messages)
            total_sent = sum(1 for msg in messages if msg.get("type") == "SENT")
            total_received = sum(1 for msg in messages if msg.get("type") == "RECEIVED")
            first_msg = messages[0] if messages else None
            last_msg = messages[-1] if messages else None
        except Exception as e:
            print(f"❌ Error retrieving chat history: {e}")
            messages = []
            total_messages = total_sent = total_received = 0
            first_msg = last_msg = None
    
    # Get date of first and last message in the filtered set
    first_message_date = "N/A"
    last_message_date = "N/A"
    
    if first_msg:
        first_message_date = f"{first_msg.get('date', 'N/A')} {first_msg.get('time', '')}"
    
    if last_msg:
        last_message_date = f"{last_msg.get('date', 'N/A')} {last_msg.get('time', '')}"
    
    # Create response message with date range if specified
    response_message = (
        f"📊 *Message Statistics{date_range_str}*\n\n"
        f"*Total Messages:* {total_messages}\n"
        f"*Messages Sent:* {total_sent}\n"
        f"*Messages Received:* {total_received}\n\n"
        f"*First Message:* {first_message_date}\n"
        f"*Latest Message:* {last_message_date}\n\n"
    )
    
    # Add note about filtering logic for payment cycle
    if start_date and end_date and not context.args:
        response_message += (
            "*Note:* For payment cycle statistics, messages are counted from the last payment date (inclusive) "
            "up to the due date (exclusive).\n\n"
        )
    
    response_message += (
        "*Usage:*\n"
        "• `/total_messages` - Show messages for current payment cycle\n"
        "• `/total_messages YYYY-MM-DD` - Show messages for specific date\n"
        "• `/total_messages YYYY-MM-DD YYYY-MM-DD` - Show messages in date range"
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
            per_message_cost = payment_data.get("per_message_cost", 1)  # Read from payments.json
            message_monthly_cost = payment_data.get("message_monthly_cost", 0)
            support_cost = payment_data.get("support_cost", 0)
            
            # Calculate message statistics for the current cycle
            json_log_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')
            
            # Get payment cycle information directly from payments.json
            try:
                # Extract payment dates - using the payment_data we already loaded
                last_payment_date_str = payment_data.get("last_payment_date", "")
                next_bill_date_str = payment_data.get("next_bill_date", "")
                due_date_str = payment_data.get("due_date", "")
                
                # Get payment cycle days
                payment_cycle_days = payment_data.get("payment_cycle_days", 28)
                
                # Parse dates using IST timezone
                if last_payment_date_str:
                    last_payment_date = string_to_ist(last_payment_date_str)
                else:
                    # Default if no payment date is set
                    last_payment_date = get_ist_now() - timedelta(days=payment_cycle_days)
                
                # If due_date is provided, use it, otherwise calculate it
                if due_date_str:
                    due_date = string_to_ist(due_date_str)
                elif next_bill_date_str:
                    next_bill_date = string_to_ist(next_bill_date_str)
                    due_date = next_bill_date - timedelta(days=1)
                else:
                    # Calculate dates if not provided
                    due_date = calculate_due_date(last_payment_date, payment_cycle_days)
                    next_bill_date = due_date + timedelta(days=1)
                    
                    # Update payments.json with calculated dates if they're missing
                    if not due_date_str or not next_bill_date_str:
                        payment_data["due_date"] = due_date.isoformat()
                        payment_data["next_bill_date"] = next_bill_date.isoformat()
                        payment_data["next_bill_due_date"] = (next_bill_date + timedelta(days=1)).isoformat()
                        
                        # Save updated payment data
                        with open(payments_file, 'w', encoding='utf-8') as f:
                            json.dump(payment_data, f, indent=2, ensure_ascii=False)
                            print("✅ Updated payments.json with missing cycle dates")
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
            
            # Get total message count in the current cycle using the common function
            last_payment_date_only = last_payment_date.date()
            due_date_only = due_date.date()
            
            # Use the shared function to count messages for the payment cycle
            messages_in_cycle, sent_messages, received_messages, _, _, _ = count_messages_for_date_range(
                chat_id, last_payment_date_only, due_date_only
            )
            
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
            total_overall_cost = server_cost + message_monthly_cost + support_cost
            
            # Format response with emojis and message usage information
            response_message = (
                "💰 *Payment Details* 💰\n\n"
                f"🖥️ *Server Costs*\n"
                f"  • Server Cost: ₹{server_cost:.2f}\n\n"
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
                f"ℹ️ Message costs are calculated for messages sent between {last_payment_display} (inclusive) and {due_date_display} (exclusive) - a {payment_cycle_days}-day billing cycle."
            )
            
            # Add overdue warning as a separate message if needed
            if is_overdue:
                response_message += "\n\n⚠️ *PAYMENT OVERDUE* - Most bot commands are blocked until payment is made. Use /pay\\_razer to make a payment. If you need to cancel during the payment process, use /cancel."
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

async def pay_razer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pay_razer command to generate a Razerpay payment link"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/pay_razer")
    
    # Check if payment is allowed based on due date
    payment_allowed, reason = is_payment_allowed(chat_id)
    
    if not payment_allowed:
        await update.message.reply_text(
            f"❌ *Payment Not Allowed*\n\n{reason}\n\nPayments can only be made on or after the due date.",
            parse_mode='Markdown'
        )
        log_message("SENT", chat_id, "", "private", f"Payment not allowed: {reason}")
        return
    
    # Get customer details if previously saved
    customer = get_customer_details(chat_id)
    
    # Check if we have all required details
    if not customer or not all(key in customer for key in ["name", "phone"]):
        # We need to ask for customer details
        if not customer:
            customer = {}
        
        # Check what information we're missing
        missing_fields = []
        if "name" not in customer:
            missing_fields.append("name")
        if "phone" not in customer:
            missing_fields.append("phone")
        
        # Initialize state for awaiting customer details
        if "awaiting_customer_details" not in notify_users.get(chat_id, {}):
            if chat_id not in notify_users:
                notify_users[chat_id] = {}
            notify_users[chat_id]["awaiting_customer_details"] = True
            notify_users[chat_id]["customer_details"] = customer.copy()
            notify_users[chat_id]["missing_fields"] = missing_fields
            notify_users[chat_id]["current_field"] = missing_fields[0] if missing_fields else None
        
        # Ask for the first missing field
        if missing_fields:
            field = missing_fields[0]
            if field == "name":
                message = "Please enter your full name for the payment:\n(You can use /cancel to stop the payment process)"
            elif field == "phone":
                message = "Please enter your phone number with country code (e.g., +919876543210):\n(You can use /cancel to stop the payment process)"
            else:
                message = f"Please enter your {field}:"
            
            await update.message.reply_text(message)
            log_message("SENT", chat_id, "", "private", message)
            return
    
    # We have all required details, generate payment link
    try:
        # Create payment link
        result = create_payment_link_with_breakdown(
            customer_name=customer.get("name", "Trading Bot User"),
            customer_email=customer.get("email"),
            customer_phone=customer.get("phone")
        )
        
        if result.get("status") == "success":
            # Save payment info
            save_payment_link_info(chat_id, result)
            
            # Send payment link
            payment_link = result.get("payment_link")
            amount = result.get("amount", 0)
            breakdown = result.get("breakdown", {})

            # Format a nice message with breakdown
            message = (
                f"💳 *Payment Link Generated*\n\n"
                f"Total Amount: ₹{amount:.2f}\n\n"
                f"*Breakdown:*\n"
                f"• Server Cost: ₹{breakdown.get('Server Cost', 0):.2f}\n"
                f"• Message Cost: ₹{breakdown.get('Message Monthly Cost', 0):.2f}\n"
                f"• Support Cost: ₹{breakdown.get('Support Cost', 0):.2f}\n\n"
                f"🔗 *Payment Link:*\n{payment_link}\n\n"
                f"After completing the payment, please use the /done command to verify your payment.\n"
                f"If you need to cancel this payment process, use the /cancel command."
            )
            
            await update.message.reply_text(message, parse_mode='Markdown')
            log_message("SENT", chat_id, "", "private", message)
        else:
            # Error creating payment link
            error_message = f"❌ *Error Creating Payment Link*\n\n{result.get('message', 'Unknown error')}"
            await update.message.reply_text(error_message, parse_mode='Markdown')
            log_message("SENT", chat_id, "", "private", error_message)
    
    except Exception as e:
        error_message = f"❌ *Error*: {str(e)}"
        await update.message.reply_text(error_message, parse_mode='Markdown')
        log_message("SENT", chat_id, "", "private", error_message)

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /done command to verify a completed payment"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/done")
    
    # Get the most recent payment info for this chat ID
    payment_info = get_payment_info_by_chat_id(chat_id)
    
    if not payment_info:
        message = "❌ *No Payment Found*\n\nNo recent payment link was generated for you. Please use /pay_razer to generate a payment link first."
        await update.message.reply_text(message, parse_mode='Markdown')
        log_message("SENT", chat_id, "", "private", message)
        return
    
    # Get payment ID from the saved payment info
    payment_id = payment_info.get("breakdown", {}).get("payment_id")
    
    if not payment_id:
        message = "❌ *Invalid Payment Data*\n\nCould not find payment ID in your recent payment. Please use /pay_razer to generate a new payment link."
        await update.message.reply_text(message, parse_mode='Markdown')
        log_message("SENT", chat_id, "", "private", message)
        return
    
    # Verify payment
    verification_result = verify_payment_and_update_cycle(payment_id)
    
    if verification_result.get("success"):
        # Payment was successful
        next_bill_date = verification_result.get("next_bill_date", "Unknown")
        due_date = verification_result.get("due_date", "Unknown")
        
        message = (
            f"✅ *Payment Confirmed*\n\n"
            f"Your payment has been verified and your subscription has been extended.\n\n"
            f"*Next Bill Date:* {next_bill_date}\n"
            f"*Due Date:* {due_date}\n\n"
            f"Thank you for your payment!"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        log_message("SENT", chat_id, "", "private", message)
    else:
        # Payment verification failed
        status = verification_result.get("status", {})
        payment_status = status.get("payment_status", status.get("status", "Unknown"))
        
        message = (
            f"❌ *Payment Not Confirmed*\n\n"
            f"Your payment could not be verified. Current status: {payment_status}\n\n"
            f"{verification_result.get('message', '')}\n\n"
            f"If you have completed the payment, please wait a few minutes and try again."
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        log_message("SENT", chat_id, "", "private", message)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command to cancel the current payment process"""
    # Log the command
    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else "unknown"
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    log_message("RECEIVED", chat_id, username, chat_type, "/cancel")
    
    # Import razerpay functions (without telegram_bot prefix)
    from razerpay import clear_customer_details, clear_payment_link_info, get_payment_info_by_chat_id
    
    # Check if there's an ongoing payment process either through customer details collection
    # or an existing payment link
    is_payment_process_active = notify_users.get(chat_id, {}).get("awaiting_customer_details", False)
    payment_info = get_payment_info_by_chat_id(chat_id)
    
    # Clear any in-memory payment flow state
    if chat_id in notify_users:
        notify_users[chat_id]["awaiting_customer_details"] = False
        notify_users[chat_id].pop("customer_details", None)
        notify_users[chat_id].pop("missing_fields", None) 
        notify_users[chat_id].pop("current_field", None)
    
    # Clear customer details and payment link info from files
    clear_customer_details(chat_id)
    payment_link_cleared = clear_payment_link_info(chat_id)
    
    # Always give a positive confirmation to the user
    message = "✅ Payment process canceled. You can start a new payment by using the /pay\\_razer command when you're ready."
    
    try:
        await update.message.reply_text(message, parse_mode='Markdown')
        log_message("SENT", chat_id, "", "private", message)
    except Exception as e:
        # If there's an error with Markdown parsing, send without markdown
        print(f"❌ Error sending cancel confirmation with markdown: {e}")
        plain_message = "✅ Payment process canceled. You can start a new payment by using the /pay_razer command when you're ready."
        await update.message.reply_text(plain_message, parse_mode=None)
        log_message("SENT", chat_id, "", "private", plain_message)

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

def calculate_next_bill_due_date(start_date, cycle_days):
    """Calculate next bill due date (end of cycle + 1 day for grace period)"""
    ist = pytz.timezone('Asia/Kolkata')
    if isinstance(start_date, str):
        start_date = string_to_ist(start_date)
    
    # Calculate the next bill date (start + cycle_days)
    next_bill_date = start_date + timedelta(days=cycle_days)
    
    # The next bill due date is 1 day after the next bill date (grace period)
    next_bill_due_date = next_bill_date + timedelta(days=1)
    
    return next_bill_due_date

def calculate_next_bill_date(start_date, cycle_days):
    """Calculate next bill date (start + cycle_days)"""
    if isinstance(start_date, str):
        start_date = string_to_ist(start_date)
    
    # Calculate the next bill date (start + cycle_days)
    next_bill_date = start_date + timedelta(days=cycle_days)
    
    return next_bill_date

def can_make_payment(last_payment_date, due_date):
    """Check if payment can be made
    Payments are only allowed on or after the due date
    Returns True if payment is allowed, False otherwise
    """
    # Get current date in IST
    today = get_ist_now()
    today_date = today.replace(hour=0, minute=0, second=0, microsecond=0).date()
    
    # Convert due date to date object for comparison
    if isinstance(due_date, str):
        due_date = string_to_ist(due_date)
    due_date_only = due_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
    
    # Payment is allowed only on or after the due date
    return today_date >= due_date_only

def get_payment_status_info():
    """Get current payment status and info message"""
    payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
    if not os.path.exists(payments_file) or os.path.getsize(payments_file) == 0:
        return False, "No payment information available"
    
    try:
        with open(payments_file, 'r', encoding='utf-8') as f:
            payment_data = json.load(f)
        
        # Get payment dates
        due_date_str = payment_data.get("due_date", "")
        next_bill_due_date_str = payment_data.get("next_bill_due_date", "")
        
        # If due_date is missing, we can't determine payment status
        if not due_date_str:
            return False, "No due date available"
            
        # If next_bill_due_date is missing, calculate it from due_date (1 day after due date)
        if not next_bill_due_date_str:
            due_date = string_to_ist(due_date_str)
            next_bill_due_date = due_date + timedelta(days=2)  # 2 days after due date (1 day grace period)
            next_bill_due_date_str = next_bill_due_date.isoformat()
            
            # Update payments.json with the calculated next_bill_due_date
            payment_data["next_bill_due_date"] = next_bill_due_date_str
            try:
                with open(payments_file, 'w', encoding='utf-8') as f:
                    json.dump(payment_data, f, indent=2, ensure_ascii=False)
                print(f"✅ Added missing next_bill_due_date to payments.json: {next_bill_due_date_str}")
            except Exception as update_error:
                print(f"❌ Error updating payments.json: {update_error}")
        
        # Get current date in IST
        today = get_ist_now()
        
        # Convert dates to datetime objects
        due_date = string_to_ist(due_date_str)
        next_bill_due_date = string_to_ist(next_bill_due_date_str)
        
        # Reset time components to compare only dates
        today_date = today.replace(hour=0, minute=0, second=0, microsecond=0).date()
        due_date_only = due_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
        next_bill_due_date_only = next_bill_due_date.replace(hour=0, minute=0, second=0, microsecond=0).date();
        
        # Format dates for display
        due_date_display = due_date_only.strftime("%Y-%m-%d")
        next_bill_due_display = next_bill_due_date_only.strftime("%Y-%m-%d")
        
        # Check payment status
        if today_date < due_date_only:
            # Before due date - payment not due yet
            days_remaining = (due_date_only - today_date).days
            return False, f"🟢 ACTIVE - Payment not due yet. Due on {due_date_display}"
        elif today_date == due_date_only:
            # On due date - payment due today
            return False, f"🟡 DUE TODAY - Payment due today {due_date_display}"
        elif today_date <= next_bill_due_date_only:
            # Between due date and next bill due date (grace period)
            return False, f"🟠 GRACE PERIOD - Payment was due on {due_date_display}, final day to pay: {next_bill_due_display}"
        else:
            # After next bill due date (payment overdue)
            days_overdue = (today_date - next_bill_due_date_only).days
            return True, f"🔴 OVERDUE - Payment was due on {due_date_display}, overdue by {days_overdue} days"
    except Exception as e:
        print(f"❌ Error getting payment status: {e}")
        return False, "Error checking payment status"

def is_payment_overdue():
    """Check if payment is overdue - returns True if payment is overdue, False otherwise"""
    is_overdue, _ = get_payment_status_info()
    
    # If payment is overdue, trigger overdue actions
    if is_overdue:
        # Run overdue actions in a separate thread to avoid blocking
        import threading
        threading.Thread(target=lambda: asyncio.run(handle_payment_overdue_actions())).start()
    
    return is_overdue

# List of commands that are always allowed, even when payment is overdue
ALLOWED_COMMANDS = [
    "start",
    "help", 
    "payments", 
    "pay_razer",
    "done",
    "cancel",
    "total_messages"
]

def payment_required(func):
    """Decorator to check if payment is overdue before executing a command"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        command = update.message.text.split()[0][1:] if update.message and update.message.text else ""
        
        # Check if command is in the allowed list
        if command.lower() in ALLOWED_COMMANDS:
            return await func(update, context)
        
        # Check if user is in the middle of a payment process (awaiting customer details)
        # In this case, allow the message to pass through even if payment is overdue
        if notify_users.get(chat_id, {}).get("awaiting_customer_details", False):
            return await func(update, context)
        
        # Check if payment is overdue
        if is_payment_overdue():
            username = update.effective_user.username if update.effective_user else "unknown"
            chat_type = update.effective_chat.type if update.effective_chat else "private"
            log_message("RECEIVED", chat_id, username, chat_type, update.message.text if update.message else "")
            
            response_message = (
                "🔒 *Payment Required*\n\n"
                "Your payment is overdue. Most commands are locked until payment is made.\n\n"
                "Please use the following commands:\n"
                "• /start - Basic bot information\n"
                "• /payments - View payment details\n"
                "• /pay\\_razer - Make a payment via Razorpay\n"
                "• /done - Verify payment completion\n"
                "• /cancel - Cancel an ongoing payment process\n"
                "• /help - Show available commands\n"
                "• /total\\_messages - View message statistics"
            )
            
            await update.message.reply_text(response_message, parse_mode='Markdown')
            log_message("SENT", chat_id, "", "private", response_message)
            return
        
        # If payment is not overdue, execute the command
        return await func(update, context)
    
    return wrapper

async def handle_payment_overdue_actions():
    """Handle actions when payment is overdue - stop bot, close positions, cancel orders"""
    try:
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        
        # Read current payment data
        with open(payments_file, 'r', encoding='utf-8') as f:
            payment_data = json.load(f)
        
        # Check if bot is already force stopped
        if payment_data.get("bot_force_stopped", False):
            return
        
        # Get current positions and orders from the trading system
        positions_to_close = []
        orders_to_cancel = []
        
        if SERVER_CALL_AVAILABLE:
            try:
                # Get current bot status
                bot_status = server_call.get_bot_status()
                
                # If bot is running, we need to handle positions first
                if bot_status.get('running', False):
                    print("🚨 Payment is overdue - initiating bot shutdown process...")
                    
                    # Check if there are any open positions
                    try:
                        # Import bot state to check current positions
                        import sys
                        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                        from utils.bot_state import get_position, get_active_buy_order, get_active_sell_order
                        
                        current_position = get_position()
                        active_buy = get_active_buy_order()
                        active_sell = get_active_sell_order()
                        
                        # Log current trading state
                        print(f"Current position: {current_position}")
                        print(f"Active buy order: {active_buy}")
                        print(f"Active sell order: {active_sell}")
                        
                        # If there are open positions, wait for them to close naturally
                        if current_position in ["LONG", "SHORT"]:
                            print(f"⏳ Waiting for {current_position} position to close naturally...")
                            positions_to_close.append(current_position)
                        
                        # If there are active orders, they will be cancelled when bot stops
                        if active_buy:
                            orders_to_cancel.append(f"BUY - {active_buy}")
                        if active_sell:
                            orders_to_cancel.append(f"SELL - {active_sell}")
                        
                    except Exception as e:
                        print(f"❌ Error checking bot state: {e}")
                    
                    # Stop the bot
                    result = server_call.control_bot_stop()
                    print(f"🛑 Bot stopped due to payment overdue: {result}")
                    
                    # Mark bot as force stopped
                    payment_data["bot_force_stopped"] = True
                    payment_data["positions_to_close"] = positions_to_close
                    payment_data["orders_to_cancel"] = orders_to_cancel
                    
                    # Save updated payment data
                    with open(payments_file, 'w', encoding='utf-8') as f:
                        json.dump(payment_data, f, indent=2)
                    
                    print("🚨 Trading bot stopped due to payment overdue")
                    print("🔒 All trading commands are now blocked until payment is made")
                    
            except Exception as e:
                print(f"❌ Error handling payment overdue actions: {e}")
                
    except Exception as e:
        print(f"❌ Error in handle_payment_overdue_actions: {e}")

async def handle_payment_restoration():
    """Handle actions when payment is restored - restart bot if needed"""
    try:
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        
        # Read current payment data
        with open(payments_file, 'r', encoding='utf-8') as f:
            payment_data = json.load(f)
        
        # Check if bot was force stopped
        if payment_data.get("bot_force_stopped", False):
            # Reset the force stopped flag
            payment_data["bot_force_stopped"] = False
            payment_data["positions_to_close"] = []
            payment_data["orders_to_cancel"] = []
            
            # Save updated payment data
            with open(payments_file, 'w', encoding='utf-8') as f:
                json.dump(payment_data, f, indent=2)
            
            print("✅ Payment restored - bot can be restarted")
            
    except Exception as e:
        print(f"❌ Error in handle_payment_restoration: {e}")

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    
    # Initialize or load payment_cycle.json file for payment history
    payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
    
    # Initialize or load payments.json file first to get payment_cycle_days
    payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
    if not os.path.exists(payments_file) or os.path.getsize(payments_file) == 0:
        # Create default payments file
        payment_data = {
            "server_cost": 550,
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
        # Create default payment_cycle.json with just payment history
        payment_cycle = {
            "payment_history": []
        }
        with open(payment_cycle_file, 'w', encoding='utf-8') as f:
            json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
        print(f"✅ Created payment_cycle.json file with empty payment history")
    else:
        # Payment cycle file exists, check if it has payment_history
        try:
            with open(payment_cycle_file, 'r', encoding='utf-8') as f:
                payment_cycle = json.load(f)
                
            # Ensure payment_history exists
            if "payment_history" not in payment_cycle:
                payment_cycle = {
                    "payment_history": []
                }
                
            # Remove any fields that should be in payments.json instead
            keys_to_remove = ["last_payment_date", "next_bill_date", "due_date", 
                             "next_bill_due_date", "payment_cycle_days", "positions_to_close", 
                             "orders_to_cancel", "bot_force_stopped"]
            for key in keys_to_remove:
                if key in payment_cycle:
                    payment_cycle.pop(key)
                
            with open(payment_cycle_file, 'w', encoding='utf-8') as f:
                json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Error initializing payment_cycle.json: {e}")
            
    # Make sure the QR code directory exists
    qr_dir = os.path.join(os.path.dirname(__file__), 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)
    
    # Initialize or create temp directory for payment screenshots
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
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
    print("   /pay_razer, /done")
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
    application.add_handler(CommandHandler("pay_razer", pay_razer_command))  # Razerpay payment command
    application.add_handler(CommandHandler("done", done_command))  # Command to verify payment
    application.add_handler(CommandHandler("cancel", cancel_command))  # Command to cancel payment process
    
    # Add message handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, payment_required(handle_message)))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    print("🚀 Bot is starting...")
    print("💡 Send /start to begin!")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

def calculate_message_cost_for_cycle():
    """Calculate the total message cost for the current payment cycle"""
    try:
        # Get payment information
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        chat_messages_file = os.path.join(os.path.dirname(__file__), 'chat_messages.json')
        
        # Load payments data
        if not os.path.exists(payments_file):
            print("❌ Payments file not found")
            return 0
            
        with open(payments_file, 'r', encoding='utf-8') as f:
            payments_data = json.load(f)
        
        # Get cycle parameters
        last_payment_date_str = payments_data.get("last_payment_date", "")
        next_bill_date_str = payments_data.get("next_bill_date", "")
        per_message_cost = payments_data.get("per_message_cost", 1)
        
        if not last_payment_date_str or not next_bill_date_str:
            print("❌ Missing payment cycle dates")
            return 0
        
        # Convert dates to datetime objects
        last_payment_date = string_to_ist(last_payment_date_str)
        next_bill_date = string_to_ist(next_bill_date_str)
        
        # Reset time components to compare only dates
        cycle_start_date = last_payment_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
        cycle_end_date = next_bill_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
        
        print(f"Calculating message cost from {cycle_start_date} to {cycle_end_date}")
        
        # Count all messages for all users in the cycle - since this is for all users
        cycle_message_count = 0
        
        # Use our common function to count messages for all chat IDs
        try:
            with open(chat_messages_file, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            
            messages = chat_data.get("messages", [])
            unique_chat_ids = set(str(msg.get("chat_id")) for msg in messages if "chat_id" in msg)
            
            # Sum up messages for each chat_id
            for chat_id in unique_chat_ids:
                user_messages, _, _, _, _, _ = count_messages_for_date_range(
                    chat_id, cycle_start_date, cycle_end_date
                )
                cycle_message_count += user_messages
                
        except Exception as e:
            print(f"❌ Error counting messages in calculate_message_cost_for_cycle: {e}")
            # If there's an error with the common function, fall back to simple counting
            if os.path.exists(chat_messages_file):
                try:
                    with open(chat_messages_file, 'r', encoding='utf-8') as f:
                        chat_data = json.load(f)
                    
                    messages = chat_data.get("messages", [])
                    
                    # Count messages within the current payment cycle
                    for message in messages:
                        try:
                            if "timestamp" in message:
                                message_timestamp = string_to_ist(message.get("timestamp", ""))
                                message_date = message_timestamp.date()
                            else:
                                message_date = datetime.strptime(message.get("date", "1970-01-01"), '%Y-%m-%d').date()
                            
                            if cycle_start_date <= message_date < cycle_end_date:
                                cycle_message_count += 1
                        except (ValueError, TypeError) as e:
                            print(f"❌ Error processing message date in cost calculation: {e}")
                            continue
                except Exception as inner_e:
                    print(f"❌ Error in fallback message counting: {inner_e}")
        
        # Calculate total message cost for the cycle
        total_message_cost = cycle_message_count * per_message_cost
        
        # Update payments.json with the calculated message cost
        payments_data["message_monthly_cost"] = total_message_cost
        
        with open(payments_file, 'w', encoding='utf-8') as f:
            json.dump(payments_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Message cost calculated for cycle: {cycle_message_count} messages × ₹{per_message_cost} = ₹{total_message_cost}")
        return total_message_cost
        
    except Exception as e:
        print(f"❌ Error calculating message cost for cycle: {e}")
        return 0

def get_total_cycle_cost():
    """Calculate the total cost for the current payment cycle"""
    try:
        # First, calculate and update the message cost
        message_cost = calculate_message_cost_for_cycle()
        
        # Load payments data
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        
        if not os.path.exists(payments_file):
            print("❌ Payments file not found")
            return 0
            
        with open(payments_file, 'r', encoding='utf-8') as f:
            payments_data = json.load(f)
        
        # Calculate total cost
        server_cost = payments_data.get("server_cost", 0)
        support_cost = payments_data.get("support_cost", 0)
        message_monthly_cost = payments_data.get("message_monthly_cost", 0)
        
        total_cost = server_cost + support_cost + message_monthly_cost
        
        print(f"📊 Total cycle cost breakdown:")
        print(f"   Server cost: ₹{server_cost}")
        print(f"   Support cost: ₹{support_cost}")
        print(f"   Message cost: ₹{message_monthly_cost}")
        print(f"   Total: ₹{total_cost}")
        
        return total_cost
        
    except Exception as e:
        print(f"❌ Error calculating total cycle cost: {e}")
        return 0

def ensure_payment_cycle_completeness():
    """
    Ensure that payments.json has all required fields.
    This will add any missing fields needed for proper operation.
    """
    try:
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        if not os.path.exists(payments_file) or os.path.getsize(payments_file) == 0:
            print("❌ Payments file not found or empty. Cannot fix.")
            return False
            
        # Load the current payment data
        with open(payments_file, 'r', encoding='utf-8') as f:
            payment_data = json.load(f)
        
        updated = False
        
        # Check for required fields
        if 'last_payment_date' not in payment_data:
            # If there's no last payment date, set it to now - payment_cycle_days
            now = get_ist_now()
            cycle_days = payment_data.get('payment_cycle_days', 28)
            last_payment_date = now - timedelta(days=cycle_days)
            payment_data['last_payment_date'] = last_payment_date.isoformat()
            updated = True
            print(f"✅ Added missing last_payment_date to payments: {last_payment_date.isoformat()}")
        else:
            # Convert to IST datetime object
            last_payment_date = string_to_ist(payment_data['last_payment_date'])
        
        # Make sure payment_cycle_days exists
        if 'payment_cycle_days' not in payment_data:
            payment_data['payment_cycle_days'] = 28
            updated = True
            print("✅ Added default payment_cycle_days (28) to payments")
            
        cycle_days = payment_data['payment_cycle_days']
        
        # Check for due_date and add if missing
        if 'due_date' not in payment_data:
            next_bill_date = last_payment_date + timedelta(days=cycle_days)
            due_date = next_bill_date - timedelta(days=1)
            payment_data['due_date'] = due_date.isoformat()
            updated = True
            print(f"✅ Added missing due_date to payments: {due_date.isoformat()}")
        
        # Check for next_bill_date and add if missing
        if 'next_bill_date' not in payment_data:
            next_bill_date = last_payment_date + timedelta(days=cycle_days)
            payment_data['next_bill_date'] = next_bill_date.isoformat()
            updated = True
            print(f"✅ Added missing next_bill_date to payments: {next_bill_date.isoformat()}")
        
        # Check for next_bill_due_date and add if missing
        if 'next_bill_due_date' not in payment_data:
            if 'next_bill_date' in payment_data:
                next_bill_date = string_to_ist(payment_data['next_bill_date'])
                next_bill_due_date = next_bill_date + timedelta(days=1)
                payment_data['next_bill_due_date'] = next_bill_due_date.isoformat()
                updated = True
                print(f"✅ Added missing next_bill_due_date to payments: {next_bill_due_date.isoformat()}")
        
        # Initialize other required fields
        if 'positions_to_close' not in payment_data:
            payment_data['positions_to_close'] = []
            updated = True
        
        if 'orders_to_cancel' not in payment_data:
            payment_data['orders_to_cancel'] = []
            updated = True
            
        if 'bot_force_stopped' not in payment_data:
            payment_data['bot_force_stopped'] = False
            updated = True
        
        # Save updates if needed
        if updated:
            with open(payments_file, 'w', encoding='utf-8') as f:
                json.dump(payment_data, f, indent=2, ensure_ascii=False)
            print("✅ Payments file updated successfully")
            return True
            
        return False
            
    except Exception as e:
        print(f"❌ Error ensuring payment data completeness: {e}")
        return False


# Call this function before using payment cycle
def main():
    """Main entry point for the Telegram Bot"""
    # Initialize payment cycle if needed
    ensure_payment_cycle_completeness()
    
    # Continue with normal initialization
    try:
        # Initialize or load payment_cycle.json file for payment history
        payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
        
        # Initialize or load payments.json file first to get payment_cycle_days
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        if not os.path.exists(payments_file) or os.path.getsize(payments_file) == 0:
            # Create default payments file
            payment_data = {
                "server_cost": 550,
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
            # Create default payment_cycle.json with just payment history
            payment_cycle = {
                "payment_history": []
            }
            with open(payment_cycle_file, 'w', encoding='utf-8') as f:
                json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
            print(f"✅ Created payment_cycle.json file with empty payment history")
        else:
            # Payment cycle file exists, check if it has payment_history
            try:
                with open(payment_cycle_file, 'r', encoding='utf-8') as f:
                    payment_cycle = json.load(f)
                
                # Ensure payment_history exists
                if "payment_history" not in payment_cycle:
                    payment_cycle = {
                        "payment_history": []
                    }
                
                # Remove any fields that should be in payments.json instead
                keys_to_remove = ["last_payment_date", "next_bill_date", "due_date", 
                                 "next_bill_due_date", "payment_cycle_days", "positions_to_close", 
                                 "orders_to_cancel", "bot_force_stopped"]
                for key in keys_to_remove:
                    if key in payment_cycle:
                        payment_cycle.pop(key)
                
                with open(payment_cycle_file, 'w', encoding='utf-8') as f:
                    json.dump(payment_cycle, f, indent=2, ensure_ascii=False)
                
            except Exception as e:
                print(f"❌ Error initializing payment_cycle.json: {e}")
        
        # Make sure the QR code directory exists
        qr_dir = os.path.join(os.path.dirname(__file__), 'qr_codes')
        os.makedirs(qr_dir, exist_ok=True)
        
        # Initialize or create temp directory for payment screenshots
        temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
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
        print("   /pay_razer, /done")
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
        application.add_handler(CommandHandler("pay_razer", pay_razer_command))  # Razerpay payment command
        application.add_handler(CommandHandler("done", done_command))  # Command to verify payment
        application.add_handler(CommandHandler("cancel", cancel_command))  # Command to cancel payment process
        
        # Add message handler for non-command messages
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, payment_required(handle_message)))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        print("🚀 Bot is starting...")
        print("💡 Send /start to begin!")
        
        # Run the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
        # Calculate the message cost for the current cycle
        calculate_message_cost_for_cycle()
    except Exception as e:
        print(f"❌ Error in main initialization: {e}")
