from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf
import mplfinance as mpf
import os

app = Flask(__name__)

# Load and normalize the CSV
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()

# Build lookup dictionaries
symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

# Track user states
user_states = {}

@app.route("/")
def home():
    return "WhatsApp Stock Bot is live 🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    user_state = user_states.get(sender, "initial")
    
    response = MessagingResponse()
    
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

    # Try to match user input to stock
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

            # Fetch last 120 daily bars
            hist = stock.history(period="150d")[-120:]
            if not hist.empty:
                filename = f"{symbol}_chart.png"
                image_path = f"static/{filename}"
                mpf.plot(hist, type="candle", style="charles", title=f"{company_name} - Last 120 Days",
                         ylabel="Price (INR)", volume=True, savefig=image_path)

                msg = response.message(f"📈 {company_name} ({symbol}): ₹{price}\nHere is the recent 120-day chart 📊")
                msg.media(f"https://whatsapp-bot-production-20ba.up.railway.app/{image_path}")
            else:
                response.message(f"ℹ️ No historical chart data available for {company_name} ({symbol}).")
        except Exception as e:
            print(f"Error fetching data/chart: {e}")
            response.message("⚠️ Could not fetch stock data.")

        # Add closing message
        response.message("✅ Thank you! Visit again 😊")
        user_states[sender] = "initial"
    else:
        if user_state == "stock_mode":
            response.message("❌ Stock not found. Please enter a valid company name or symbol.")
        else:
            response.message("❌ Stock not found. Type 'Hi' to see the menu or enter a valid company name/symbol.")

    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
