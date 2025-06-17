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

# Track user states
user_states = {}

@app.route("/")
def home():
    return "WhatsApp Stock Bot is live 🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    try:
        sender = request.form.get("From", "unknown")
        user_msg = request.form.get("Body", "").strip()
        user_state = user_states.get(sender, "initial")
        
        print(f"Received message: '{user_msg}' from {sender} (state: {user_state})")
        print(f"All form data: {dict(request.form)}")
        
        response = MessagingResponse()
        
        # Add debug logging
        print(f"Creating response for: {user_msg}")
    
    # Handle "Hi" or "Hello" - Show menu
    if user_msg.lower() in ["hi", "hello"]:
        reply.body(
            "👋 Welcome to Stock Bot!\n"
            "What can I help you with?\n\n"
            "1️⃣ Stock Analysis 📈\n"
            "2️⃣ Application Support ⚙️\n\n"
            "Please reply with 1 or 2."
        )
        user_states[sender] = "menu"
        print(f"Sending welcome message to {sender}")
        print(f"Response XML: {str(response)}")
        print(f"Final response: {str(response)}")
    return str(response)
    
    # Handle menu choices
    if user_state == "menu":
        if user_msg == "1":
            reply.body("You have selected Stock Analysis.\nPlease enter the company name or stock symbol.")
            user_states[sender] = "stock_mode"
            return str(response)
        elif user_msg == "2":
            reply.body("🔧 This feature is currently under maintenance.")
            user_states[sender] = "initial"
            return str(response)
        else:
            reply.body("❗ Invalid choice. Please reply with 1 or 2.")
            return str(response)
    
    # Handle stock lookup (either in stock_mode or default behavior)
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
        
        # Reset to initial state after stock lookup
        user_states[sender] = "initial"
    else:
        # If no stock found and not in a specific state, show help
        if user_state == "stock_mode":
            reply.body("❌ Stock not found. Please enter a valid company name or symbol.")
        else:
            reply.body("❌ Stock not found. Type 'Hi' to see the menu or enter a valid company name/symbol.")
    
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
