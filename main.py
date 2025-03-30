import json
import requests
import re
import logging
import os
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "ProcessedMessages")  # DynamoDB table name

# API Endpoints
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Initialize DynamoDB client
dynamodb = boto3.client("dynamodb")

def lambda_handler(event, context):
    try:
        logger.info(f"🔍 Received event: {json.dumps(event, indent=2)}")
        
        # Parse incoming Telegram webhook payload
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", {})

        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()
        message_id = str(message.get("message_id"))  # Convert to string for DynamoDB

        if not chat_id or not text:
            logger.error("🚨 Missing chat_id or text!")
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid request"})}

        # Check if the message has already been processed
        if check_if_processed(message_id):
            logger.info(f"⚠️ Message ID {message_id} has already been processed. Skipping...")
            return {"statusCode": 200, "body": json.dumps({"message": "Already processed"})}

        # Mark message as processed in DynamoDB
        mark_as_processed(message_id)

        # Analyze expense using Gemini API
        analysis = analyze_expense(text)

        # **Apply proper formatting (Bold category, Italic message)**
        response_text = f"₹{analysis['amount']} marked under <b>{analysis['category']}</b> expenses. <i>{analysis['message']}</i>"

        # Send response as a reply to the user's message in a thread
        send_telegram_reply(chat_id, message_id, response_text)

        return {"statusCode": 200, "body": json.dumps({"message": "Processed successfully"})}

    except Exception as e:
        logger.error(f"🔥 Error processing request: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"message": "Internal Server Error"})}


def check_if_processed(message_id):
    """ Check DynamoDB if the message has already been processed """
    try:
        response = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={"message_id": {"S": message_id}}
        )
        return "Item" in response  # If item exists, return True
    except Exception as e:
        logger.error(f"⚠️ Error checking DynamoDB: {str(e)}")
        return False


def mark_as_processed(message_id):
    """ Mark a message as processed by storing it in DynamoDB """
    try:
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={"message_id": {"S": message_id}}
        )
        logger.info(f"✅ Marked message {message_id} as processed in DynamoDB.")
    except Exception as e:
        logger.error(f"⚠️ Error marking message in DynamoDB: {str(e)}")


def send_telegram_reply(chat_id, message_id, text):
    """ Sends a reply to the specific message in Telegram with proper formatting """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": message_id,  # Replying to the original message in a thread
        "parse_mode": "HTML"  # **Ensures proper formatting in Telegram**
    }

    logger.info(f"📤 Sending reply to Telegram: {payload}")  # Debugging payload

    try:
        response = requests.post(TELEGRAM_API_URL, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        
        logger.info(f"✅ Message sent successfully: {response.json()}")
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"⚠️ HTTP error occurred: {http_err} - Response: {response.text}")
    except Exception as e:
        logger.error(f"⚠️ Failed to send message: {str(e)}")

# Your other functions (analyze_expense, parse_gemini_response, etc.) remain unchanged

def analyze_expense(prompt):
    """ Calls Gemini API to analyze expense details """
    system_prompt = """You are a witty expense tracker assistant. Analyze the user's expense message and:

1. Extract numerical amount (support INR formats: ₹500, 5k, 1.5L etc.)
2. Determine category: Food, Beverages, Electronics, Fashion, Transport, Bills, Health, Education, Personal Care, Miscellaneous
3. Generate a friendly response message in English (20-30 words) with emojis.
4. Return JSON format: {"amount": number, "category": string, "message": string}

Example response for "Paid ₹899 for Vivo phone":
{"amount": 899, "category": "Electronics", "message": "New phone alert! 📱 You're going to love your new gadget!"}"""

    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nUser Input: {prompt}"}]
        }]
    }

    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=8
        )
        
        response.raise_for_status()
        
        result = response.json()
        
        response_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        
        return parse_gemini_response(response_text, prompt)
        
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return fallback_analysis(prompt)

def parse_gemini_response(response_text, original_prompt):
    """ Parses the response from Gemini API and ensures proper formatting """
    try:
        json_str = re.search(r'\{.*\}', response_text, re.DOTALL).group()
        data = json.loads(json_str)
        
        return {
            'amount': format_inr(data.get('amount', 0)),
            'category': data.get('category', 'Miscellaneous').title(),
            'message': data.get('message', 'Added to expenses! 💰')
        }
        
    except Exception as e:
        logger.warning(f"Parse failed: {str(e)}")
        return fallback_analysis(original_prompt)

def fallback_analysis(prompt):
    """ Fallback expense analysis if Gemini API fails """
    amount = extract_inr_amount(prompt)
    category = determine_category(prompt)
    return {
        'amount': format_inr(amount) if amount else "???",
        'category': category,
        'message': generate_fallback_message(category)
    }

def format_inr(amount):
    """ Formats numbers into INR format """
    try:
        num = float(amount)
        return "{:,.2f}".format(num).rstrip('0').rstrip('.') if '.' in str(amount) else "{:,.0f}".format(num)
    except:
        return "???"

def extract_inr_amount(text):
    """ Extracts amount from text """
    text = text.replace(',', '').lower()
    patterns = [
        r'₹\s*(\d+\.?\d*)',
        r'rs\.?\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*(?:rs|inr)',
        r'(\d+\.?\d*)\s*(k|thousand)',  # 5k = 5000
        r'(\d+\.?\d*)\s*lakh',         # 1.5 lakh = 150000
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            base, multiplier = match.group(1), match.group(2) if len(match.groups()) > 1 else ''
            try:
                amount = float(base)
                if multiplier == 'k' or multiplier == 'thousand':
                    amount *= 1000
                elif multiplier == 'lakh':
                    amount *= 100000
                return amount
            except:
                continue
    # Final fallback - find first number
    match = re.search(r'\d+\.?\d*', text)
    return float(match.group()) if match else None

def determine_category(text):
    """ Determines expense category """
    text = text.lower()
    categories = {
       # Categories like Electronics etc.
   }

def generate_fallback_message(category):
   pass

