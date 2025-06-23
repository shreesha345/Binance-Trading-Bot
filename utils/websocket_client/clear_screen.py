# Utility for clearing the terminal screen
import os

def clear_screen(debug_mode=False):
    """Clear the terminal screen unless in debug mode"""
    if not debug_mode:
        os.system('cls' if os.name == 'nt' else 'clear')
