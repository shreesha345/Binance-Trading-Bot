# Utility for clearing the terminal screen
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
