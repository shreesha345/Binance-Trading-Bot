from fastapi import UploadFile, File
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from utils.logger import log_api
import logging
from fastapi.responses import JSONResponse, FileResponse
import os
import json
from typing import Optional, Any, Dict
from pydantic import Field
import base64
import tempfile

router = APIRouter()

class UvicornInterceptHandler(logging.Handler):
    def emit(self, record):
        from utils.logger import log_api
        try:
            msg = self.format(record)
            log_api(f"[uvicorn] {msg}")
        except Exception:
            pass

# Intercept uvicorn logs and store in api.log
logging.getLogger("uvicorn").addHandler(UvicornInterceptHandler())
logging.getLogger("uvicorn.error").addHandler(UvicornInterceptHandler())
logging.getLogger("uvicorn.access").addHandler(UvicornInterceptHandler())

class BotControlRequest(BaseModel):
    action: int  # 1 for start, 0 for stop

@router.post("/bot/control")
def control_bot(req: BotControlRequest):
    """
    Control the trading bot: 1=start, 0=stop
    """
    from main import start_bot, stop_bot
    if req.action == 1:
        started = start_bot()
        log_api("Bot start requested via API. Status: {}".format("started" if started else "already running"))
        return {"status": "started" if started else "already running"}
    elif req.action == 0:
        stopped = stop_bot()
        log_api("Bot stop requested via API. Status: {}".format("stopped" if stopped else "already stopped"))
        return {"status": "stopped" if stopped else "already stopped"}
    else:
        log_api("Invalid action requested via API: {}".format(req.action))
        return {"status": "invalid action"}

@router.get("/bot/status")
def bot_status():
    """
    Check if the trading bot is running
    """
    from main import is_bot_running
    running = is_bot_running()
    log_api("Bot status checked via API. Running: {}".format(running))
    return {"running": running}

@router.get("/order_book/historical")
def order_book_historical():
    """
    Returns all filled orders from order_book.json.
    """
    order_book_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'order_book.json')
    if not os.path.exists(order_book_path) or os.path.getsize(order_book_path) == 0:
        return JSONResponse(content={"message": "order_book.json not found or empty"}, status_code=204)
    with open(order_book_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception:
            return JSONResponse(content={"error": "Invalid JSON in order_book.json"}, status_code=500)
    # Only return filled orders (assuming a 'status' field with value 'FILLED')
    filled_orders = [order for order in data if order.get('status') == 'FILLED'] if isinstance(data, list) else []
    return {"filled_orders": filled_orders}

# For last_update, keep track of last sent mtime in memory
last_sent_mtime: Optional[float] = None
last_sent_data: Optional[dict] = None

@router.get("/order_book/last_update")
def order_book_last_update():
    """
    Returns only the latest filled order from order_book.json.
    """
    order_book_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'order_book.json')
    if not os.path.exists(order_book_path) or os.path.getsize(order_book_path) == 0:
        return JSONResponse(content={"filled_orders": []}, status_code=204)
    with open(order_book_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception:
            return JSONResponse(content={"error": "Invalid JSON in order_book.json"}, status_code=500)
    # Only consider filled orders
    filled_orders = [order for order in data if order.get('status') == 'FILLED'] if isinstance(data, list) else []
    if not filled_orders:
        return {"filled_orders": []}
    # Get the latest order by orderId or recorded_at
    def get_order_sort_key(order):
        meta = order.get("meta", {})
        return (
            int(order.get("orderId", 0)),
            str(order.get("saved_at") or meta.get("recorded_at") or "")
        )
    latest = max(filled_orders, key=get_order_sort_key)
    return {"filled_orders": [latest]}


@router.get("/gpay/generate_qr")
def generate_qr_api(payee_vpa: str, message: str, amount: str):
    """
    Generate a UPI QR code and return the image as a base64 string.
    The image is not stored in the payments folder.
    """
    from utils.gpay_parser import generate_upi_qr
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        temp_path = tmp.name
    try:
        generate_upi_qr(payee_vpa, message, amount, temp_path)
        with open(temp_path, "rb") as img_file:
            b64_string = base64.b64encode(img_file.read()).decode("utf-8")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    return {"image_base64": b64_string}

@router.post("/gpay/scan_image")
def scan_gpay_image_api(file: UploadFile = File(...)):
    """
    Scan a GPay payment screenshot and extract payment details.
    """
    import tempfile
    from utils.gpay_parser import parse_gpay_payment_from_image
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        result = parse_gpay_payment_from_image(tmp_path)
        # result is a JSON string, so parse it before returning
        import json as _json
        parsed = _json.loads(result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        os.remove(tmp_path)
    return JSONResponse(content=parsed)

class TradingConfigUpdateRequest(BaseModel):
    last_payment_date: Any = Field(default=None)
    first_payment_made: Any = Field(default=None)
    reminder_sent: Any = Field(default=None)
    service_active: Any = Field(default=None)
    symbol_name: Any = Field(default=None)
    sell_long_offset: Any = Field(default=None)
    buy_long_offset: Any = Field(default=None)
    quantity: Any = Field(default=None)
    candle_interval: Any = Field(default=None)

@router.post("/trading_config/update")
def update_trading_config(req: TradingConfigUpdateRequest):
    """
    Update trading_config.json with only the provided fields. Unspecified fields remain unchanged.
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'trading_config.json')
    if not os.path.exists(config_path):
        return JSONResponse(content={"error": "trading_config.json not found"}, status_code=404)
    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
        except Exception:
            return JSONResponse(content={"error": "Invalid JSON in trading_config.json"}, status_code=500)
    update_data = req.dict(exclude_unset=True)
    for k, v in update_data.items():
        if v is not None:
            config[k] = v
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
    return {"status": "success", "updated_config": config}

@router.get("/trading_config")
def get_trading_config():
    """
    Get the current trading_config.json contents.
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'trading_config.json')
    if not os.path.exists(config_path):
        return JSONResponse(content={"error": "trading_config.json not found"}, status_code=404)
    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
        except Exception:
            return JSONResponse(content={"error": "Invalid JSON in trading_config.json"}, status_code=500)
    return config
