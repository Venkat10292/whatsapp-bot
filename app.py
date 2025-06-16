from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from difflib import get_close_matches
import pandas as pd

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
            df['Symbol'] = df['Symbol'].astype(str)
            df['Company Name'] = df['Company Name'].astype(str)
            stock_dict.update(dict(zip(df['Symbol'].str.upper(), df['Company Name'])))
            all_names.extend(df['Symbol'].str.lower().str.strip())
            all_names.extend(df['Company Name'].str.lower().str.strip())
        except Exception as e:
            print(f"❌ Error loading stock data: {e}")

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
        query = ' '.join(message[6:].strip().lower().split())
        match = get_close_matches(query, all_names, n=1, cutoff=0.4)

        if match:
            matched = match[0]
            row = df[df['Symbol'].str.lower().str.strip() == matched]  # exact symbol
            if row.empty:
                row = df[df['Company Name'].str.lower().str.strip() == matched]  # exact company
            if row.empty:
                row = df[df['Symbol'].str.lower().str.strip().str.contains(matched) |
                         df['Company Name'].str.lower().str.strip().str.contains(matched)]

            if not row.empty:
                symbol = row.iloc[0]['Symbol'].upper()
                company = row.iloc[0]['Company Name']
                user_sessions[sender] = {"suggested": symbol, "awaiting_confirmation": True}
                reply = f"Did you mean: {company} ({symbol})? Reply 'yes' to continue or type a new stock name."
            else:
                reply = "⚠️ Found a match but couldn't extract stock details. Please try again."
        else:
            reply = "❓ Couldn't find a match. Please try again with a valid stock name or symbol (e.g., stock: INFY)"
    else:
        reply = "Hi! To get stock info, send: stock: <company name or symbol>"

    response.message(reply)
    return str(response)

# Start server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
