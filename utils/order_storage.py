import os
import json
import datetime
from typing import Dict, List, Any, Optional

# Define paths for JSON files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
ORDER_BOOK_FILE = os.path.join(DATA_DIR, 'order_book.json')

def ensure_data_dir_exists():
    """Ensure the data directory exists"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def load_json_file(file_path: str) -> List[Dict[str, Any]]:
    """Load data from a JSON file, return empty list if file doesn't exist"""
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_json_file(file_path: str, data: List[Dict[str, Any]]):
    """Save data to a JSON file"""
    ensure_data_dir_exists()
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def load_filled_orders() -> List[Dict[str, Any]]:
    """Load all filled orders from order_book.json"""
    return load_json_file(ORDER_BOOK_FILE)


def filter_filled_orders(
    symbol: Optional[str] = None,
    time_interval: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Filter filled orders based on symbol, time interval, and date range.
    
    Args:
        symbol: Trading pair symbol (e.g., 'ETHUSDT')
        time_interval: Candle interval (e.g., '1m', '5m', '15m', '1h')
        start_date: Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        end_date: End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        
    Returns:
        List of filled orders matching the filter criteria
    """
    filled_orders = load_filled_orders()
    filtered_orders = []
    
    # Parse date strings if provided
    start_datetime = None
    end_datetime = None
    
    if start_date:
        # Handle date-only format by appending time if needed
        if 'T' not in start_date:
            start_date = f"{start_date}T00:00:00"
        start_datetime = datetime.datetime.fromisoformat(start_date)
    
    if end_date:
        # Handle date-only format by appending time if needed
        if 'T' not in end_date:
            end_date = f"{end_date}T23:59:59"
        end_datetime = datetime.datetime.fromisoformat(end_date)
    
    for order in filled_orders:
        # Skip non-filled orders
        if order.get('status') != 'FILLED':
            continue
        
        # Apply symbol filter if specified
        if symbol:
            # Check both in the main order data and in the meta.additional_info
            order_symbol = order.get('symbol')
            if not order_symbol:
                meta = order.get('meta', {})
                additional_info = meta.get('additional_info', {})
                order_symbol = additional_info.get('symbol')
            
            if not order_symbol or order_symbol.upper() != symbol.upper():
                continue
        
        # Apply time interval filter if specified
        if time_interval:
            order_interval = order.get('meta', {}).get('time_interval')
            if not order_interval or order_interval != time_interval:
                continue
        
        # Apply date range filter if specified
        if start_datetime or end_datetime:
            # Try multiple date fields in order of preference
            date_str = None
            for field in ['saved_at', 'meta.recorded_at', 'updateTime', 'time']:
                if field == 'meta.recorded_at':
                    date_str = order.get('meta', {}).get('recorded_at')
                else:
                    date_str = order.get(field)
                
                if date_str:
                    break
            
            if not date_str:
                # Skip orders without date information when filtering by date
                continue
            
            try:
                order_date = datetime.datetime.fromisoformat(date_str) if isinstance(date_str, str) else datetime.datetime.fromtimestamp(int(date_str)/1000)
                
                if start_datetime and order_date < start_datetime:
                    continue
                
                if end_datetime and order_date > end_datetime:
                    continue
            except (ValueError, TypeError):
                # Skip orders with invalid date format when filtering by date
                continue
        
        # If all filters pass, add to filtered list
        filtered_orders.append(order)
    
    return filtered_orders


def save_filled_order(order_details: Dict[str, Any]):
    """
    Save a filled order to order_book.json
    This will append the order to the existing list without replacing any orders
    """
    # Only save orders that are actually filled
    if order_details.get('status') != 'FILLED':
        return
    
    # Add timestamp for when the order was saved
    order_details['saved_at'] = datetime.datetime.now().isoformat()
    
    # Load existing filled orders
    filled_orders = load_filled_orders()
    
    # Add the new order (always append, never replace)
    filled_orders.append(order_details)
    
    # Save back to file
    save_json_file(ORDER_BOOK_FILE, filled_orders)


def save_open_order(order_details: Dict[str, Any]):
    """
    This function no longer saves open orders, but still exists for compatibility.
    Only filled orders are saved now.
    """
    pass


def remove_open_order(order_id: str) -> Optional[Dict[str, Any]]:
    """
    This function no longer removes open orders, but still exists for compatibility.
    """
    return None


def enrich_order_details(order_details: Dict[str, Any], 
                         order_type: str,
                         position_side: str,
                         filled_price: Optional[float] = None,
                         additional_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Enrich order details with additional information
    
    Args:
        order_details: The original order details
        order_type: The type of order ('BUY' or 'SELL')
        position_side: The position side ('LONG' or 'SHORT')
        filled_price: The price at which the order was filled (if applicable)
        additional_info: Additional information to include
        
    Returns:
        Enriched order details
    """
    # Import here to avoid circular imports
    from utils.config import CANDLE_INTERVAL
    
    enriched = order_details.copy()
    
    # Add metadata
    enriched['meta'] = {
        'order_type': order_type,
        'position_side': position_side,
        'recorded_at': datetime.datetime.now().isoformat(),
        'time_interval': CANDLE_INTERVAL  # Add the candle interval information
    }
    
    # Add filled price if provided
    if filled_price is not None:
        enriched['meta']['filled_price'] = filled_price
    
    # Add any additional info
    if additional_info:
        enriched['meta'].update(additional_info)
    
    return enriched
