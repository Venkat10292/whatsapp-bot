from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf

app = Flask(__name__)

# Load and normalize stock data
try:
    df = pd.read_csv("nse_stocks.csv")
    df.columns = df.columns.str.strip().str.upper()
    
    symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
    name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))
    print(f"[INFO] Loaded {len(df)} stocks from CSV")
except Exception as e:
    print(f"[ERROR] Failed to load CSV: {e}")
    symbol_to_name = {}
    name_to_symbol = {}

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

    print(f"[DEBUG] From: {sender} | Msg: '{user_msg}' | State: {user_state}")

    response = MessagingResponse()
    reply = response.message()

    try:
        # Step 1: Welcome / Menu - Handle Hi, Hello, or initial state
        if user_msg.lower() in ["hi", "hello", "start"] or user_state == "initial":
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

        # Step 2: Handle Menu Selection
        elif user_state == "menu":
            if user_msg.strip() == "1":
                reply.body(
                    "📈 Stock Analysis\n\n"
                    "Please enter the company name or stock symbol to get the latest price.\n\n"
                    "Example: 'RELIANCE' or 'TCS'"
                )
                user_states[sender] = "awaiting_stock"
                print(f"[DEBUG] State set to 'awaiting_stock' for {sender}")
                return str(response)
            
            elif user_msg.strip() == "2":
                reply.body(
                    "⚙️ Application Support\n\n"
                    "🔧 This feature is currently under maintenance.\n"
                    "Please contact our support team for assistance.\n\n"
                    "Type 'Hi' to return to the main menu."
                )
                user_states[sender] = "initial"
                print(f"[DEBUG] State reset to 'initial' for {sender}")
                return str(response)
            
            else:
                reply.body(
                    "❗ Invalid choice. Please reply with:\n"
                    "1️⃣ for Stock Analysis\n"
                    "2️⃣ for Application Support"
                )
                print(f"[DEBUG] Invalid menu choice: '{user_msg}'")
                return str(response)

        # Step 3: Handle Stock Lookup
        elif user_state == "awaiting_stock":
            if user_msg.lower() in ["hi", "hello", "menu", "back"]:
                # Allow user to go back to menu
                reply.body(
                    "👋 Welcome back to Stock Bot!\n"
                    "What can I help you with?\n\n"
                    "1️⃣ Stock Analysis 📈\n"
                    "2️⃣ Application Support ⚙️\n\n"
                    "Please reply with 1 or 2."
                )
                user_states[sender] = "menu"
                return str(response)
            
            symbol = None
            company_name = None

            # Check if input is a stock symbol
            if user_msg.upper() in symbol_to_name:
                symbol = user_msg.upper()
                company_name = symbol_to_name[symbol]
                print(f"[DEBUG] Found symbol: {symbol} -> {company_name}")
            else:
                # Check if input matches company name
                matches = get_close_matches(user_msg.lower(), name_to_symbol.keys(), n=1, cutoff=0.6)
                if matches:
                    matched_name = matches[0]
                    symbol = name_to_symbol[matched_name]
                    company_name = matched_name.title()
                    print(f"[DEBUG] Found company: {company_name} -> {symbol}")

            if symbol and company_name:
                try:
                    print(f"[DEBUG] Fetching data for {symbol}.NS")
                    stock = yf.Ticker(symbol + ".NS")
                    info = stock.info
                    
                    # Try multiple price fields
                    price = (info.get("regularMarketPrice") or 
                            info.get("currentPrice") or 
                            info.get("previousClose"))
                    
                    if price:
                        reply.body(
                            f"📊 *{company_name}* ({symbol})\n"
                            f"💰 Current Price: ₹{price:.2f}\n\n"
                            f"Type another stock name or 'Hi' for main menu."
                        )
                    else:
                        reply.body(
                            f"ℹ️ Found *{company_name}* ({symbol}), but current price is unavailable.\n\n"
                            f"Type another stock name or 'Hi' for main menu."
                        )
                except Exception as e:
                    print(f"[ERROR] yfinance fetch error for {symbol}: {e}")
                    reply.body(
                        f"⚠️ Found *{company_name}* ({symbol}), but couldn't fetch current price.\n\n"
                        f"Type another stock name or 'Hi' for main menu."
                    )
            else:
                reply.body(
                    f"❌ Stock '{user_msg}' not found in NSE database.\n\n"
                    f"Please try with:\n"
                    f"• Stock symbol (e.g., RELIANCE, TCS)\n"
                    f"• Company name (e.g., Reliance Industries)\n\n"
                    f"Or type 'Hi' for main menu."
                )

            # Keep user in stock lookup state for continuous queries
            print(f"[DEBUG] Keeping user in 'awaiting_stock' state")
            return str(response)

        # Step 4: Fallback for any other state
        else:
            reply.body(
                "⚠️ I didn't understand that.\n"
                "Type 'Hi' to start over."
            )
            user_states[sender] = "initial"
            print(f"[DEBUG] Fallback triggered, resetting to 'initial' for {sender}")
            return str(response)

    except Exception as e:
        print(f"[ERROR] Unexpected error in whatsapp_bot(): {e}")
        reply.body("🚨 Sorry! Something went wrong. Please type 'Hi' to restart.")
        user_states[sender] = "initial"
        return str(response)

if __name__ == "__main__":
    print("[INFO] Starting WhatsApp Stock Bot...")
    app.run(host="0.0.0.0", port=5000, debug=True)
