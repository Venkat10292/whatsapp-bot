from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from difflib import get_close_matches
import yfinance as yf

app = Flask(__name__)

# Load your stock CSV (example columns: 'Name', 'Symbol')
df = pd.read_csv("nse_stocks.csv")
stock_dict = dict(zip(df["Name"].str.lower(), df["Symbol"]))

@app.route("/bot", methods=["POST"])
def whatsapp_bot():
    user_msg = request.form.get("Body").strip().lower()
    response = MessagingResponse()
    reply = response.message()

    # Match closest stock name
    matches = get_close_matches(user_msg, stock_dict.keys(), n=1, cutoff=0.6)
    
    if matches:
        matched_name = matches[0]
        symbol = stock_dict[matched_name]
        try:
            stock = yf.Ticker(symbol + ".NS")  # NSE stocks need .NS suffix
            price = stock.info.get("regularMarketPrice", None)
            if price:
                reply.body(f"📈 {matched_name.title()} ({symbol}): ₹{price}")
            else:
                reply.body("❌ Couldn't fetch the price. Try again later.")
        except Exception as e:
            reply.body("⚠️ Error fetching data: " + str(e))
    else:
        reply.body("❌ No matching stock found. Please try again.")

    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
