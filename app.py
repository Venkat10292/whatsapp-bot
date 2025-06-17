from flask import Flask, request, send_from_directory
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

# Ensure 'static' folder exists
if not os.path.exists("static"):
    os.makedirs("static")

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
            response_msg = f"📈 {company_name} ({symbol}): ₹{price}" if price else f"ℹ️ {company_name} ({symbol}) found, but price is unavailable."

            # Generate chart image
            hist = stock.history(period="6mo", interval="1d").tail(120)
            if not hist.empty:
                chart_file = f"static/{symbol}_chart.png"
                mpf.plot(hist, type="candle", style="yahoo", title=f"{symbol} - Last 120 Days", savefig=chart_file)

                # Attach image + message
                msg = response.message(response_msg)
                msg.media(request.url_root + chart_file)
                response.message("✅ Chart generated!\nThank you! Visit again 😊")
            else:
                response.message(response_msg + "\n⚠️ Not enough chart data to generate image.")

        except Exception as e:
            print(f"Error: {e}")
            response.message("⚠️ Could not fetch stock data.")

        user_states[sender] = "initial"
    else:
        if user_state == "stock_mode":
            response.message("❌ Stock not found. Please enter a valid company name or symbol.")
        else:
            response.message("❌ Stock not found. Type 'Hi' to see the menu or enter a valid name/symbol.")

    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
