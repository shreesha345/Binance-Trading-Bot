#!/usr/bin/env python
# Order storage utilities

import argparse
import os
import json
import sys

# Add parent directory to path to allow importing from utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.order_storage import (
    load_filled_orders,
    save_json_file,
    ORDER_BOOK_FILE
)

def view_orders(filled=False, open_orders=False):
    """View orders from order_book.json"""
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

def main():
    parser = argparse.ArgumentParser(description="Order storage utilities")
    parser.add_argument("--view", action="store_true", help="View filled orders in order_book.json")
    parser.add_argument("--clear", action="store_true", help="Clear all orders from order_book.json")
    parser.add_argument("--init", action="store_true", help="Initialize order storage files")
    parser.add_argument("--test", action="store_true", help="Add test orders for verification")
    
    args = parser.parse_args()
    
    if args.init:
        init_files()
    
    if args.test:
        add_test_orders()
    
    if args.view:
        view_orders()
    
    if args.clear:
        clear_orders()
    
if __name__ == "__main__":
    main()
