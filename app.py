from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf
import mplfinance as mpf
import os
from datetime import datetime

app = Flask(__name__)

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

# Load and normalize the CSV
try:
    df = pd.read_csv("nse_stocks.csv")
    df.columns = df.columns.str.strip().str.upper()  # Normalize column headers
    symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
    name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))
except Exception as e:
    print("Error loading CSV:", e)
    symbol_to_name, name_to_symbol = {}, {}

# Track user states
user_states = {}

@app.route("/")
def home():
    return "WhatsApp Stock Bot is live 🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    print("DEBUG: Incoming request received")
    print("DEBUG: request.form =>", dict(request.form))

    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    user_state = user_states.get(sender, "initial")

    response = MessagingResponse()

    # Handle greetings
    if user_msg.lower() in ["hi", "hello"]:
        response.message(
            "👋 Welcome to Stock Bot!\n"
            "What can I help you with?\n\n"
            "1️⃣ Stock Analysis 📈\n"
            "2️⃣ Application Support ⚙️\n\n"
            "Please reply with 1 or 2."
        )
        user_states[sender] = "menu"
        return str(response)

    if user_state == "menu":
        if user_msg == "1":
            response.message("You have selected Stock Analysis.\nPlease enter the company name or stock symbol.")
            user_states[sender] = "stock_mode"
            return str(response)
        elif user_msg == "2":
            response.message("🔧 This feature is currently under maintenance.")
            user_states[sender] = "initial"
            return str(response)
        else:
            response.message("❗ Invalid choice. Please reply with 1 or 2.")
            return str(response)

    # Determine symbol
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

            # Download last 120 daily candles
            hist = stock.history(period="6mo")
            hist = hist.tail(120)

            if hist.empty:
                response.message(f"ℹ️ {company_name} ({symbol}) data not available.")
                return str(response)

            # Generate candlestick chart
            image_filename = f"{symbol}_chart.png"
            image_path = os.path.join("static", image_filename)
            mpf.plot(hist, type='candle', style='yahoo', volume=True, mav=(10, 20), savefig=image_path)

            # Send price and image URL
            domain = "https://your-railway-app-name.up.railway.app"
            response.message(f"📈 {company_name} ({symbol}): ₹{price}")
            response.message().media(f"{domain}/static/{image_filename}")
            response.message("Thank you! Visit again 😊")

        except Exception as e:
            print("ERROR fetching stock or chart:", str(e))
            response.message("⚠️ Something went wrong while processing your request.")
        user_states[sender] = "initial"
        return str(response)

    # Handle fallback
    if user_state == "stock_mode":
        response.message("❌ Stock not found. Please enter a valid company name or symbol.")
    else:
        response.message("❌ I didn't understand that. Type 'Hi' to start over.")
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
