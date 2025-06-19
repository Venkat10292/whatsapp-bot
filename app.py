from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf

app = Flask(__name__)

# Load and normalize the CSV
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()  # Normalize column headers

# Build lookup dictionaries
symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

@app.route("/")
def home():
    return "WhatsApp Stock Bot is live 🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    user_msg = request.form.get("Body", "").strip()
    print(f"Received message: {user_msg}")

    response = MessagingResponse()
    reply = response.message()

    symbol = None
    company_name = None

    # Check if message is a known symbol
    if user_msg.upper() in symbol_to_name:
        symbol = user_msg.upper()
        company_name = symbol_to_name[symbol]

    # Check if message closely matches a company name
    else:
        matches = get_close_matches(user_msg.lower(), name_to_symbol.keys(), n=1, cutoff=0.6)
        if matches:
            matched_name = matches[0]
            symbol = name_to_symbol[matched_name]
            company_name = matched_name.upper()

    # Respond with stock price if found
    if symbol and company_name:
        try:
            stock = yf.Ticker(symbol + ".NS")
            price = stock.info.get("regularMarketPrice", None)
            if price:
                reply.body(f"📈 {company_name} ({symbol}): ₹{price}")
            else:
                reply.body(f"ℹ️ {company_name} ({symbol}) found, but price is unavailable.")
        except Exception as e:
            print(f"Error fetching stock price: {e}")
            reply.body("⚠️ Could not fetch stock price.")
    else:
        reply.body("❌ Stock not found. Please enter a valid company name or symbol.")

    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
