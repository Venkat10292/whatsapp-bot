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

# Track each user's state
user_states = {}

@app.route("/")
def home():
    return "WhatsApp Stock Bot is Live 🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    user_state = user_states.get(sender, "initial")

    print(f"[DEBUG] From: {sender} | Msg: {user_msg} | State: {user_state}")

    response = MessagingResponse()
    reply = response.message()

    try:
        # Step 1: Welcome / Menu
        if user_msg.lower() in ["hi", "hello"] or user_state == "initial":
            reply.body(
                "👋 Welcome to Stock Bot!\n"
                "What can I help you with?\n\n"
                "1️⃣ Stock Analysis 📈\n"
                "2️⃣ Application Support ⚙️\n\n"
                "Please reply with 1 or 2."
            )
            user_states[sender] = "menu"
            print(f"[DEBUG] State set to 'menu' for {sender}")
            return str(response)

        # Step 2: Handle Menu
        if user_state == "menu":
            if user_msg == "1":
                reply.body("You have selected Stock Analysis.\nPlease enter the company name or stock symbol.")
                user_states[sender] = "awaiting_stock"
                print(f"[DEBUG] State set to 'awaiting_stock' for {sender}")
                return str(response)
            elif user_msg == "2":
                reply.body("🔧 This feature is currently under maintenance.")
                user_states[sender] = "initial"
                print(f"[DEBUG] State reset to 'initial' for {sender}")
                return str(response)
            else:
                reply.body("❗ Invalid choice. Please reply with 1 or 2.")
                return str(response)

        # Step 3: Handle Stock Lookup
        if user_state == "awaiting_stock":
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
                        reply.body(f"ℹ️ Found {company_name} ({symbol}), but price is unavailable.")
                except Exception as e:
                    print(f"[ERROR] yfinance fetch error: {e}")
                    reply.body("⚠️ Could not fetch stock price.")
            else:
                reply.body("❌ Stock not found. Please try again with a correct name or symbol.")

            user_states[sender] = "initial"
            print(f"[DEBUG] State reset to 'initial' after stock check for {sender}")
            return str(response)

        # Step 4: Fallback for undefined flow
        reply.body("⚠️ I didn’t understand that. Please type 'Hi' to begin.")
        user_states[sender] = "initial"
        print(f"[DEBUG] Fallback triggered for {sender}")
        return str(response)

    except Exception as e:
        print(f"[ERROR] Unexpected issue: {e}")
        reply.body("🚨 Sorry! Something went wrong. Please try again.")
        return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
