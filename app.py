from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from difflib import get_close_matches
import csv
import requests

app = Flask(__name__)

# Load stock symbols and names from CSV (modify path if needed)
def load_stock_data():
    url = "https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME/main/nse_stocks.csv"
    response = requests.get(url)
    lines = response.text.strip().split('\n')
    reader = csv.DictReader(lines)
    stocks = {}
    for row in reader:
        symbol = row['SYMBOL'].strip().upper()
        name = row['NAME'].strip().upper()
        stocks[symbol] = name
    return stocks

stock_dict = load_stock_data()
user_sessions = {}

# Mock API for stock info (replace with real API if available)
def get_stock_info(symbol):
    return {
        "price": "₹18.74",
        "high": "₹23.63",
        "low": "₹15.82",
        "entry": "₹18.37",
        "exit": "₹19.68"
    }

@app.route("/incoming", methods=['POST'])
def incoming_message():
    message = request.form.get('Body').strip()
    sender = request.form.get('From')
    response = MessagingResponse()
    session = user_sessions.get(sender, {})

    # Handle user confirmation
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
            user_sessions.pop(sender, None)
            reply = "Please retype the correct stock name (e.g., stock: TCS)"
        response.message(reply)
        return str(response)

    # New stock request
    if message.lower().startswith("stock:"):
        query = message[6:].strip().upper()

        # Direct symbol match
        if query in stock_dict:
            suggested = query
            company = stock_dict[suggested].title()
            user_sessions[sender] = {"suggested": suggested, "awaiting_confirmation": True}
            reply = f"Did you mean: {company} ({suggested})? Reply 'yes' to continue or type a new stock name."

        else:
            # Fuzzy match on names
            match = get_close_matches(query, stock_dict.values(), n=1, cutoff=0.5)
            if match:
                matched_name = match[0]
                # Reverse lookup
                suggested = [symbol for symbol, name in stock_dict.items() if name == matched_name][0]
                company = stock_dict[suggested].title()
                user_sessions[sender] = {"suggested": suggested, "awaiting_confirmation": True}
                reply = f"Did you mean: {company} ({suggested})? Reply 'yes' to continue or type a new stock name."
            else:
                reply = "Couldn't find a match. Please try again with a valid stock name or symbol (e.g., stock: INFY)"
    else:
        reply = "Hi! To get stock info, send: stock: <company name or symbol>"

    response.message(reply)
    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
