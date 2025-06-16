from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from difflib import get_close_matches
import pandas as pd
import re

app = Flask(__name__)

# Load stock data from GitHub (load only once)
df = None
stock_dict = {}
all_names = []

def load_stock_data():
    global df, stock_dict, all_names
    if df is None:
        try:
            STOCKS_CSV_URL = "https://raw.githubusercontent.com/Venkat10292/whatsapp-bot/main/nse_stocks.csv"
            df = pd.read_csv(STOCKS_CSV_URL)

            # Normalize and prepare
            df['Symbol'] = df['Symbol'].astype(str).str.upper().str.strip()
            df['Company Name'] = df['Company Name'].astype(str).str.strip()
            
            # Create a dictionary with both symbols and company names as keys
            stock_dict = {}
            for _, row in df.iterrows():
                stock_dict[row['Symbol'].lower()] = row['Company Name']
                stock_dict[row['Company Name'].lower()] = row['Symbol']
            
            # Prepare all names for matching
            all_names = list(stock_dict.keys())
            
        except Exception as e:
            print(f"❌ Error loading stock data: {e}")

def clean_query(query):
    """Clean and normalize the search query"""
    query = query.lower().strip()
    # Remove common words that might interfere with matching
    query = re.sub(r'\b(?:stock|of|the|and|limited|ltd|co|corporation)\b', '', query)
    return ' '.join(query.split())

def find_stock_match(query):
    """Find the best stock match for the query"""
    query = clean_query(query)
    
    # First try exact matches
    if query in stock_dict:
        return stock_dict[query]
    
    # Then try close matches
    matches = get_close_matches(query, all_names, n=1, cutoff=0.4)
    if matches:
        return stock_dict[matches[0]]
    
    # If no close matches, try partial matching
    for name in all_names:
        if query in name or name in query:
            return stock_dict[name]
    
    return None

# Mock price lookup (replace with real API later)
def get_stock_info(symbol):
    return {
        "price": "₹18.74",
        "high": "₹23.63",
        "low": "₹15.82",
        "entry": "₹18.37",
        "exit": "₹19.68"
    }

# Store user session info
user_sessions = {}

@app.route("/incoming", methods=['POST'])
def incoming_message():
    load_stock_data()

    message = request.form.get('Body', '').strip()
    sender = request.form.get('From')
    response = MessagingResponse()

    session = user_sessions.get(sender, {})

    # Step 1: Handle user confirmation
    if session.get("awaiting_confirmation"):
        if message.lower() == "yes":
            symbol = session["suggested"]
            info = get_stock_info(symbol)
            reply = f"""📊 {symbol}
Price: {info['price']}
52W High: {info['high']}
52W Low: {info['low']}
Suggested Entry: {info['entry']}
Suggested Exit: {info['exit']}"""
            user_sessions.pop(sender, None)
        else:
            reply = "❌ Please retype the correct stock name (e.g., stock: TCS)"
            user_sessions.pop(sender, None)
        response.message(reply)
        return str(response)

    # Step 2: Handle stock lookup
    if message.lower().startswith("stock:"):
        query = message[6:].strip()
        symbol_or_name = find_stock_match(query)
        
        if symbol_or_name:
            # Determine if we got a symbol or company name
            if symbol_or_name in df['Symbol'].values:
                # We got a company name, find the symbol
                symbol = symbol_or_name
                company = df[df['Symbol'] == symbol_or_name]['Company Name'].values[0]
            else:
                # We got a symbol, find the company name
                company = symbol_or_name
                symbol = df[df['Company Name'] == symbol_or_name]['Symbol'].values[0]
                
            user_sessions[sender] = {"suggested": symbol, "awaiting_confirmation": True}
            reply = f"Did you mean: {company} ({symbol})? Reply 'yes' to continue or type a new stock name."
        else:
            reply = "❓ Couldn't find a match. Please try again with a valid stock name or symbol (e.g., stock: INFY)"
    else:
        reply = "Hi! To get stock info, send: stock: <company name or symbol>"

    response.message(reply)
    return str(response)

# Start server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
