from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Optional

class BinanceFuturesPnLTracker:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        Initialize Binance Futures P&L Tracker
        
        Args:
            api_key (str): Binance API key
            api_secret (str): Binance API secret
            testnet (bool): True for testnet, False for mainnet
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Initialize Binance client
        self.client = Client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )
        
        print(f"Connected to Binance {'Testnet' if testnet else 'Mainnet'} Futures")
    
    def get_account_info(self) -> Dict:
        """Get futures account information"""
        try:
            account_info = self.client.futures_account()
            return account_info
        except BinanceAPIException as e:
            raise Exception(f"Failed to get account info: {e}")
    
    def get_account_balance(self) -> Dict:
        """Get futures account balance"""
        try:
            balance = self.client.futures_account_balance()
            return balance
        except BinanceAPIException as e:
            raise Exception(f"Failed to get account balance: {e}")
    
    def get_positions(self) -> List[Dict]:
        """Get all futures positions"""
        try:
            positions = self.client.futures_position_information()
            # Filter only positions with non-zero amounts
            active_positions = [pos for pos in positions if float(pos['positionAmt']) != 0]
            return active_positions
        except BinanceAPIException as e:
            raise Exception(f"Failed to get positions: {e}")
    
    def get_income_history(self, days: int = 30, income_type: str = None, 
                          start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """
        Get income history (realized P&L, funding fees, etc.)
        
        Args:
            days (int): Number of days to look back (ignored if start_date and end_date are provided)
            income_type (str): Type of income ('REALIZED_PNL', 'FUNDING_FEE', etc.)
            start_date (str, optional): Start date in 'YYYY-MM-DD' format
            end_date (str, optional): End date in 'YYYY-MM-DD' format
        """
        try:
            if start_date and end_date:
                # Parse provided date strings to datetime objects - force UTC timezone
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                # Set start time to beginning of day (00:00:00) UTC
                start_time = int(start_datetime.timestamp() * 1000)
                
                # Set end_date to end of day (23:59:59) UTC
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
                end_time = int(end_datetime.timestamp() * 1000)
                
                print(f"Fetching data from {start_datetime} to {end_datetime} (UTC)")
            else:
                # Use the days parameter as fallback
                end_time = int(datetime.now().timestamp() * 1000)
                start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            
            params = {
                'startTime': start_time,
                'endTime': end_time,
                'limit': 1000
            }
            
            if income_type:
                params['incomeType'] = income_type
            
            income_history = self.client.futures_income_history(**params)
            return income_history
        except BinanceAPIException as e:
            raise Exception(f"Failed to get income history: {e}")
    
    def get_trading_stats(self, days: int = 30, start_date: Optional[str] = None, 
                        end_date: Optional[str] = None) -> Dict:
        """
        Get comprehensive trading statistics
        
        Args:
            days (int): Number of days to look back (ignored if start_date and end_date are provided)
            start_date (str, optional): Start date in 'YYYY-MM-DD' format
            end_date (str, optional): End date in 'YYYY-MM-DD' format
        """
        try:
            # Get account info
            account_info = self.get_account_info()
            
            # Get positions
            positions = self.get_positions()
            
            # Get income history
            income_history = self.get_income_history(days, start_date=start_date, end_date=end_date)
            
            # Calculate P&L metrics
            total_wallet_balance = float(account_info['totalWalletBalance'])
            total_unrealized_pnl = float(account_info['totalUnrealizedProfit'])
            total_margin_balance = float(account_info['totalMarginBalance'])
            
            # Calculate realized P&L from income history
            realized_pnl = 0
            funding_fees = 0
            commission_fees = 0
            pnl_by_symbol = {}
            
            for income in income_history:
                amount = float(income['income'])
                symbol = income['symbol']
                income_type = income['incomeType']
                
                if income_type == 'REALIZED_PNL':
                    realized_pnl += amount
                    if symbol not in pnl_by_symbol:
                        pnl_by_symbol[symbol] = 0
                    pnl_by_symbol[symbol] += amount
                elif income_type == 'FUNDING_FEE':
                    funding_fees += amount
                elif income_type == 'COMMISSION':
                    commission_fees += amount
            
            # Position details
            position_details = []
            total_position_value = 0
            
            for pos in positions:
                position_amt = float(pos['positionAmt'])
                entry_price = float(pos['entryPrice'])
                mark_price = float(pos['markPrice'])
                unrealized_pnl = float(pos['unRealizedProfit'])
                
                position_value = abs(position_amt * mark_price)
                total_position_value += position_value
                
                position_details.append({
                    'symbol': pos['symbol'],
                    'side': 'LONG' if position_amt > 0 else 'SHORT',
                    'size': abs(position_amt),
                    'entry_price': entry_price,
                    'mark_price': mark_price,
                    'unrealized_pnl': unrealized_pnl,
                    'position_value': position_value,
                    'roe': (unrealized_pnl / (position_value / abs(position_amt) * abs(position_amt))) * 100 if position_value > 0 else 0
                })
            
            return {
                'account_summary': {
                    'total_wallet_balance': total_wallet_balance,
                    'total_margin_balance': total_margin_balance,
                    'total_unrealized_pnl': total_unrealized_pnl,
                    'available_balance': float(account_info['availableBalance']),
                    'total_position_value': total_position_value
                },
                'pnl_summary': {
                    'realized_pnl': realized_pnl,
                    'unrealized_pnl': total_unrealized_pnl,
                    'total_pnl': realized_pnl + total_unrealized_pnl,
                    'funding_fees': funding_fees,
                    'commission_fees': commission_fees,
                    'net_profit': realized_pnl + funding_fees - abs(commission_fees)
                },
                'positions': position_details,
                'pnl_by_symbol': pnl_by_symbol,
                'period': {
                    'days': days if not (start_date and end_date) else None,
                    'start_date': start_date,
                    'end_date': end_date
                },
                'timestamp': datetime.now().isoformat(),
                'testnet': self.testnet
            }
            
        except Exception as e:
            raise Exception(f"Failed to get trading stats: {e}")
    
    def get_daily_pnl(self, days: int = 7, start_date: Optional[str] = None, 
                      end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get daily P&L breakdown
        
        Args:
            days (int): Number of days to look back (ignored if start_date and end_date are provided)
            start_date (str, optional): Start date in 'YYYY-MM-DD' format
            end_date (str, optional): End date in 'YYYY-MM-DD' format
        """
        try:
            income_history = self.get_income_history(days, start_date=start_date, end_date=end_date)
            
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(income_history)
            # Convert timestamps to datetime and ensure UTC timezone
            df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
            df['income'] = df['income'].astype(float)
            
            # When using date range, make sure we're filtering by UTC dates
            if start_date and end_date:
                # Extract date only (without timezone conversion)
                df['date'] = df['time'].dt.date
                
                # Additional filtering to ensure exact date range match
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
            else:
                # Regular date extraction
                df['date'] = df['time'].dt.date
            
            # Group by date and income type
            daily_pnl = df.groupby(['date', 'incomeType'])['income'].sum().reset_index()
            daily_pnl_pivot = daily_pnl.pivot(index='date', columns='incomeType', values='income').fillna(0)
            
            return daily_pnl_pivot
            
        except Exception as e:
            raise Exception(f"Failed to get daily P&L: {e}")
    
    def print_pnl_report(self, days: int = 30, start_date: Optional[str] = None, 
                          end_date: Optional[str] = None):
        """
        Print comprehensive P&L report
        
        Args:
            days (int): Number of days to look back (ignored if start_date and end_date are provided)
            start_date (str, optional): Start date in 'YYYY-MM-DD' format
            end_date (str, optional): End date in 'YYYY-MM-DD' format
        """
        try:
            stats = self.get_trading_stats(days, start_date=start_date, end_date=end_date)
            
            print("=" * 60)
            print(f"BINANCE FUTURES P&L REPORT - {'TESTNET' if self.testnet else 'MAINNET'}")
            print("=" * 60)
            
            if stats['period']['start_date'] and stats['period']['end_date']:
                print(f"Period: {stats['period']['start_date']} to {stats['period']['end_date']} (UTC)")
            else:
                print(f"Period: Last {stats['period']['days']} days")
                
            print(f"Generated: {stats['timestamp']}")
            print()
            
            # Account Summary
            account = stats['account_summary']
            print("ACCOUNT SUMMARY:")
            print(f"  Total Wallet Balance: ${account['total_wallet_balance']:.2f}")
            print(f"  Total Margin Balance: ${account['total_margin_balance']:.2f}")
            print(f"  Available Balance: ${account['available_balance']:.2f}")
            print(f"  Total Position Value: ${account['total_position_value']:.2f}")
            print()
            
            # P&L Summary
            pnl = stats['pnl_summary']
            print("P&L SUMMARY:")
            print(f"  Realized P&L: ${pnl['realized_pnl']:.2f}")
            print(f"  Unrealized P&L: ${pnl['unrealized_pnl']:.2f}")
            print(f"  Total P&L: ${pnl['total_pnl']:.2f}")
            print(f"  Funding Fees: ${pnl['funding_fees']:.2f}")
            print(f"  Commission Fees: ${pnl['commission_fees']:.2f}")
            print(f"  Net Profit: ${pnl['net_profit']:.2f}")
            print()
            
            # Active Positions
            if stats['positions']:
                print("ACTIVE POSITIONS:")
                for pos in stats['positions']:
                    print(f"  {pos['symbol']} {pos['side']}:")
                    print(f"    Size: {pos['size']:.4f}")
                    print(f"    Entry Price: ${pos['entry_price']:.4f}")
                    print(f"    Mark Price: ${pos['mark_price']:.4f}")
                    print(f"    Unrealized P&L: ${pos['unrealized_pnl']:.2f}")
                    print(f"    ROE: {pos['roe']:.2f}%")
                    print()
            else:
                print("No active positions")
                print()
            
            # P&L by Symbol
            if stats['pnl_by_symbol']:
                print("REALIZED P&L BY SYMBOL:")
                for symbol, pnl_amount in stats['pnl_by_symbol'].items():
                    print(f"  {symbol}: ${pnl_amount:.2f}")
                print()
            
        except Exception as e:
            print(f"Error generating report: {e}")
    
    def save_pnl_data(self, filename: str = None, days: int = 30, 
                       start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        Save P&L data to JSON file
        Note: This method is only intended for direct use when running the pnl_analyzer.py 
        script and should not be called from the API or Telegram bot.
        
        Args:
            filename (str, optional): Output filename (auto-generated if None)
            days (int): Number of days to look back (ignored if start_date and end_date are provided)
            start_date (str, optional): Start date in 'YYYY-MM-DD' format
            end_date (str, optional): End date in 'YYYY-MM-DD' format
        """
        # Check if this is being called from the API route
        import inspect
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name
        caller_file = caller_frame.f_code.co_filename
        
        # Skip file saving if called from API routes or Telegram bot
        if 'routes.py' in caller_file or 'bot.py' in caller_file:
            print("File saving skipped when called from API or bot")
            return None
            
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                env = "testnet" if self.testnet else "mainnet"
                
                if start_date and end_date:
                    # Include date range in filename
                    start_str = start_date.replace('-', '')
                    end_str = end_date.replace('-', '')
                    filename = f"binance_futures_pnl_{env}_{start_str}_to_{end_str}_{timestamp}.json"
                else:
                    filename = f"binance_futures_pnl_{env}_{timestamp}.json"
            
            stats = self.get_trading_stats(days, start_date=start_date, end_date=end_date)
            
            with open(filename, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            
            print(f"P&L data saved to {filename}")
            return filename
            
        except Exception as e:
            print(f"Error saving data: {e}")
            
        except Exception as e:
            print(f"Error saving data: {e}")


def main():
    """Example usage"""
    import argparse
    
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Binance Futures PnL Analyzer')
    parser.add_argument('--days', type=int, default=30, help='Number of days to look back (default: 30)')
    parser.add_argument('--start-date', type=str, help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, help='End date in YYYY-MM-DD format')
    args = parser.parse_args()
    
    try:
        # Import configuration from config file
        from config import BINANCE_API_KEY, BINANCE_API_SECRET, TEST
        
        API_KEY = BINANCE_API_KEY
        API_SECRET = BINANCE_API_SECRET
        USE_TESTNET = TEST
        
    except ImportError as e:
        print("Error importing config file!")
        print("Please make sure you have a config.py file with:")
        print("  BINANCE_API_KEY = 'your_api_key'")
        print("  BINANCE_API_SECRET = 'your_api_secret'")
        print("  TEST = True  # or False for mainnet")
        print(f"Error details: {e}")
        return
    except Exception as e:
        print(f"Error loading config: {e}")
        return
    
    if not API_KEY or not API_SECRET:
        print("Please set your API credentials in config.py!")
        return
    
    try:
        # Initialize tracker
        tracker = BinanceFuturesPnLTracker(API_KEY, API_SECRET, testnet=USE_TESTNET)
        
        # Validate date inputs if provided
        if (args.start_date and not args.end_date) or (not args.start_date and args.end_date):
            print("Error: Both --start-date and --end-date must be provided together.")
            return
        
        if args.start_date and args.end_date:
            print("Note: Binance API uses UTC timezone for all timestamps.")
            print(f"Analyzing data for period {args.start_date} to {args.end_date} (UTC timezone)")
            print()
            
        # Print comprehensive report
        tracker.print_pnl_report(days=args.days, start_date=args.start_date, end_date=args.end_date)
        
        # Save data to file
        tracker.save_pnl_data(days=args.days, start_date=args.start_date, end_date=args.end_date)
        
        # Get daily P&L breakdown
        print("DAILY P&L BREAKDOWN:")
        daily_pnl = tracker.get_daily_pnl(days=7 if not args.start_date else args.days, 
                                         start_date=args.start_date, end_date=args.end_date)
        print(daily_pnl)
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure your API key and secret are correct")
        print("2. Ensure your API key has futures trading permissions")
        print("3. Check if you're using the correct environment (testnet/mainnet)")
        print("4. Verify your API key is not restricted by IP")


if __name__ == "__main__":
    main()