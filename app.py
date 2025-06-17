from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf

app = Flask(__name__)

# Load stock data
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()
symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

# Track user session states
user_state = {}

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From")
    user_msg = request.form.get("Body", "").strip()
    response = MessagingResponse()
    reply = response.message()

    state = user_state.get(sender, "initial")

    # Initial greeting
    if user_msg.lower() in ["hi", "hello"] and state == "initial":
        reply.body(
            "👋 G. Satish చాట్‌బాట్‌కి స్వాగతం!\n"
            "ఈ రోజు నేను మీకు ఎలా సహాయపడగలను?\n\n"
            "1️⃣ స్టాక్ విశ్లేషణ 📈\n"
            "2️⃣ కొనుగోలు/అమ్మకం సమస్యలు ⚙️\n\n"
            "దయచేసి 1 లేదా 2 అని రిప్లై ఇవ్వండి."
        )
        user_state[sender] = "menu"
        return str(response)

    # Handle menu choice
    if state == "menu":
        if user_msg == "1":
            reply.body("✅ You've selected *Stock Analysis*.\nPlease enter the stock name or symbol.")
            user_state[sender] = "awaiting_stock"
        elif user_msg == "2":
            reply.body("🔧 This feature is currently under maintenance.")
            user_state[sender] = "initial"
        else:
            reply.body("❗ Invalid option. Please reply with 1 or 2.")
        return str(response)

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
                    reply.body(f"ℹ️ Found {company_name} ({symbol}) but price is unavailable.")
            except Exception as e:
                reply.body("⚠️ Error fetching stock price.")
        else:
            reply.body("❌ Could not find the stock. Please try again.")

        user_state[sender] = "initial"
        return str(response)

    # Default fallback
    reply.body("⚠️ Please type 'Hi' to begin.")
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
