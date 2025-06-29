import base64
from openai import OpenAI
from config import GEMINI_API_KEY
import os

def parse_gpay_payment_from_image(image_path):
    client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    # Function to encode the image
    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    # Check if the file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File not found at {image_path}. Please provide a valid image path.")
    base64_image = encode_image(image_path)

    json_formatter = """
    {
      "amount": "", // string: The transaction amount with currency symbol (e.g., "₹707")
      "date": "", // string: Transaction date in "DD MMM YYYY" format (e.g., "28 Jun 2025")
      "time": "", // string: Time of transaction in 12-hour format with AM/PM (e.g., "12:12 AM")
      "from": "", // string: Sender's name and UPI ID (e.g., "Name (Bank) - UPI ID")
      "to": "", // string: Recipient's name and UPI ID (e.g., "Name - UPI ID")
      "message": "", // string: Message or purpose associated with the transaction
      "upi_transaction_id": "", // string: Unique identifier for the UPI transaction
      "google_transaction_id": "" // string: Unique identifier assigned by Google Pay
    }
    """

    response = client.chat.completions.create(
        model="gemini-2.0-flash",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""You are a payment parser. Extract the payment details from the image below and provide ONLY the following JSON data:
                        - amount: The transaction amount with currency symbol (e.g., "₹707")
                        - date: Transaction date in "DD MMM YYYY" format (e.g., "28 Jun 2025")
                        - time: Time of transaction in 12-hour format with AM/PM (e.g., "12:12 AM")
                        - from: Sender's name and UPI ID (e.g., "Name (Bank) - UPI ID")
                        - to: Recipient's name and UPI ID (e.g., "Name - UPI ID")
                        - message: Message or purpose associated with the transaction it's in grey box
                        - upi_transaction_id: Unique identifier for the UPI transaction
                        - google_transaction_id: Unique identifier assigned by Google Pay

                        Format: {json_formatter}""",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
    )

    result = response.choices[0].message.content
    response_json = result.replace("```json", "").replace("```", "").strip()
    return response_json



import qrcode
import os

def generate_upi_qr(payee_vpa, message, amount, filename="upi_qr_code.png"):
    """
    Generates a UPI QR code and saves it to a file in the 'payments' folder at the project root.

    Args:
        payee_vpa (str): Payee UPI ID.
        message (str): Transaction message.
        amount (str or float): Amount to pay.
        filename (str): Output filename for the QR code image.
    """
    # Find the project root (where payments folder is expected)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    payments_dir = os.path.join(project_root, "payments")
    os.makedirs(payments_dir, exist_ok=True)
    file_path = os.path.join(payments_dir, filename)

    upi_url = (
        f"upi://pay?"
        f"pa={payee_vpa}"
        f"&tn={message.replace(' ', '%20')}"
        f"&am={amount}"
        f"&cu=INR"
    )
    qr = qrcode.make(upi_url)
    qr.save(file_path)
    qr.show()

# Example usage:
generate_upi_qr("shashikalaaithal97-1@okaxis", "EEREXXX", "1")


# response_json = parse_gpay_payment_from_image("C:\\D-drive\\binance_trading_bot\\payments\\image.png")

# print(response_json)