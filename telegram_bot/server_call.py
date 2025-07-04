import requests
from dotenv import load_dotenv
import os

load_dotenv()

base_url = "http://localhost:8000"  # Replace with your FastAPI server URL

def control_bot_start():
    """
    Control the trading bot: 1 for start, 0 for stop
    """
    url = f"{base_url}/bot/control"
    response = requests.post(url, json={"action": 1})

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to control bot: {response.text}")


def control_bot_stop():
    """
    Control the trading bot: 1 for start, 0 for stop
    """
    url = f"{base_url}/bot/control"
    response = requests.post(url, json={"action": 0})

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to control bot: {response.text}")
    

def get_bot_status():
    """
    Check if the trading bot is running
    """
    url = f"{base_url}/bot/status"
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get bot status: {response.text}")
    
def get_historical_order_book():
    """
    Get historical order book data
    """
    url = f"{base_url}/order_book/historical"
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get historical order book: {response.text}")

def get_current_order_book():
    """
    Get current order book snapshot
    """
    url = f"{base_url}/order_book/last_update"
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get order book snapshot: {response.text}")

def get_qrcode(amount: int, message: str, save_path=None):
    """
    Get QR code for the bot, decode base64 from API, and save it as an image file.
    
    Args:
        amount: Payment amount
        message: Payment reference code
        save_path: Path to save QR code image (defaults to telegram_bot/qr_codes/upi_qr_code.png if None)
    """
    if save_path is None:
        # Use the default path in telegram_bot/qr_codes
        qr_dir = os.path.join(os.path.dirname(__file__), 'qr_codes')
        os.makedirs(qr_dir, exist_ok=True)
        save_path = os.path.join(qr_dir, "upi_qr_code.png")
    payee = os.getenv("Payment_NAME_ID")
    url = f"{base_url}/gpay/generate_qr"
    response = requests.get(url, params={
        "payee_vpa": payee,
        "message": message,
        "amount": str(amount)  # amount must be string as per OpenAPI
    })

    if response.status_code == 200:
        data = response.json()
        if "image_base64" in data:
            import base64
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(data["image_base64"]))
            return f"QR code saved to {save_path}"
        else:
            return data
    else:
        try:
            return response.json()
        except Exception:
            raise Exception(f"Failed to get QR code: {response.text}")

def photo_scanner(image_path: str):
    """
    Scan a photo and return the text.
    """
    url = f"{base_url}/gpay/scan_image"
    with open(image_path, "rb") as f:
        files = {'file': f}
        response = requests.post(url, files=files)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to scan photo: {response.text}")

def update_trading_config(
    last_payment_date=None,
    first_payment_made=None,
    reminder_sent=None,
    service_active=None,
    symbol_name=None,
    sell_long_offset=None,
    buy_long_offset=None,
    quantity=None,
    quantity_type=None,
    quantity_percentage=None,
    candle_interval=None
):
    """
    Update trading_config.json with only the provided fields.
    """
    url = f"{base_url}/trading_config/update"
    payload = {}
    if last_payment_date is not None:
        payload["last_payment_date"] = last_payment_date
    if first_payment_made is not None:
        payload["first_payment_made"] = first_payment_made
    if reminder_sent is not None:
        payload["reminder_sent"] = reminder_sent
    if service_active is not None:
        payload["service_active"] = service_active
    if symbol_name is not None:
        payload["symbol_name"] = symbol_name
    if sell_long_offset is not None:
        payload["sell_long_offset"] = sell_long_offset
    if buy_long_offset is not None:
        payload["buy_long_offset"] = buy_long_offset
    if quantity is not None:
        payload["quantity"] = quantity
    if quantity_type is not None:
        payload["quantity_type"] = quantity_type
    if quantity_percentage is not None:
        payload["quantity_percentage"] = quantity_percentage
    if candle_interval is not None:
        payload["candle_interval"] = candle_interval

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            error_message = f"Failed to update trading config: {response.text}"
            print(f"ERROR: {error_message}")
            raise Exception(error_message)
    except requests.exceptions.ConnectionError as e:
        error_message = f"Connection error while updating trading config: {str(e)}"
        print(f"ERROR: {error_message}")
        raise Exception(error_message)
    except Exception as e:
        error_message = f"Unexpected error while updating trading config: {str(e)}"
        print(f"ERROR: {error_message}")
        raise Exception(error_message)

def get_latest_update():
    """
    Get the latest filled order (last item in the data list from the API).
    Returns a dict with a 'filled_orders' key containing a list with the latest order (or empty list).
    """
    url = f"{base_url}/order_book/latest_update"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        orders = data.get("data", [])
        latest = orders[-1:]  # last item as a list, or empty list
        return {"filled_orders": latest}
    else:
        raise Exception(f"Failed to get latest update: {response.text}")