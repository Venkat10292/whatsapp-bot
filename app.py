from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from difflib import get_close_matches
import pandas as pd

app = Flask(__name__)

# Load NSE stock data from CSV
df = pd.read_csv("nse_stocks.csv")
stock_dict = dict(zip(df["SYMBOL"], df["NAME OF COMPANY"]))

# Mock stock info lookup
def get_stock_info(symbol):
    return {
        "price": "₹18.74",
        "high": "₹23.63",
        "low": "₹15.82",
        "entry": "₹18.37",
        "exit": "₹19.68"
    }

user_sessions = {}

@app.route("/incoming", methods=['POST'])
def incoming_message():
    message = request.form.get('Body').strip()
    sender = request.form.get('From')
    response = MessagingResponse()

    session = user_sessions.get(sender, {})

    # If awaiting confirmation
    if session.get("awaiting_confirmation"):
        if message.lower() == "yes":
            symbol = session["suggested"]
            info = get_stock_info(symbol)
            reply = f"""📊 {symbol} - {stock_dict[symbol]}
Price: {info['price']}
52W High: {info['high']}
52W Low: {info['low']}
Suggested Entry: {info['entry']}
Suggested Exit: {info['exit']}"""
            user_sessions.pop(sender, None)
        else:
            reply = "Please retype the correct stock name using: stock: SYMBOL or COMPANY NAME"
            user_sessions.pop(sender, None)
        response.message(reply)
        return str(response)

    # Main flow
    if message.lower().startswith("stock:"):
        query = message[6:].strip().upper()
        symbols = list(stock_dict.keys())
        names = list(stock_dict.values())
        combined = symbols + names

        matches = get_close_matches(query, combined, n=1, cutoff=0.5)

        if matches:
            match = matches[0]
            # Get the actual symbol from match
            if match in stock_dict:
                symbol = match
            else:
                # Reverse lookup by name
                symbol = df[df["NAME OF COMPANY"] == match]["SYMBOL"].values[0]

            company = stock_dict[symbol]
            user_sessions[sender] = {"suggested": symbol, "awaiting_confirmation": True}
            reply = f"Did you mean: {company} ({symbol})? Reply 'yes' to continue or type a new stock name."
        else:
            reply = "Couldn't find a close match. Try again with: stock: SYMBOL or COMPANY NAME"
    else:
        reply = "Hi! To get stock info, send: stock: TCS or stock: Infosys"

    response.message(reply)
    return str(response)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
