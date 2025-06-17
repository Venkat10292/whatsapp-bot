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
    print("\n--- NEW REQUEST ---")
    print("RAW FORM DATA:", request.form)

    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    user_state = user_states.get(sender, "initial")

    print(f"Received message: '{user_msg}' from {sender} (state: {user_state})")

    response = MessagingResponse()

    if user_msg.lower() in ["hi", "hello"]:
        response.message(
            "👋 Welcome to Stock Bot!\n"
            "1️⃣ Stock Analysis 📈\n"
            "2️⃣ Application Support ⚙️\n\n"
            "Please reply with 1 or 2."
        )
        user_states[sender] = "menu"
        print("State changed to 'menu'")
        return str(response)

    if user_state == "menu":
        if user_msg == "1":
            response.message("You selected Stock Analysis. Send stock name or symbol.")
            user_states[sender] = "stock_mode"
            print("State changed to 'stock_mode'")
            return str(response)
        elif user_msg == "2":
            response.message("🔧 Application Support is under maintenance.")
            user_states[sender] = "initial"
            print("Support selected — under maintenance")
            return str(response)
        else:
            response.message("❗ Invalid choice. Reply with 1 or 2.")
            print("Invalid menu choice")
            return str(response)

    symbol = None
    company_name = None

    if user_msg.upper() in symbol_to_name:
        symbol = user_msg.upper()
        company_name = symbol_to_name[symbol]
        print(f"Matched SYMBOL directly: {symbol} = {company_name}")
    else:
        matches = get_close_matches(user_msg.lower(), name_to_symbol.keys(), n=1, cutoff=0.6)
        if matches:
            matched_name = matches[0]
            symbol = name_to_symbol[matched_name]
            company_name = matched_name.upper()
            print(f"Matched NAME: {matched_name} → {symbol}")
        else:
            print("No match found for stock")

    if symbol and company_name:
        try:
            full_symbol = symbol + ".NS"
            stock = yf.Ticker(full_symbol)
            print(f"Fetching stock data for {full_symbol}")
            price = stock.info.get("regularMarketPrice", None)
            print(f"Market Price: ₹{price}" if price else "Price not found")

            # Get last 120 daily candles
            print("Fetching historical data...")
            hist = stock.history(period="6mo")[-120:]

            if hist.empty:
                raise Exception("Empty history received.")

            # Save chart
            os.makedirs("static", exist_ok=True)
            img_path = f"static/{symbol}_chart.png"
            print(f"Saving chart to {img_path}...")
            mpf.plot(hist, type='candle', style='charles', volume=False, title=f'{company_name} Chart',
                     mav=(20, 50), savefig=img_path)
            print("Chart saved.")

            if price:
                response.message(f"📈 {company_name} ({symbol}): ₹{price}")
            else:
                response.message(f"ℹ️ {company_name} ({symbol}) found. Price unavailable.")

            response.message().media(f"{request.url_root}static/{symbol}_chart.png")
            response.message("✅ Chart generated.\nThank you! Visit again 😊")

        except Exception as e:
            print(f"❌ Error: {e}")
            response.message("⚠️ Failed to fetch stock info or chart.")

        user_states[sender] = "initial"
    else:
        print("Symbol not found or invalid.")
        if user_state == "stock_mode":
            response.message("❌ Stock not found. Try another name or symbol.")
        else:
            response.message("❌ Invalid input. Type 'Hi' to start again.")

    print("Final XML response:", str(response))
    return str(response)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
