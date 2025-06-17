from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf

app = Flask(__name__)

# Load the CSV and clean headers
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()  # Normalize headers

# Create lookup dictionary
stock_dict = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip()))

@app.route("/bot", methods=["POST"])
def whatsapp_bot():
    user_msg = request.form.get("Body").strip().lower()
    response = MessagingResponse()
    reply = response.message()

    # Find the closest stock name
    matches = get_close_matches(user_msg, stock_dict.keys(), n=1, cutoff=0.6)

    if matches:
        matched_name = matches[0]
        symbol = stock_dict[matched_name]
        try:
            stock = yf.Ticker(symbol + ".NS")  # NSE symbols need '.NS'
            price = stock.info.get("regularMarketPrice", None)
            if price:
                reply.body(f"📊 {matched_name.title()} ({symbol}): ₹{price}")
            else:
                reply.body("❌ Couldn't fetch the stock price.")
        except Exception as e:
            reply.body(f"⚠️ Error fetching stock data: {str(e)}")
    else:
        reply.body("❌ Stock not found. Please enter a valid company name.")

    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
