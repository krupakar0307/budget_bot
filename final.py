import json
import requests
import re
import logging
import os
import boto3
from datetime import datetime, timedelta
import uuid
import time

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

# Store deletion confirmations temporarily (userId -> confirmation data)
deletion_confirmations = {}

def lambda_handler(event, context):
    try:
        logger.info(f"🔍 Received event: {json.dumps(event, indent=2)}")
        
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", {})

        chat_id = message.get("chat", {}).get("id")
        username = message.get("from", {}).get("username", str(chat_id))
        text = message.get("text", "").strip()
        message_id = str(message.get("message_id"))

        if not chat_id or not text:
            logger.error("🚨 Missing chat_id or text!")
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid request"})}

        # Check if the message has already been processed
        if check_if_processed(message_id):
            logger.info(f"⚠️ Message ID {message_id} has already been processed. Skipping...")
            return {"statusCode": 200, "body": json.dumps({"message": "Already processed"})}

        # Mark message as processed in DynamoDB
        mark_as_processed(message_id)
        
        # Check if this is a confirmation for expense deletion
        if is_deletion_confirmation(username, text):
            handle_deletion_confirmation(chat_id, message_id, username, text)
            return {"statusCode": 200, "body": json.dumps({"message": "Deletion confirmation processed"})}
        
        # Check if this is a deletion request
        if is_deletion_request(text):
            time_range = extract_deletion_time_range(text)
            handle_deletion_request(chat_id, message_id, username, time_range)
            return {"statusCode": 200, "body": json.dumps({"message": "Deletion request processed"})}

        # Check if it's an expense query
        if is_expense_query(text):
            logger.info(f"Processing as expense QUERY: {text}")
            time_range = extract_time_range_from_query(text)
            expenses = get_user_expenses(username, time_range)
            send_telegram_reply(chat_id, message_id, format_expense_summary(expenses, time_range))
            return {"statusCode": 200, "body": json.dumps({"message": "Expense query processed"})}
        
        # Then check if it contains a number for potential expense entry
        if not re.search(r'(?:show|display|list|my expenses|total)', text.lower()):
            analysis = analyze_expense(text)

            if analysis.get('amount') and analysis['amount'] != "???":
                try:
                    amount = float(str(analysis['amount']).replace(",", "").strip())

                    if amount > 0:
                        store_user_expense(username, analysis, text)

                        # Simple confirmation for expense entry
                        response_text = f"₹{amount} marked under <b>{analysis['category']}</b> expenses. <i>{analysis['message']}</i>"
                        send_telegram_reply(chat_id, message_id, response_text)
                        return {"statusCode": 200, "body": json.dumps({"message": "Expense processed"})}
                
                except ValueError as e:
                    logger.error(f"🔥 Invalid amount format: {analysis['amount']}, error: {e}")

        # If we get here, it's not a clear expense or query - show helpful message
        helpful_message = """
<b>👋 Hello! I'm your Expense Tracker Assistant!</b>

I can help you track expenses and provide insights about your spending habits.

<b>Here's how you can use me:</b>

<b>1️⃣ To record expenses, try formats like:</b>
• "spent 500 on dinner"
• "paid 1200 for groceries"
• "bought shoes for 3000"
• "purchased phone for 15000"
• "2000 for rent"
• "taxi 300"
• "1.5L for laptop" (I understand ₹, k, L and Cr formats)

<b>2️⃣ To review your expenses, ask me:</b>
• "show my expenses"
• "what did I spend today"
• "show my last expense"
• "show my expenses from last week"
• "what are my total expenses this month"

<b>3️⃣ To clean up your expenses:</b>
• "delete all my expenses"
• "erase my expenses from last month"
• "clear my expense history"

Just tell me what you bought and how much it cost, or ask about your spending history!
"""
        send_telegram_reply(chat_id, message_id, helpful_message)
        return {"statusCode": 200, "body": json.dumps({"message": "Instructions sent"})}
        
    except Exception as e:
        logger.error(f"🔥 Error processing request: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"message": "Internal Server Error"})}


def check_if_processed(message_id):
    """ Check DynamoDB if the message has already been processed """
    try:
        response = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={"message_id": {"S": f"MSG#{message_id}"}},
            ConsistentRead=True  # Ensure latest data is read
        )
        return "Item" in response  # True if item exists, False otherwise
    except Exception as e:
        logger.error(f"⚠️ Error checking DynamoDB: {str(e)}")
        return False  # Return False to avoid skipping transactions incorrectly


def mark_as_processed(message_id):
    """ Mark a message as processed in DynamoDB """
    try:
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={
                "message_id": {"S": f"MSG#{message_id}"},
                "processed_at": {"S": datetime.utcnow().isoformat()}
            }
        )
        logger.info(f"✅ Marked message {message_id} as processed.")
    except Exception as e:
        logger.error(f"⚠️ Error marking message in DynamoDB: {str(e)}")

def store_user_expense(username, analysis, original_text):
    """ Store user expense in DynamoDB """
    try:
        # Remove commas from the amount string before converting to float
        amount = float(analysis['amount'].replace(",", ""))
        
        if amount <= 0:
            logger.info(f"Skipping expense with zero or negative amount: {amount}")
            return
            
        timestamp = datetime.utcnow().isoformat()
        expense_id = f"EXP#{username}#{timestamp}"
        
        # Log for debugging
        logger.info(f"Storing expense for user {username}: {analysis}")
        
        # Store in DynamoDB
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={
                "message_id": {"S": expense_id},
                "username": {"S": username},
                "type": {"S": "EXPENSE"},
                "timestamp": {"S": timestamp},
                "amount": {"N": str(amount)},  # Ensure it's a valid float
                "category": {"S": analysis.get("category", "Uncategorized")},
                "description": {"S": original_text}
            }
        )
        logger.info(f"✅ Stored expense for user {username}")

    except ValueError as ve:
        logger.error(f"🔥 Invalid amount format: {analysis['amount']}, error: {ve}")
    except Exception as e:
        logger.error(f"⚠️ Error storing expense: {str(e)}")

        
def is_expense_query(text):
    """Check if text is asking about past expenses with typo tolerance"""
    text_lower = text.lower()
    
    # Common typos for "show"
    show_variants = ["show", "shwo", "shoq", "sho", "sbow"]
    
    # Direct matches for common query phrases with typo tolerance
    for show_variant in show_variants:
        direct_queries = [
            f"{show_variant} my expenses",
            f"{show_variant} expenses", 
            f"{show_variant} my transactions"
        ]
        if any(query in text_lower for query in direct_queries):
            logger.info(f"Detected as expense query (direct match with typo tolerance): {text_lower}")
            return True
    
    # Other direct phrases that don't depend on "show"
    other_direct_queries = [
        "my expenses",
        "what did i spend",
        "how much did i spend",
        "total expenses",
        "expense report",
        "spending summary"
    ]
    
    if any(query in text_lower for query in other_direct_queries):
        logger.info(f"Detected as expense query (direct match): {text_lower}")
        return True
    
    # Keywords that indicate a query
    query_keywords = [
        "show", "shwo", "list", "display", "tell me", "what", "how much", 
        "total", "summary", "report", "analysis", "breakdown"
    ]
    
    # Must include both a query keyword and 'expense'/'spent'/'spend' term
    has_query_keyword = any(keyword in text_lower for keyword in query_keywords)
    has_expense_term = any(term in text_lower for term in ["expense", "spent", "spend", "cost", "payment"])
    
    if has_query_keyword and has_expense_term:
        logger.info(f"Detected as expense query (keyword + expense term): {text_lower}")
        return True
    
    logger.info(f"Not detected as expense query: {text_lower}")
    return False


def extract_time_range_from_query(query):
    """ Extract time range from query using Gemini API """
    system_prompt = """You are an expense tracking assistant. Analyze the user's query about their expenses and extract the time range and limit.
    
    Return a JSON with the following format:
    {
        "days": number,
        "description": "human readable description of the time period",
        "limit": number (number of transactions to show, null for all)
    }
    
    Examples:
    - "show my last expense" → {"days": 30, "description": "last expense", "limit": 1}
    - "show my last transaction" → {"days": 30, "description": "last expense", "limit": 1}
    - "show my all transactions" → {"days": 30, "description": "last expense", "limit": 1}
    - "show my last expense only" → {"days": 30, "description": "last expense", "limit": 1}
    - "what did I spend today" → {"days": 1, "description": "today", "limit": null}
    - "show my expenses from last week" → {"days": 7, "description": "last week", "limit": null}
    - "how much did I spend this month" → {"days": 30, "description": "this month", "limit": null}
    - "expenses in the last 3 days" → {"days": 3, "description": "last 3 days", "limit": null}
    - "show all my expenses" → {"days": 90, "description": "all expenses", "limit": null}
    - "show my recent 5 expenses" → {"days": 30, "description": "recent expenses", "limit": 5}
    
    Be very attentive to phrases like "last expense", "last transaction", "recent expense" which indicate the user wants to see only the most recent expense.
    """

    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nUser query: {query}"}]
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
        
        # Extract JSON from response
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            time_range = json.loads(json_match.group(1))
            return {
                "days": time_range.get("days", 30),
                "description": time_range.get("description", "recent expenses"),
                "limit": time_range.get("limit", None)
            }
    except Exception as e:
        logger.error(f"⚠️ Error extracting time range: {str(e)}")
    
    # Default fallback
    return {"days": 30, "description": "recent expenses", "limit": None}


def get_user_expenses(username, time_range):
    """ Get user expenses from DynamoDB based on time range """
    try:
        # Calculate start time based on days
        days = time_range.get("days", 7)
        start_time = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Scan DynamoDB for expenses
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            FilterExpression="username = :u AND #type = :t AND #ts >= :st AND #amount > :zero",
            ExpressionAttributeNames={
                "#type": "type",
                "#ts": "timestamp",
                "#amount": "amount"
            },
            ExpressionAttributeValues={
                ":u": {"S": username},
                ":t": {"S": "EXPENSE"},
                ":st": {"S": start_time},
                ":zero": {"N": "0"}  # Filter out zero-amount expenses
            }
        )
        
        items = response.get('Items', [])
        logger.info(f"Found {len(items)} expenses for user {username} in {time_range['description']}")
        return items
    except Exception as e:
        logger.error(f"⚠️ Error querying expenses: {str(e)}")
        return []


def format_expense_summary(expenses, time_range, threshold=5000):
    """ Format expenses into a readable summary """

    if threshold is None:
        threshold = 1000  # Default value if threshold is not set
    
    if not expenses:
        return f"No expenses found for {time_range['description']}! 💸"
    
    try:
        # Sort expenses by timestamp (newest first)
        sorted_expenses = sorted(expenses, key=lambda x: x['timestamp']['S'], reverse=True)
        
        # Apply limit if specified
        limit = time_range.get('limit')
        if limit is not None and limit > 0:
            is_single = limit == 1
            sorted_expenses = sorted_expenses[:limit]
            
            # If we're only showing a single expense, format differently
            if is_single and sorted_expenses:
                exp = sorted_expenses[0]
                amount = float(exp['amount']['N'])
                category = exp['category']['S']
                desc = exp.get('description', {}).get('S', category)
                date = datetime.fromisoformat(exp['timestamp']['S']).strftime("%d %b, %H:%M")
                
                response = [f"<b>💰 Your Most Recent Expense</b>"]
                response.append(f"<b>Amount:</b> ₹{amount:,.2f}")
                response.append(f"<b>Category:</b> {category}")
                response.append(f"<b>Details:</b> {desc}")
                response.append(f"<b>Date:</b> {date}")
                
                return "\n".join(response)
        
        # Calculate total
        total = sum(float(exp['amount']['N']) for exp in sorted_expenses)
        
        # Group by category
        categories = {}
        for exp in sorted_expenses:
            cat = exp['category']['S']
            amount = float(exp['amount']['N'])
            categories[cat] = categories.get(cat, 0) + amount
        
        # Format summary
        if limit is not None and limit > 0:
            response = [f"<b>💰 Your {limit} Most Recent Expenses</b>"]
        else:
            response = [f"<b>💰 Your Expenses ({time_range['description']})</b>"]
            
        response.append(f"<b>Total:</b> <u><b>₹{total:,.2f}</b></u>")
        
        # Add category breakdown
        response.append("\n<b>Category Breakdown:</b>")
        for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            percentage = (amount / total) * 100
            response.append(f"• <b>{cat}:</b> ₹{amount:,.2f} ({percentage:.1f}%)")
        
        # Add transactions
        response.append("\n<b>Transactions:</b>")
        for idx, exp in enumerate(sorted_expenses[:5]):
            if idx >= 5 and limit is None:
                break
            amount = float(exp['amount']['N'])
            category = exp['category']['S']
            desc = exp.get('description', {}).get('S', category)
            date = datetime.fromisoformat(exp['timestamp']['S']).strftime("%d %b, %H:%M")
            response.append(f"• ₹{amount:,.2f} - {desc} ({date})")
        
        # Add total transactions count if we limited them
        remaining = len(sorted_expenses) - 5
        if remaining > 0 and limit is None:
            response.append(f"\n<i>+ {remaining} more transactions</i>")
        
        
        # Check threshold and add warning
        remaining = threshold - total
        if total >= threshold * 0.8:
            if total >= threshold:
                response.append(f"\n<b>⚠️ You have reached your threshold of ₹{threshold}!</b> You're now at ₹{total:,.2f}. Be careful, you're getting close to overspending!")
            else:
                response.append(f"\n<b>⚠️ You've reached 80% of your threshold!</b> ₹{total:,.2f} out of ₹{threshold}. Watch out, you're almost there!")

        return "\n".join(response)

    except Exception as e:
        logger.error(f"⚠️ Error formatting expense summary: {str(e)}")
        return "I encountered an error while formatting your expenses. Please try again."

def send_telegram_reply(chat_id, message_id, text):
    """ Sends a reply to the specific message in Telegram with proper formatting """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": message_id,  # Replying to the original message in a thread
        "parse_mode": "HTML"  # **Ensures proper formatting in Telegram**
    }

    logger.info(f"📤 Sending reply to Telegram: {json.dumps(payload)}")

    try:
        response = requests.post(TELEGRAM_API_URL, json=payload)
        response.raise_for_status()  # Raise an error for bad responses
        
        logger.info(f"✅ Message sent successfully: {response.json()}")
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"⚠️ HTTP error occurred: {http_err} - Response: {response.text}")
    except Exception as e:
        logger.error(f"⚠️ Failed to send message: {str(e)}")

# Your other functions (analyze_expense, parse_gemini_response, etc.) remain unchanged

def is_expense_entry(text):
    """Determine if this is an expense entry attempt with emoji support"""
    text_lower = text.lower()
    
    # Log the text for debugging
    logger.info(f"Checking if this is an expense entry: {text_lower}")
    
    # Check if the text contains any number - this is the most basic check
    has_number = bool(re.search(r'\d+', text_lower))
    if not has_number:
        logger.info(f"Not an expense entry - no numbers found: {text_lower}")
        return False
    
    # Check for emojis that indicate expense categories
    electronics_emojis = ["💻", "📱", "⌚", "🖥️", "🖨️", "📷", "🎮"]
    food_emojis = ["🍕", "🍔", "🍟", "🍗", "🍖", "🥗", "🍣", "🍩", "🍦", "🍨", "🧁", "🍰", "🍪"]
    transport_emojis = ["🚗", "🚕", "🚌", "🚆", "✈️", "🛵", "🚲", "🚅", "🚄"]
    
    # If text has a number and any relevant emoji, it's likely an expense
    if has_number and any(emoji in text for emoji in electronics_emojis + food_emojis + transport_emojis):
        logger.info(f"Detected expense entry with emoji: {text}")
        return True
    
    # Rest of the existing checks
    # ... [existing checks] ...
    
    return True  # If we got this far, it's probably an expense

def format_inr(amount):
    """ Formats numbers into INR format """
    try:
        if isinstance(amount, str):
            amount = float(amount.replace(',', ''))
        num = float(amount)
        return "{:,.2f}".format(num).rstrip('0').rstrip('.') if '.' in str(amount) else "{:,.0f}".format(num)
    except Exception as e:
        logger.error(f"Error formatting amount: {str(e)}")
        return "???"

def extract_inr_amount(text):
    """ Extracts amount from text with improved detection """
    text = text.replace(',', '').lower().strip()

    # Debug log
    logger.info(f"Extracting amount from: {text}")

    # Regex to match amounts with optional decimal and multipliers
    match = re.search(r'(\d+(\.\d+)?)\s*(k|thousand|l|lakh|lakhs|cr|crore|crores)?', text, re.IGNORECASE)
    
    if match:
        try:
            amount = float(match.group(1))  # Extract numeric part
            multiplier = match.group(3)  # Extract multiplier, if any

            # Apply multipliers if present
            if multiplier:
                multiplier = multiplier.lower()
                if multiplier in ('k', 'thousand'):
                    amount *= 1_000
                elif multiplier in ('l', 'lakh', 'lakhs'):
                    amount *= 100_000
                elif multiplier in ('cr', 'crore', 'crores'):
                    amount *= 10_000_000

                logger.info(f"Applied '{multiplier}' multiplier: {amount}")

            logger.info(f"Extracted amount: {amount}")
            return amount
        except Exception as e:
            logger.error(f"🔥 Error converting amount: {str(e)}")

    logger.warning(f"⚠️ No amount found in text: {text}")
    return None

 

def analyze_expense(prompt):
    """Calls Gemini API to analyze expense details with better error handling"""
    # Log the prompt for debugging
    logger.info(f"Analyzing expense prompt: {prompt}")
    
    system_prompt = """You are a smart expense tracking assistant for Indian users. Analyze the user's expense message and:

1. Extract numerical amount in any format (₹500, 5k, 1.5L, 4L, 1Cr etc.) - where k = thousand (1000), L = Lakh (100,000) and Cr = Crore (10,000,000)
2. Determine the most appropriate category from this list:
   - Food (meals, restaurants, snacks, groceries, dining, coffee, tea, beverages)
   - Groceries (supermarket, fruits, vegetables, household items)
   - Transport (uber, ola, taxi, auto, bus, metro, fuel, travel)
   - Vehicle (car, bike, cycle, repair, servicing, automotive, motor)
   - Bills (electricity, water, internet, recharges, subscriptions)
   - Health (medicines, doctor visits, hospital, medical)
   - Fashion (clothes, shoes, frocks, dresses, accessories, footwear)
   - Electronics (gadgets, phones, iphone, smartphone, laptop, computer, devices)
   - Personal Care (haircut, spa, cosmetics, grooming)
   - Education (books, courses, tuition, coaching)
   - Entertainment (movies, games, events, recreation)
   - Shopping (general purchases)
   - Home (furniture, decor, appliances, housing)
   - Miscellaneous (anything else)
3. Generate a friendly response message in English (20-30 words) with emojis.
4. Return JSON format: {"amount": number, "category": string, "message": string}

IMPORTANT: Be extremely flexible in understanding expense formats. Extract any number and make a reasonable guess at the category.
Always return a valid numerical amount and category even if you have to guess based on limited information.
"""

    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nUser Input: {prompt}"}]
        }]
    }

    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=10
        )
        
        response.raise_for_status()
        
        result = response.json()
        
        response_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        
        # Log the response from Gemini for debugging
        logger.info(f"Gemini response: {response_text}")
        
        parsed_result = parse_gemini_response(response_text, prompt)
        
        # Log the parsed result
        logger.info(f"Parsed result: {parsed_result}")
        
        # Verify we have a valid amount
        if parsed_result.get('amount') and parsed_result.get('amount') != "???":
            try:
                amount = float(parsed_result['amount'])
                if amount <= 0:
                    # Try manual extraction as fallback
                    amount = extract_inr_amount(prompt)
                    if amount:
                        parsed_result['amount'] = format_inr(amount)
            except:
                # Fallback to manual extraction
                amount = extract_inr_amount(prompt)
                if amount:
                    parsed_result['amount'] = format_inr(amount)
        
        return parsed_result
        
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return fallback_analysis(prompt)

def parse_gemini_response(response_text, original_prompt):
    """ Parses the response from Gemini API and ensures proper formatting """
    try:
        json_str = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_str:
            logger.error(f"No JSON found in response: {response_text}")
            return fallback_analysis(original_prompt)
            
        data = json.loads(json_str.group())
        
        # Validate the data
        if 'amount' not in data or 'category' not in data:
            logger.error(f"Missing fields in JSON response: {data}")
            return fallback_analysis(original_prompt)
            
        # Format amount and ensure it's a number
        amount = data.get('amount', 0)
        # Convert string representations to numbers if needed
        if isinstance(amount, str) and amount.replace(',', '').isdigit():
            amount = float(amount.replace(',', ''))
            
        return {
            'amount': format_inr(amount),
            'category': data.get('category', 'Miscellaneous').title(),
            'message': data.get('message', 'Added to expenses! 💰')
        }
        
    except Exception as e:
        logger.warning(f"Parse failed: {str(e)}")
        return fallback_analysis(original_prompt)

def fallback_analysis(prompt):
    """ Fallback expense analysis if Gemini API fails """
    # Log that we're using fallback
    logger.info(f"Using fallback analysis for: {prompt}")
    
    # Try to extract amount and category from the text
    amount = extract_inr_amount(prompt)
    
    # Determine category with better handling of electronics
    category = determine_fallback_category(prompt)
    
    return {
        'amount': format_inr(amount) if amount else "???",
        'category': category,
        'message': generate_fallback_message(category)
    }

def determine_fallback_category(text):
    """Improved category determination including emoji support"""
    text_lower = text.lower()
    
    # Electronics emojis
    electronics_emojis = ["💻", "📱", "⌚", "🖥️", "🖨️", "📷", "🎮"]
    if any(emoji in text for emoji in electronics_emojis):
        return 'Electronics'
    
    # Food emojis
    food_emojis = ["🍕", "🍔", "🍟", "🍗", "🍖", "🥗", "🍣", "🍩", "🍦", "🍨", "🧁", "🍰", "🍪"]
    if any(emoji in text for emoji in food_emojis):
        return 'Food'
    
    # Transport emojis
    transport_emojis = ["🚗", "🚕", "🚌", "🚆", "✈️", "🛵", "🚲", "🚅", "🚄"]
    if any(emoji in text for emoji in transport_emojis):
        return 'Transport'
    
    # Regular keyword checks
    category_keywords = {
        'Food': ['food', 'meal', 'lunch', 'dinner', 'breakfast', 'restaurant', 'eat', 'coffee', 'tea', 'cafe'],
        'Groceries': ['grocery', 'groceries', 'supermarket', 'fruit', 'vegetable'],
        'Transport': ['uber', 'ola', 'taxi', 'auto', 'transport', 'travel', 'bus', 'train', 'metro'],
        'Vehicle': ['car', 'bike', 'cycle', 'repair', 'service', 'motor', 'fuel', 'petrol', 'diesel'],
        'Bills': ['bill', 'recharge', 'subscription', 'electricity', 'water', 'internet', 'phone bill'],
        'Health': ['medicine', 'doctor', 'hospital', 'medical', 'health', 'clinic', 'dentist'],
        'Fashion': ['clothes', 'dress', 'shirt', 'pant', 'shoe', 'footwear', 'apparel', 'fashion'],
        'Electronics': ['phone', 'mobile', 'laptop', 'computer', 'gadget', 'electronics', 'device'],
        'Entertainment': ['movie', 'game', 'show', 'concert', 'entertainment', 'theatre', 'amusement'],
        'Education': ['book', 'course', 'class', 'tuition', 'school', 'college', 'education']
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            return category
    
    # Default
    return 'Miscellaneous'

def generate_fallback_message(category):
    """Generate a friendly message based on category"""
    messages = {
        'Electronics': "New gadget! 📱 Your electronics purchase has been logged. Enjoy your new device!",
        'Bills': "Payment noted! 🧾 I've recorded your bill payment. Keeping your expenses organized!",
        'Food': "Yum! 🍔 I've added your food expense to your tracker. Bon appétit!",
        'Transport': "On the move! 🚗 I've logged your transport expense. Safe travels!",
        'Miscellaneous': "Got it! 💰 Your expense has been recorded. Thanks for keeping track!"
    }
    
    return messages.get(category, "Added to expenses! 💰")

def is_deletion_request(text):
    """Check if text is asking to delete expense history"""
    text_lower = text.lower()
    
    # Keywords that indicate deletion
    deletion_keywords = [
        "delete", "remove", "erase", "clear", "clean", "wipe", "purge"
    ]
    
    # Target phrases
    target_phrases = [
        "expense", "expenses", "history", "data", "records", "transactions"
    ]
    
    has_deletion_keyword = any(keyword in text_lower for keyword in deletion_keywords)
    has_target_phrase = any(phrase in text_lower for phrase in target_phrases)
    
    if has_deletion_keyword and has_target_phrase:
        logger.info(f"Detected as deletion request: {text_lower}")
        return True
    
    logger.info(f"Not detected as deletion request: {text_lower}")
    return False


def extract_deletion_time_range(text):
    """Extract time range or count for deletion using Gemini API"""
    system_prompt = """You are an expense tracking assistant. Analyze the user's request to delete their expense history and extract either a time range or a count of recent expenses.
    
    Return a JSON with the following format:
    {
        "days": number or null,
        "description": "human readable description of what to delete",
        "count": number or null,
        "position": string or null (possible values: "first", "last", or null)
    }
    
    Examples:
    - "delete all my expenses" → {"days": null, "description": "all expenses", "count": null, "position": null}
    - "erase my expenses from last week" → {"days": 7, "description": "last week", "count": null, "position": null}
    - "clear my expense history for this month" → {"days": 30, "description": "this month", "count": null, "position": null}
    - "remove my expenses from last 3 days" → {"days": 3, "description": "last 3 days", "count": null, "position": null}
    - "delete my last 2 expenses" → {"days": null, "description": "last 2 expenses", "count": 2, "position": "last"}
    - "delete first 2 expenses" → {"days": null, "description": "first 2 expenses", "count": 2, "position": "first"}
    - "delete my recent 5 expenses" → {"days": null, "description": "last 5 expenses", "count": 5, "position": "last"}
    
    IMPORTANT: Pay careful attention to words like "first" or "last" when deleting a specific number of expenses.
    - "first N expenses" means the oldest N expenses (top of the list)
    - "last N expenses" means the most recent N expenses (shown first in the list)
    - If no position is specified, assume "last" (most recent)
    """

    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nUser request: {text}"}]
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
        
        # Extract JSON from response
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            time_range = json.loads(json_match.group(1))
            return {
                "days": time_range.get("days"),
                "description": time_range.get("description", "specified expenses"),
                "count": time_range.get("count"),
                "position": time_range.get("position")
            }
    except Exception as e:
        logger.error(f"⚠️ Error extracting deletion parameters: {str(e)}")
    
    # Default fallback is to delete all
    return {"days": None, "description": "all expenses", "count": None, "position": None}


def handle_deletion_request(chat_id, message_id, username, time_range):
    """Handle a request to delete expenses"""
    try:
        # Get expenses based on time range or count
        if time_range.get("count") is not None:
            # Get all expenses for the user
            all_expenses = get_all_user_expenses(username)
            
            # Sort expenses by timestamp based on position
            position = time_range.get("position", "last")  # Default to "last" if not specified
            
            if position == "last":
                # Most recent expenses first (newest first)
                sorted_expenses = sorted(all_expenses, key=lambda x: x['timestamp']['S'], reverse=True)
            else:  # "first" position
                # Oldest expenses first
                sorted_expenses = sorted(all_expenses, key=lambda x: x['timestamp']['S'], reverse=False)
            
            count = min(time_range["count"], len(sorted_expenses))
            expenses = sorted_expenses[:count]
            
            # Log what we're deleting
            logger.info(f"Deleting {count} expenses from position {position}")
            for exp in expenses:
                logger.info(f"Will delete: {exp.get('description', {}).get('S')} - {exp.get('amount', {}).get('N')}")
                
        elif time_range.get("days") is not None:
            start_time = (datetime.utcnow() - timedelta(days=time_range["days"])).isoformat()
            expenses = get_user_expenses_for_deletion(username, start_time)
        else:
            expenses = get_all_user_expenses(username)
        
        expense_count = len(expenses)
        
        if expense_count == 0:
            send_telegram_reply(chat_id, message_id, f"You don't have any expenses to delete.")
            return
        
        # Create a confirmation code
        confirmation_code = str(uuid.uuid4())[:8]
        
        # Store the deletion request with an expiration
        deletion_confirmations[username] = {
            "confirmation_code": confirmation_code,
            "time_range": time_range,
            "expenses_to_delete": [exp["message_id"]["S"] for exp in expenses],  # Store IDs of expenses to delete
            "chat_id": chat_id,
            "expense_count": expense_count,
            "expires_at": time.time() + 300  # 5 minutes expiration
        }
        
        # Calculate total amount
        total_amount = sum(float(exp['amount']['N']) for exp in expenses)
        
        # Send confirmation message
        confirmation_message = f"""
<b>⚠️ Expense Deletion Confirmation</b>

You've requested to delete <b>{expense_count} expenses</b> ({time_range['description']}) with a total value of <b>₹{total_amount:,.2f}</b>.

<b>This action cannot be undone!</b>

To confirm deletion, please reply with:
<code>confirm {confirmation_code}</code>

To cancel, simply ignore this message or type "cancel".
"""
        send_telegram_reply(chat_id, message_id, confirmation_message)
    except Exception as e:
        logger.error(f"⚠️ Error handling deletion request: {str(e)}")
        send_telegram_reply(chat_id, message_id, "I encountered an error processing your deletion request. Please try again.")


def is_deletion_confirmation(username, text):
    """Check if this is a confirmation for deletion"""
    # First check if there's a pending confirmation for this user
    if username not in deletion_confirmations:
        return False
    
    # Check if the confirmation has expired
    if deletion_confirmations[username]["expires_at"] < time.time():
        # Remove expired confirmation
        del deletion_confirmations[username]
        return False
    
    # Check if this is a confirmation or cancellation
    text_lower = text.lower()
    
    # Check for cancellation
    if text_lower == "cancel":
        # Remove the confirmation
        del deletion_confirmations[username]
        return True
    
    # Check for confirmation with code
    confirmation_data = deletion_confirmations[username]
    confirmation_match = re.match(r'confirm\s+(\w+)', text_lower)
    
    if confirmation_match and confirmation_match.group(1) == confirmation_data["confirmation_code"]:
        return True
    
    return False


def handle_deletion_confirmation(chat_id, message_id, username, text):
    """Handle the confirmation response for deletion"""
    if username not in deletion_confirmations:
        send_telegram_reply(chat_id, message_id, "I don't have any pending deletion requests for you.")
        return
    
    text_lower = text.lower()
    
    # Check if this is a cancellation
    if text_lower == "cancel":
        del deletion_confirmations[username]
        send_telegram_reply(chat_id, message_id, "Expense deletion cancelled. Your data remains intact.")
        return
    
    # Execute the deletion
    confirmation_data = deletion_confirmations[username]
    time_range = confirmation_data["time_range"]
    expense_count = confirmation_data["expense_count"]
    
    try:
        # Use the stored expense IDs if available
        if "expenses_to_delete" in confirmation_data:
            expense_ids = confirmation_data["expenses_to_delete"]
            deleted_count = delete_specific_expenses(expense_ids)
        elif time_range.get("days") is not None:
            start_time = (datetime.utcnow() - timedelta(days=time_range["days"])).isoformat()
            deleted_count = delete_user_expenses(username, start_time)
        else:
            deleted_count = delete_all_user_expenses(username)
        
        # Remove the confirmation data
        del deletion_confirmations[username]
        
        # Send success message
        send_telegram_reply(
            chat_id, 
            message_id, 
            f"✅ Successfully deleted {deleted_count} expenses ({time_range['description']}). Your expense history has been updated."
        )
    except Exception as e:
        logger.error(f"⚠️ Error executing deletion: {str(e)}")
        send_telegram_reply(chat_id, message_id, "I encountered an error while deleting your expenses. Please try again.")


def get_user_expenses_for_deletion(username, start_time):
    """Get user expenses for a specific time range for deletion"""
    try:
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            FilterExpression="username = :u AND #type = :t AND #ts >= :st",
            ExpressionAttributeNames={
                "#type": "type",
                "#ts": "timestamp"
            },
            ExpressionAttributeValues={
                ":u": {"S": username},
                ":t": {"S": "EXPENSE"},
                ":st": {"S": start_time}
            }
        )
        
        return response.get('Items', [])
    except Exception as e:
        logger.error(f"⚠️ Error getting expenses for deletion: {str(e)}")
        return []


def get_all_user_expenses(username):
    """Get all expenses for a user"""
    try:
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            FilterExpression="username = :u AND #type = :t",
            ExpressionAttributeNames={
                "#type": "type"
            },
            ExpressionAttributeValues={
                ":u": {"S": username},
                ":t": {"S": "EXPENSE"}
            }
        )
        
        return response.get('Items', [])
    except Exception as e:
        logger.error(f"⚠️ Error getting all user expenses: {str(e)}")
        return []


def delete_user_expenses(username, start_time):
    """Delete user expenses from a specific time range"""
    try:
        # Get expenses to delete
        expenses = get_user_expenses_for_deletion(username, start_time)
        
        deleted_count = 0
        for expense in expenses:
            # Get the message_id for deletion
            message_id = expense["message_id"]["S"]
            
            # Delete the item
            dynamodb.delete_item(
                TableName=DYNAMODB_TABLE,
                Key={"message_id": {"S": message_id}}
            )
            deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} expenses for user {username} from {start_time}")
        return deleted_count
    except Exception as e:
        logger.error(f"⚠️ Error deleting expenses: {str(e)}")
        raise e


def delete_all_user_expenses(username):
    """Delete all expenses for a user"""
    try:
        # Get all expenses
        expenses = get_all_user_expenses(username)
        
        deleted_count = 0
        for expense in expenses:
            # Get the message_id for deletion
            message_id = expense["message_id"]["S"]
            
            # Delete the item
            dynamodb.delete_item(
                TableName=DYNAMODB_TABLE,
                Key={"message_id": {"S": message_id}}
            )
            deleted_count += 1
        
        logger.info(f"Deleted all {deleted_count} expenses for user {username}")
        return deleted_count
    except Exception as e:
        logger.error(f"⚠️ Error deleting all expenses: {str(e)}")
        raise e

def delete_specific_expenses(expense_ids):
    """Delete specific expenses by their message_id"""
    try:
        deleted_count = 0
        for message_id in expense_ids:
            dynamodb.delete_item(
                TableName=DYNAMODB_TABLE,
                Key={"message_id": {"S": message_id}}
            )
            deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} specific expenses")
        return deleted_count
    except Exception as e:
        logger.error(f"⚠️ Error deleting specific expenses: {str(e)}")
        raise e
