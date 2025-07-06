#!/usr/bin/env python
# Order storage utilities

import argparse
import os
import json
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to path to allow importing from utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.order_storage import (
    load_filled_orders,
    filter_filled_orders,
    save_json_file,
    ORDER_BOOK_FILE,
    DATA_DIR
)

def view_orders(filled=False, open_orders=False, symbol=None, time_interval=None, start_date=None, end_date=None):
    """
    View orders from order_book.json with optional filtering
    
    Args:
        filled: Display filled orders (always True for backward compatibility)
        open_orders: Display open orders (not used, for backward compatibility)
        symbol: Filter by trading symbol (e.g., 'ETHUSDT')
        time_interval: Filter by time interval (e.g., '1m', '5m', '15m', '1h')
        start_date: Filter by start date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        end_date: Filter by end date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    """
    if symbol or time_interval or start_date or end_date:
        orders = filter_filled_orders(symbol, time_interval, start_date, end_date)
        filter_description = []
        if symbol:
            filter_description.append(f"Symbol: {symbol}")
        if time_interval:
            filter_description.append(f"Interval: {time_interval}")
        if start_date:
            filter_description.append(f"From: {start_date}")
        if end_date:
            filter_description.append(f"To: {end_date}")
        
        filter_str = ", ".join(filter_description)
        print(f"\n=== FILTERED FILLED ORDERS ({len(orders)} orders) ===")
        print(f"Filters: {filter_str}")
    else:
        orders = load_filled_orders()
        print(f"\n=== FILLED ORDERS IN ORDER BOOK ({len(orders)} orders) ===")
    
    for i, order in enumerate(orders, 1):
        print(f"\nOrder {i}/{len(orders)}:")
        print(f"  Order ID: {order.get('orderId')}")
        print(f"  Symbol: {order.get('symbol', order.get('meta', {}).get('additional_info', {}).get('symbol', 'Unknown'))}")
        print(f"  Type: {order.get('meta', {}).get('order_type')}")
        print(f"  Side: {order.get('side')} / {order.get('meta', {}).get('position_side')}")
        print(f"  Status: {order.get('status')}")
        price = order.get('meta', {}).get('filled_price', order.get('avgPrice', order.get('price')))
        print(f"  Price: {price}")
        print(f"  Time Interval: {order.get('meta', {}).get('time_interval', 'N/A')}")
        print(f"  Saved At: {order.get('saved_at')}")

def clear_orders(filled=False, open_orders=False):
    """Clear orders from order_book.json"""
    print(f"Clearing all orders from {ORDER_BOOK_FILE}")
    save_json_file(ORDER_BOOK_FILE, [])
    print("Done. All orders have been cleared.")

def init_files():
    """Initialize order storage files"""
    from data.init_order_storage import init_order_storage
    init_order_storage()

def add_test_orders():
    """Add test orders to verify storage functionality"""
    from utils.order_storage import save_filled_order, save_open_order, enrich_order_details
    import datetime
    
    # Create test orders
    test_orders = [
        {
            "orderId": 12345,
            "symbol": "ETHUSDT",
            "side": "BUY",
            "price": "2450.00",
            "stopPrice": "2449.00",
            "status": "FILLED",
            "executedQty": "1.0",
            "origQty": "1.0"
        },
        {
            "orderId": 12346,
            "symbol": "ETHUSDT",
            "side": "SELL",
            "price": "2480.00",
            "stopPrice": "2479.00",
            "status": "FILLED",
            "executedQty": "1.0",
            "origQty": "1.0"
        }
    ]
    
    # Save test filled orders
    for i, order in enumerate(test_orders):
        enriched = enrich_order_details(
            order,
            order_type='BUY' if i == 0 else 'SELL',
            position_side='LONG',
            filled_price=float(order['price']),
            additional_info={
                'symbol': order['symbol'],
                'test_order': True,
                'timestamp': datetime.datetime.now().isoformat()
            }
        )
        save_filled_order(enriched)
        print(f"Added test filled order: {order['orderId']}")
    
    print("\nTest orders added successfully. Use --view to see them.")

def print_filter_examples():
    """
    Print examples of how to use the filtering functionality
    """
    print("\n=== FILTER EXAMPLES ===")
    print("Filter by symbol:")
    print("  python -m utils.order_storage_utils --view --symbol ETHUSDT")
    print("\nFilter by time interval:")
    print("  python -m utils.order_storage_utils --view --interval 1m")
    print("\nFilter by date range:")
    print("  python -m utils.order_storage_utils --view --start 2025-07-01 --end 2025-07-06")
    print("\nCombine filters:")
    print("  python -m utils.order_storage_utils --view --symbol BTCUSDT --interval 5m --start 2025-07-01T09:00:00")
    print("\nExport filtered orders to a file:")
    print("  python -m utils.order_storage_utils --export filtered_orders.json --symbol ETHUSDT --interval 1m")
    print("\nAPI Usage:")
    print("  GET /order_book/filter?symbol=ETHUSDT&interval=1m&start_date=2025-07-01&end_date=2025-07-06")
    print("\n")

def export_filtered_orders(
    output_file: str,
    symbol: Optional[str] = None,
    time_interval: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Export filtered orders to a JSON file
    
    Args:
        output_file: Path to output file
        symbol: Filter by trading symbol
        time_interval: Filter by time interval
        start_date: Filter by start date
        end_date: Filter by end date
    """
    from utils.order_storage import filter_filled_orders
    
    # Get filtered orders
    filtered_orders = filter_filled_orders(
        symbol=symbol,
        time_interval=time_interval,
        start_date=start_date,
        end_date=end_date
    )
    
    # Generate export file path if not absolute
    if not os.path.isabs(output_file):
        output_file = os.path.join(DATA_DIR, output_file)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(filtered_orders, f, indent=2)
    
    # Build filter description
    filters = []
    if symbol:
        filters.append(f"symbol={symbol}")
    if time_interval:
        filters.append(f"interval={time_interval}")
    if start_date:
        filters.append(f"from={start_date}")
    if end_date:
        filters.append(f"to={end_date}")
    
    filter_str = ", ".join(filters) if filters else "no filters"
    print(f"\nExported {len(filtered_orders)} orders with {filter_str} to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Order storage utilities")
    parser.add_argument("--view", action="store_true", help="View filled orders in order_book.json")
    parser.add_argument("--clear", action="store_true", help="Clear all orders from order_book.json")
    parser.add_argument("--init", action="store_true", help="Initialize order storage files")
    parser.add_argument("--test", action="store_true", help="Add test orders for verification")
    parser.add_argument("--examples", action="store_true", help="Show examples of filtering usage")
    parser.add_argument("--export", type=str, help="Export filtered orders to specified file path")
    
    # Add arguments for filtering
    parser.add_argument("--symbol", type=str, help="Filter orders by symbol (e.g., 'ETHUSDT')")
    parser.add_argument("--interval", type=str, help="Filter orders by time interval (e.g., '1m', '5m', '15m', '1h')")
    parser.add_argument("--start", type=str, help="Filter orders from start date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    parser.add_argument("--end", type=str, help="Filter orders to end date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    
    args = parser.parse_args()
    
    if args.examples:
        print_filter_examples()
        return
    
    if args.init:
        init_files()
    
    if args.test:
        add_test_orders()
    
    if args.view:
        view_orders(
            symbol=args.symbol,
            time_interval=args.interval,
            start_date=args.start,
            end_date=args.end
        )
    
    if args.export:
        export_filtered_orders(
            output_file=args.export,
            symbol=args.symbol,
            time_interval=args.interval,
            start_date=args.start,
            end_date=args.end
        )
    
    if args.clear:
        clear_orders()
    
if __name__ == "__main__":
    main()
