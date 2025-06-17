from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf

app = Flask(__name__)

# Raw CSV from your public GitHub repo
CSV_URL = "https://raw.githubusercontent.com/Venkat10292/whatsapp-bot/main/nse_stocks.csv"

# Load and clean CSV
df = pd.read_csv(CSV_URL)
df.columns = df.columns.str.strip().str.upper()  # Clean headers
df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip().str.upper()
df["NAME OF COMPANY"] = df["NAME OF COMPANY"].astype(str).str.strip().str.upper()

# Create dictionaries
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.lower(), df["SYMBOL"]))
symbol_to_name = dict(zip(df["SYMBOL"], df["NAME OF COMPANY"]))

@app.route("/bot", methods=["POST"])
def whatsapp_bot():
    user_msg = request.form.get("Body", "").strip().upper()
    response = MessagingResponse()
    reply = response.message()

    symbol = None
    company_name = None

    # Check if input is exact symbol
    if user_msg in symbol_to_name:
        symbol = user_msg
        company_name = symbol_to_name[symbol]

    # Check if input closely matches a company name
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
                reply.body(f"📈 {company_name} ({symbol}): ₹{price}")
            else:
                reply.body(f"ℹ️ {company_name} ({symbol}) found, but price is unavailable.")
        except Exception as e:
            reply.body(f"⚠️ Error fetching stock data: {str(e)}")
    else:
        reply.body("❌ No matching stock found. Please enter a valid company name or symbol.")

    return str(response)

if __name__ == "__main__":
    app.run(debug=True)
