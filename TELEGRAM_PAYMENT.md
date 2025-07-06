# Telegram Bot and Payment Integration Documentation

This document provides detailed information about the Telegram bot integration and the Razorpay payment system implemented in the Binance Trading Bot.

## Telegram Bot Overview

The Telegram bot serves as a user interface for the trading bot, allowing users to:
- Control the trading bot remotely
- Check trading status and account balances
- Manage subscription payments
- Receive trading notifications and alerts

## Bot Architecture

The Telegram bot consists of several components:

1. **Main Bot Module** (`telegram_bot/bot.py`):
   - Handles Telegram API interactions
   - Processes user commands
   - Manages user sessions and states
   - Routes requests to appropriate handlers

2. **Server Communication** (`telegram_bot/server_call.py`):
   - Connects the Telegram bot to the main trading bot
   - Sends control commands to the trading engine
   - Retrieves status and performance information

3. **Payment Processing** (`telegram_bot/razerpay.py`):
   - Integrates with Razorpay API
   - Creates and verifies payment links
   - Manages subscription cycles
   - Stores customer information

## Payment System Implementation

### Payment Flow

1. **Subscription Request**:
   - User requests subscription through Telegram
   - Bot collects necessary customer information
   - Bot generates a payment link with detailed breakdown

2. **Payment Processing**:
   - User completes payment through Razorpay interface
   - Razorpay processes the transaction
   - Razorpay sends webhooks/notifications upon completion

3. **Verification and Activation**:
   - Bot verifies payment status with Razorpay API
   - Upon successful verification, subscription is activated
   - Payment details are stored for records

4. **Subscription Management**:
   - Bot tracks subscription expiration dates
   - Sends reminders for upcoming renewals
   - Manages service access based on subscription status

### Razorpay Integration

The integration with Razorpay is handled through the `razerpay.py` module, which provides the following functionality:

#### Customer Management

```python
def save_customer_details(chat_id, name=None, email=None, phone=None):
    """
    Save customer details to a JSON file for future use
    """
    # Implementation details...

def get_customer_details(chat_id):
    """
    Get customer details from JSON file
    """
    # Implementation details...

def clear_customer_details(chat_id):
    """
    Clear customer details for a specific chat_id from the JSON file
    """
    # Implementation details...
```

These functions manage customer information in the `customer_details.json` file, storing:
- Customer name
- Email address
- Phone number

This information is used when creating Razorpay payment links and for customer identification.

#### Payment Link Generation

```python
def create_payment_link_with_breakdown(
    pricing_file="telegram_bot/payments.json",
    customer_name=None,
    customer_email=None,
    customer_phone=None
):
    """
    Creates a Razorpay payment link and returns detailed pricing breakdown.
    """
    # Implementation details...
```

This function:
1. Loads pricing information from `payments.json`
2. Calculates the detailed cost breakdown:
   - Server costs
   - Messaging costs
   - Support costs
   - Processing fees
   - GST/taxes
   - Additional charges
3. Creates a payment link through Razorpay API
4. Returns the payment link along with the breakdown details

#### Payment Tracking

```python
def save_payment_link_info(chat_id, payment_info):
    """
    Save payment link info to track pending payments
    """
    # Implementation details...

def get_payment_info_by_chat_id(chat_id):
    """
    Get the most recent payment info for a chat ID
    """
    # Implementation details...

def get_payment_info_by_id(payment_id):
    """
    Get payment info by payment ID
    """
    # Implementation details...

def clear_payment_link_info(chat_id):
    """
    Clear payment link info for a specific chat_id
    """
    # Implementation details...
```

These functions manage payment link information in the `payment_links.json` file, tracking:
- Payment link associations with users
- Payment details and amounts
- Timestamps of link creation
- Payment IDs for verification

#### Payment Verification

```python
def check_payment_status(payment_link_id):
    """
    Check the status of a payment link
    """
    # Implementation details...

def verify_payment_and_update_cycle(payment_link_id):
    """
    Verify payment status and update payment cycle if paid
    """
    # Implementation details...
```

These functions:
1. Check payment status with Razorpay API
2. Verify successful payments
3. Update the payment cycle information when payments are confirmed
4. Update the bot's service activation status

#### Subscription Cycle Management

```python
def is_payment_allowed(chat_id=None):
    """
    Check if payment is allowed based on the current date and due date
    """
    # Implementation details...
```

This function manages the subscription cycle by:
1. Checking the current payment due date
2. Determining if a new payment is allowed/required
3. Providing information about days remaining or days overdue

### Payment Cycle Logic

The payment cycle is managed through the `payment_cycle.json` file and includes:

1. **Cycle Definition**:
   - Default cycle length: 28 days
   - Grace period: 1 day after due date
   - Configurable through `payment_cycle_days` parameter

2. **Key Dates**:
   - `last_payment_date`: When the last payment was made
   - `next_bill_date`: When the next payment will be due
   - `due_date`: When the payment must be made (typically 1 day before next_bill_date)
   - `next_bill_due_date`: Final deadline including grace period

3. **Payment History**:
   - Tracks all payments in a historical record
   - Includes payment dates, amounts, and status
   - Maintains audit trail for billing disputes

### Late Payment Handling

The system handles late payments through:

1. **Grace Period**: Short period after the due date where service remains active
2. **Service Restrictions**: Gradual limitations imposed on overdue accounts
3. **Notification System**: Automated reminders about upcoming and overdue payments
4. **Reactivation Logic**: Process for restoring service after late payment

## Environment and API Key Management

The Razorpay integration supports both test and production environments:

```python
# Use test keys if MODE is 'test', live keys otherwise
if MODE_ENV in ['test', 'true']:
    api_key = os.getenv("RAZORPAY_TEST_API_KEY")
    api_secret = os.getenv("RAZORPAY_TEST_API_SECRET")
else:
    api_key = os.getenv("RAZORPAY_API_KEY")
    api_secret = os.getenv("RAZORPAY_API_SECRET")
```

This allows:
1. Testing the payment flow in a sandbox environment
2. Seamless transition to production without code changes
3. Separate credentials for test and live environments

## Security Considerations

The payment integration implements several security measures:

1. **API Key Protection**:
   - Keys stored in environment variables, not in code
   - Different keys for test and production environments

2. **Data Storage**:
   - Customer information stored locally, not transmitted unnecessarily
   - Payment details saved only for verification purposes

3. **Verification Checks**:
   - Multiple verification steps for payment confirmation
   - Reconciliation with Razorpay records before activating service

4. **Error Handling**:
   - Graceful handling of API failures
   - Fallback mechanisms for connectivity issues
   - Detailed error logging for troubleshooting

## Payment Pricing Structure

The default pricing structure includes:

1. **Server Cost**: Base fee for hosting and maintaining the trading bot
2. **Message Monthly Cost**: Fee for Telegram message notifications
3. **Support Cost**: Fee for technical support and assistance
4. **Processing Fee**: 2% transaction fee
5. **GST on Processing Fee**: 18% tax on the processing fee
6. **Additional Charges**: Fixed additional charges

This structure is defined in `payments.json` and can be customized as needed.

## Telegram Bot Commands

The Telegram bot typically supports the following commands:

- `/start`: Initialize the bot and get welcome message
- `/subscribe`: Start the subscription process
- `/status`: Check subscription status
- `/balance`: Check trading account balance
- `/positions`: View current trading positions
- `/history`: View trading history
- `/help`: Get help information
- `/settings`: Configure bot settings
- `/pay`: Generate a new payment link
- `/verify`: Verify payment status
- `/support`: Contact support

## Implementation Recommendations

When implementing or extending the Telegram bot and payment system:

1. **Error Handling**:
   - Implement comprehensive error handling for API calls
   - Provide clear error messages to users
   - Log detailed error information for debugging

2. **User Experience**:
   - Keep payment flows simple and straightforward
   - Provide clear breakdowns of costs
   - Send confirmation messages at each step

3. **Security**:
   - Validate all user inputs
   - Implement proper authentication
   - Protect sensitive information

4. **Testing**:
   - Test thoroughly in the Razorpay sandbox environment
   - Verify webhook handling
   - Test edge cases like payment failures

5. **Documentation**:
   - Document the payment flow for users
   - Provide clear instructions for setup
   - Include troubleshooting information

## Conclusion

The Telegram bot and Razorpay integration provide a complete subscription management system for the Binance Trading Bot. By following this documentation, you can understand, implement, and extend the payment functionality to meet your specific requirements.
