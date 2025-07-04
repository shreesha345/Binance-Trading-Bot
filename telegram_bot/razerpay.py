import os
import json
import base64
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz

# Define path for customer details file
CUSTOMER_DETAILS_FILE = os.path.join(os.path.dirname(__file__), 'customer_details.json')
PAYMENT_LINKS_FILE = os.path.join(os.path.dirname(__file__), 'payment_links.json')

def save_customer_details(chat_id, name=None, email=None, phone=None):
    """
    Save customer details to a JSON file for future use
    """
    # Create the file if it doesn't exist
    if not os.path.exists(CUSTOMER_DETAILS_FILE):
        with open(CUSTOMER_DETAILS_FILE, 'w') as f:
            json.dump({"customers": {}}, f, indent=2)
    
    # Load existing data
    try:
        with open(CUSTOMER_DETAILS_FILE, 'r') as f:
            customer_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        customer_data = {"customers": {}}
    
    # Update customer details
    chat_id_str = str(chat_id)
    if chat_id_str not in customer_data["customers"]:
        customer_data["customers"][chat_id_str] = {}
    
    # Only update fields that are provided
    if name:
        customer_data["customers"][chat_id_str]["name"] = name
    if email:
        customer_data["customers"][chat_id_str]["email"] = email
    if phone:
        customer_data["customers"][chat_id_str]["phone"] = phone
    
    # Save the updated data
    with open(CUSTOMER_DETAILS_FILE, 'w') as f:
        json.dump(customer_data, f, indent=2)
    
    return True

def get_customer_details(chat_id):
    """
    Get customer details from JSON file
    """
    if not os.path.exists(CUSTOMER_DETAILS_FILE):
        return None
    
    try:
        with open(CUSTOMER_DETAILS_FILE, 'r') as f:
            customer_data = json.load(f)
        
        chat_id_str = str(chat_id)
        return customer_data.get("customers", {}).get(chat_id_str)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

def clear_customer_details(chat_id):
    """
    Clear customer details for a specific chat_id from the JSON file
    Returns True if something was cleared, False otherwise
    """
    if not os.path.exists(CUSTOMER_DETAILS_FILE):
        return False
    
    try:
        with open(CUSTOMER_DETAILS_FILE, 'r') as f:
            customer_data = json.load(f)
        
        chat_id_str = str(chat_id)
        if chat_id_str in customer_data.get("customers", {}):
            # Check if there was actual data to clear
            had_data = bool(customer_data.get("customers", {}).get(chat_id_str))
            
            # Remove the customer details
            customer_data["customers"].pop(chat_id_str, None)
            
            # Save the updated data
            with open(CUSTOMER_DETAILS_FILE, 'w') as f:
                json.dump(customer_data, f, indent=2)
            return had_data
        return False
    except (json.JSONDecodeError, FileNotFoundError):
        return False

def save_payment_link_info(chat_id, payment_info):
    """
    Save payment link info to track pending payments
    """
    # Create the file if it doesn't exist
    if not os.path.exists(PAYMENT_LINKS_FILE):
        with open(PAYMENT_LINKS_FILE, 'w') as f:
            json.dump({"payments": {}}, f, indent=2)
    
    # Load existing data
    try:
        with open(PAYMENT_LINKS_FILE, 'r') as f:
            payment_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        payment_data = {"payments": {}}
    
    # Update payment info
    chat_id_str = str(chat_id)
    
    # Add timestamp to payment info
    payment_info["timestamp"] = datetime.now().isoformat()
    payment_info["chat_id"] = chat_id
    
    # Save by payment ID for easy lookup
    payment_id = payment_info.get("breakdown", {}).get("payment_id")
    if payment_id:
        if "by_id" not in payment_data:
            payment_data["by_id"] = {}
        payment_data["by_id"][payment_id] = payment_info
    
    # Save by chat ID to track user's most recent payment
    if "by_chat_id" not in payment_data:
        payment_data["by_chat_id"] = {}
    payment_data["by_chat_id"][chat_id_str] = payment_info
    
    # Save the updated data
    with open(PAYMENT_LINKS_FILE, 'w') as f:
        json.dump(payment_data, f, indent=2)
    
    return True

def get_payment_info_by_chat_id(chat_id):
    """
    Get the most recent payment info for a chat ID
    """
    if not os.path.exists(PAYMENT_LINKS_FILE):
        return None
    
    try:
        with open(PAYMENT_LINKS_FILE, 'r') as f:
            payment_data = json.load(f)
        
        chat_id_str = str(chat_id)
        return payment_data.get("by_chat_id", {}).get(chat_id_str)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

def get_payment_info_by_id(payment_id):
    """
    Get payment info by payment ID
    """
    if not os.path.exists(PAYMENT_LINKS_FILE):
        return None
    
    try:
        with open(PAYMENT_LINKS_FILE, 'r') as f:
            payment_data = json.load(f)
        
        return payment_data.get("by_id", {}).get(payment_id)
    except (json.JSONDecodeError, FileNotFoundError):
        return None

def clear_payment_link_info(chat_id):
    """
    Clear payment link info for a specific chat_id from the payment_links.json file
    Returns True if something was cleared, False otherwise
    """
    if not os.path.exists(PAYMENT_LINKS_FILE):
        return False
    
    try:
        with open(PAYMENT_LINKS_FILE, 'r') as f:
            payment_data = json.load(f)
        
        chat_id_str = str(chat_id)
        something_cleared = False
        
        # Get payment ID for this chat ID
        payment_info = payment_data.get("by_chat_id", {}).get(chat_id_str)
        if payment_info and "breakdown" in payment_info:
            payment_id = payment_info.get("breakdown", {}).get("payment_id")
            if payment_id and payment_id in payment_data.get("by_id", {}):
                # Remove the payment info by ID
                payment_data["by_id"].pop(payment_id, None)
                something_cleared = True
        
        # Remove the payment info by chat ID
        if chat_id_str in payment_data.get("by_chat_id", {}):
            payment_data["by_chat_id"].pop(chat_id_str, None)
            something_cleared = True
            
        # Save the updated data
        with open(PAYMENT_LINKS_FILE, 'w') as f:
            json.dump(payment_data, f, indent=2)
        return something_cleared
    except (json.JSONDecodeError, FileNotFoundError):
        return False

def create_payment_link_with_breakdown(
    pricing_file="telegram_bot/payments.json",
    customer_name=None,
    customer_email=None,
    customer_phone=None
):
    """
    Creates a Razorpay payment link and returns detailed pricing breakdown.
    """
    load_dotenv()
    api_key = os.getenv("RAZORPAY_API_KEY")
    api_secret = os.getenv("RAZORPAY_API_SECRET")

    if not api_key or not api_secret:
        return {"status": "error", "message": "Missing Razorpay API credentials"}

    # Load pricing details
    try:
        with open(pricing_file, "r") as f:
            pricing_data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"Failed to load pricing data: {e}"}

    # Extract values safely
    server_cost = pricing_data.get("server_cost", 0)
    message_monthly_cost = pricing_data.get("message_monthly_cost", 0)
    support_cost = pricing_data.get("support_cost", 0)

    total_amount = server_cost + message_monthly_cost + support_cost
    amount_in_paisa = total_amount * 100

    # Prepare detailed breakdown
    breakdown = {
        "Server Cost": server_cost,
        "Message Monthly Cost": message_monthly_cost,
        "Support Cost": support_cost,
        "Total": total_amount,
        "amount": total_amount
    }

    # Prepare Razorpay payload
    reference_id = f"telegram_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    # Prepare detailed payment description (compact for Razorpay field)
    # Description breakdown for multiline display
    description_lines = [
        f"SERVER      : ₹{server_cost}",
        f"MESSAGING   : ₹{message_monthly_cost}",
        f"SUPPORT     : ₹{support_cost}",
    ]
    compact_description = "TELEGRAM BOT SERVICES\n" + "\n".join(description_lines)

    # Razorpay payload with detailed description
    payload = {
        "amount": amount_in_paisa,
        "currency": "INR",
        "description": compact_description,
        "reference_id": reference_id,
        "expire_by": int((datetime.now() + timedelta(days=30)).timestamp()),
        "reminder_enable": True,
        "notes": {
            "Server Cost": f"₹{server_cost}",
            "Messaging": f"₹{message_monthly_cost}",
            "Support": f"₹{support_cost}"
        }
    }

    # Optional customer fields
    if customer_phone and len(set(customer_phone.replace("+91", "").replace(" ", ""))) >= 3:
        payload["customer"] = {}
        if customer_name:
            payload["customer"]["name"] = customer_name
        if customer_email:
            payload["customer"]["email"] = customer_email
        payload["customer"]["contact"] = customer_phone

    # Make API call
    auth_str = f"{api_key}:{api_secret}".encode("ascii")
    headers = {
        "Authorization": "Basic " + base64.b64encode(auth_str).decode("ascii"),
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://api.razorpay.com/v1/payment_links",
            json=payload,
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            # Add payment_id to breakdown
            breakdown["payment_id"] = data["id"]
            return {
                "status": "success",
                "payment_link": data["short_url"],
                "amount": total_amount,
                "breakdown": breakdown
            }
        else:
            return {
                "status": "error",
                "message": f"Razorpay API Error {response.status_code}",
                "details": response.text,
                "breakdown": breakdown
            }
    except Exception as e:
        return {"status": "error", "message": f"Request failed: {e}"}




def check_payment_status(payment_link_id):
    url = f"https://api.razorpay.com/v1/payment_links/{payment_link_id}"

    load_dotenv()
    api_key = os.getenv("RAZORPAY_API_KEY")
    api_secret = os.getenv("RAZORPAY_API_SECRET")

    if not api_key or not api_secret:
        return {"status": "error", "message": "Missing Razorpay API credentials"}

    
    try:
        response = requests.get(url, auth=HTTPBasicAuth(api_key, api_secret))
        data = response.json()
        
        if response.status_code == 200:
            status = data.get('status')
            paid = data.get('payment_status')  # Can be 'paid', 'unpaid', 'partial'
            return {
                'status': status,
                'payment_status': paid,
                'amount': data.get('amount') / 100,
                'description': data.get('description'),
                'customer': data.get('customer', {}).get('name'),
                'created_at': data.get('created_at'),
                'paid_at': data.get('paid_at'),
                'link': data.get('short_url')
            }
        else:
            return {'error': data}
    
    except Exception as e:
        return {'error': str(e)}


def verify_payment_and_update_cycle(payment_link_id):
    """
    Verify payment status and update payment cycle if paid
    
    Returns:
        dict: Status information with 'success' boolean and 'message' string
    """
    payment_status = check_payment_status(payment_link_id)
    
    if 'error' in payment_status:
        return {
            'success': False,
            'message': f"Error checking payment status: {payment_status['error']}",
            'status': payment_status
        }
    
    # Check if payment is complete
    if payment_status.get('status') == 'paid' or payment_status.get('payment_status') == 'paid':
        # Payment is successful, update payments.json and payment_cycle.json
        payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
        payment_cycle_file = os.path.join(os.path.dirname(__file__), 'payment_cycle.json')
        
        try:
            # Load current payment data
            if os.path.exists(payments_file):
                with open(payments_file, 'r') as f:
                    payment_data = json.load(f)
            else:
                payment_data = {
                    "server_cost": 4000,
                    "per_message_cost": 1,
                    "message_monthly_cost": 0,
                    "support_cost": 2000,
                    "payment_cycle_days": 28
                }
            
            # Load payment history file
            if os.path.exists(payment_cycle_file):
                with open(payment_cycle_file, 'r') as f:
                    payment_history = json.load(f)
            else:
                payment_history = {"payment_history": []}
            
            # Update payment information
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            payment_data['last_payment_date'] = now.isoformat()
            payment_data['first_payment_made'] = True
            payment_data['reminder_sent'] = False
            
            # Get payment cycle days (default 28 if not specified)
            payment_cycle_days = payment_data.get('payment_cycle_days', 28)
            
            # Calculate next bill date from the payment date (not from the original due date)
            # This ensures full payment cycle length regardless of when payment was made
            next_bill_date = now + timedelta(days=payment_cycle_days)
            payment_data['next_bill_date'] = next_bill_date.isoformat()
            
            # Calculate due date (1 day before the next bill date)
            # This gives users until the day before the next bill is due
            due_date = next_bill_date - timedelta(days=1)
            payment_data['due_date'] = due_date.isoformat()
            
            # Calculate next bill due date (1 day after next bill date for grace period)
            next_bill_due_date = next_bill_date + timedelta(days=1)
            payment_data['next_bill_due_date'] = next_bill_due_date.isoformat()
            
            # Save payment information
            payment_data['last_payment_amount'] = payment_status.get('amount', 0)
            payment_data['last_payment_id'] = payment_link_id
            payment_data['service_active'] = True
            
            # Reset overdue flags if payment is made
            payment_data['bot_force_stopped'] = False
            payment_data['positions_to_close'] = []
            payment_data['orders_to_cancel'] = []
            
            # Add to payment history in payment_cycle.json
            if 'payment_history' not in payment_history:
                payment_history['payment_history'] = []
            
            payment_history['payment_history'].append({
                'payment_date': now.isoformat(),
                'payment_id': payment_link_id,
                'amount': payment_status.get('amount', 0),
                'status': 'paid'
            })
            
            # Write updated payment data back to file
            with open(payments_file, 'w') as f:
                json.dump(payment_data, f, indent=2)
            
            # Write updated payment history back to file
            with open(payment_cycle_file, 'w') as f:
                json.dump(payment_history, f, indent=2)
            
            return {
                'success': True,
                'message': "Payment verified and payment cycle updated successfully",
                'status': payment_status,
                'next_bill_date': next_bill_date.strftime('%Y-%m-%d'),
                'due_date': due_date.strftime('%Y-%m-%d')
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"Error updating payment cycle: {str(e)}",
                'status': payment_status
            }
    else:
        # Payment not complete
        return {
            'success': False,
            'message': f"Payment not complete. Current status: {payment_status.get('status')}",
            'status': payment_status
        }

def is_payment_allowed(chat_id=None):
    """
    Check if payment is allowed based on the current date and due date
    
    Returns:
        tuple: (allowed, message) where allowed is a boolean and message explains why
    """
    payments_file = os.path.join(os.path.dirname(__file__), 'payments.json')
    
    try:
        # If payments file doesn't exist, allow payment (first time user)
        if not os.path.exists(payments_file):
            return (True, "First payment")
        
        # Load payment information
        with open(payments_file, 'r') as f:
            payment_data = json.load(f)
        
        # If due date is not set, allow payment
        if 'due_date' not in payment_data:
            return (True, "Due date not set")
        
        # Get IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        
        # Parse due date - ensure it's properly converted to IST
        due_date = datetime.fromisoformat(payment_data['due_date'])
        if due_date.tzinfo is None:
            due_date = ist.localize(due_date)
        
        # Get current date in IST
        current_date = datetime.now(ist)
        
        # Strip time components for date comparison
        due_date_only = due_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
        current_date_only = current_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
        
        # Check if current date is on or after due date
        if current_date_only >= due_date_only:
            days_overdue = (current_date_only - due_date_only).days
            if days_overdue == 0:
                return (True, "Payment is due today")
            else:
                return (True, f"Payment is due (overdue by {days_overdue} days)")
        else:
            days_until_due = (due_date_only - current_date_only).days
            return (False, f"Payment is not due yet. {days_until_due} days remaining until due date ({due_date_only.strftime('%Y-%m-%d')})")
    
    except Exception as e:
        # If there's an error, allow payment (fail-safe)
        print(f"Error in is_payment_allowed: {str(e)}")
        return (True, f"Error checking payment cycle: {str(e)}")


# Example usage
# if __name__ == "__main__":
#     # result = create_payment_link_with_breakdown(
#     #     customer_name="Jane Doe",
#     #     customer_email="jane@example.com",
#     #     customer_phone="+919812345678"
#     # )
#     # print(json.dumps(result, indent=2))
#     payment_link_id = "plink_Qp0o1POthbD5lY"  # Replace with your actual payment link ID
#     print(check_payment_status(payment_link_id))