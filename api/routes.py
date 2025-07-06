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
# Add PnL analyzer imports
from utils.pnl_analyzer import BinanceFuturesPnLTracker
from utils.config import BINANCE_API_KEY, BINANCE_API_SECRET, TEST
from datetime import datetime

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
    quantity_type: Any = Field(default=None)
    quantity_percentage: Any = Field(default=None)
    price_value: Any = Field(default=None)
    leverage: Any = Field(default=None)
    candle_interval: Any = Field(default=None)

@router.post("/trading_config/update")
def update_trading_config(req: TradingConfigUpdateRequest):
    """
    Update trading_config.json with only the provided fields. Unspecified fields remain unchanged.
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'trading_config.json')
    if not os.path.exists(config_path):
        log_api(f"Error: trading_config.json not found at {config_path}")
        return JSONResponse(content={"error": "trading_config.json not found"}, status_code=404)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
        except Exception as e:
            log_api(f"Error parsing trading_config.json: {str(e)}")
            return JSONResponse(content={"error": "Invalid JSON in trading_config.json"}, status_code=500)
    
    update_data = req.dict(exclude_unset=True)
    
    # Log the received update data
    log_api(f"Updating trading config with: {update_data}")
    
    # Apply updates
    for k, v in update_data.items():
        if v is not None:
            config[k] = v
    
    # Write the updated config back to the file
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
    
    log_api(f"Trading config updated successfully")
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

class PnLAnalysisRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = 30

@router.post("/pnl/analyze")
def analyze_pnl(req: PnLAnalysisRequest):
    """
    Analyze PnL for a specific date range or number of days.
    Does not save data to a JSON file - only returns the data for display.
    """
    try:
        tracker = BinanceFuturesPnLTracker(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=TEST)
        
        # Validate date inputs if provided
        if (req.start_date and not req.end_date) or (not req.start_date and req.end_date):
            log_api("Error: Both start_date and end_date must be provided together.")
            return JSONResponse(
                status_code=400,
                content={"error": "Both start_date and end_date must be provided together."}
            )
        
        # Get trading stats
        stats = tracker.get_trading_stats(
            days=req.days,
            start_date=req.start_date,
            end_date=req.end_date
        )
        
        # Get daily PnL breakdown
        daily_pnl = tracker.get_daily_pnl(
            days=req.days if not req.start_date else req.days,
            start_date=req.start_date,
            end_date=req.end_date
        )
        
        # Convert DataFrame to dict for JSON serialization
        daily_pnl_dict = {}
        if not daily_pnl.empty:
            daily_pnl_dict = daily_pnl.reset_index().to_dict(orient='records')
        
        response_data = {
            "trading_stats": stats,
            "daily_pnl": daily_pnl_dict,
            "timestamp": datetime.now().isoformat()
        }
        
        log_api(f"PnL analysis completed for period: {req.start_date or f'Last {req.days} days'} to {req.end_date or 'now'}")
        return response_data
        
    except Exception as e:
        log_api(f"Error analyzing PnL: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to analyze PnL: {str(e)}"}
        )

@router.get("/order_book/filter")
def filter_order_book(
    symbol: Optional[str] = None, 
    interval: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Returns filtered filled orders from order_book.json based on:
    - symbol: Trading pair symbol (e.g., 'ETHUSDT')
    - interval: Candle interval (e.g., '1m', '5m', '15m', '1h')
    - start_date: Filter orders after this date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    - end_date: Filter orders before this date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    """
    from utils.order_storage import filter_filled_orders
    
    # Log the API request
    filters = []
    if symbol:
        filters.append(f"symbol={symbol}")
    if interval:
        filters.append(f"interval={interval}")
    if start_date:
        filters.append(f"start_date={start_date}")
    if end_date:
        filters.append(f"end_date={end_date}")
    
    filter_str = ", ".join(filters) if filters else "no filters"
    log_api(f"Filtered order book requested with {filter_str}")
    
    # Get filtered orders
    filtered_orders = filter_filled_orders(
        symbol=symbol,
        time_interval=interval,
        start_date=start_date,
        end_date=end_date
    )
    
    return {"filled_orders": filtered_orders, "count": len(filtered_orders)}

@router.get("/order_book/export")
def export_order_book(
    filename: str,
    symbol: Optional[str] = None, 
    interval: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Exports filtered filled orders to a JSON file in the data directory.
    
    Parameters:
    - filename: Name of the file to export to (will be saved in data directory)
    - symbol: Trading pair symbol (e.g., 'ETHUSDT')
    - interval: Candle interval (e.g., '1m', '5m', '15m', '1h')
    - start_date: Filter orders after this date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    - end_date: Filter orders before this date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    """
    from utils.order_storage import filter_filled_orders, DATA_DIR
    import os
    
    # Validate filename to prevent directory traversal attacks
    if os.path.sep in filename or '..' in filename:
        return JSONResponse(
            content={"error": "Invalid filename. Must not contain path separators or parent directory references"}, 
            status_code=400
        )
    
    # Ensure the filename has a .json extension
    if not filename.lower().endswith('.json'):
        filename += '.json'
    
    # Create the full output path in the data directory
    output_path = os.path.join(DATA_DIR, filename)
    
    # Get filtered orders
    filtered_orders = filter_filled_orders(
        symbol=symbol,
        time_interval=interval,
        start_date=start_date,
        end_date=end_date
    )
    
    # Save to file
    try:
        with open(output_path, 'w') as f:
            json.dump(filtered_orders, f, indent=2)
    except Exception as e:
        log_api(f"Error exporting orders to {output_path}: {str(e)}")
        return JSONResponse(content={"error": f"Failed to export orders: {str(e)}"}, status_code=500)
    
    # Log the export
    filters = []
    if symbol:
        filters.append(f"symbol={symbol}")
    if interval:
        filters.append(f"interval={interval}")
    if start_date:
        filters.append(f"start_date={start_date}")
    if end_date:
        filters.append(f"end_date={end_date}")
    
    filter_str = ", ".join(filters) if filters else "no filters"
    log_api(f"Exported {len(filtered_orders)} orders with {filter_str} to {output_path}")
    
    return {
        "success": True,
        "filename": filename,
        "path": output_path,
        "count": len(filtered_orders),
        "filters": {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date
        }
    }
