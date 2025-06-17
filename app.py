from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf

app = Flask(__name__)

# Load and normalize stock data
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()

symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

# Track user states
user_states = {}

@app.route("/")
def home():
    return "WhatsApp Stock Bot is Live 🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From")
    user_msg = request.form.get("Body", "").strip()
    state = user_states.get(sender, "initial")

    resp = MessagingResponse()
    reply = resp.message()

    # Greeting flow
    if user_msg.lower() in ["hi", "hello"]:
        reply.body(
            "👋 Welcome to Stock Bot!\n"
            "How can I help you today?\n\n"
            "1️⃣ Stock Analysis 📈\n"
            "2️⃣ Application Support ⚙️\n\n"
            "Please reply with 1 or 2."
        )
        user_states[sender] = "menu"
        return str(resp)

    # Handle menu
    if state == "menu":
        if user_msg == "1":
            reply.body("✅ You've selected *Stock Analysis*.\nPlease enter the *company name* or *stock symbol*.")
            user_states[sender] = "awaiting_stock"
        elif user_msg == "2":
            reply.body("🔧 This feature is currently under maintenance.")
            user_states[sender] = "initial"
        else:
            reply.body("❗ Invalid choice. Please reply with 1 or 2.")
        return str(resp)

    # Handle stock analysis
    if state == "awaiting_stock":
        symbol = None
        company_name = None

        if user_msg.upper() in symbol_to_name:
            symbol = user_msg.upper()
            company_name = symbol_to_name[symbol]
        else:
            matches = get_close_matches(user_msg.lower(), name_to_symbol.keys(), n=1, cutoff=0.6)
            if matches:
                matched_name = matches[0]
                symbol = name_to_symbol[matched_name]
                company_name = matched_name.upper()

        if symbol and company_name:
            try:
                stock = yf.Ticker(symbol + ".NS")
                price = stock.info.get("regularMarketPrice", None)
                if price:
                    reply.body(f"📊 {company_name} ({symbol}): ₹{price}")
                else:
                    reply.body(f"ℹ️ {company_name} ({symbol}) found, but price is unavailable.")
            except Exception as e:
                print(f"Error: {e}")
                reply.body("⚠️ Error fetching stock price.")
        else:
            reply.body("❌ Stock not found. Please try again.")

        user_states[sender] = "initial"
        return str(resp)

    # Fallback
    reply.body("⚠️ Please type 'Hi' to start again.")
    user_states[sender] = "initial"
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
