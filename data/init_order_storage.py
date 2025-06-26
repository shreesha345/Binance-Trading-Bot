#!/usr/bin/env python
# Initialize order storage JSON files

import os
import json
import sys

# Add parent directory to path to allow importing from utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.order_storage import DATA_DIR, ORDER_BOOK_FILE

def init_order_storage():
    """Initialize order storage JSON files"""
    # Ensure data directory exists
    if not os.path.exists(DATA_DIR):
        print(f"Creating data directory: {DATA_DIR}")
        os.makedirs(DATA_DIR)
    
    # Initialize order_book.json if it doesn't exist
    if not os.path.exists(ORDER_BOOK_FILE):
        print(f"Creating order_book.json: {ORDER_BOOK_FILE}")
        with open(ORDER_BOOK_FILE, 'w') as f:
            json.dump([], f, indent=2)
    
    print("Order storage initialization complete")

if __name__ == "__main__":
    init_order_storage()
