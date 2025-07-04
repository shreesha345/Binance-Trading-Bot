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
