from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import yfinance as yf

app = Flask(__name__)

@app.route("/incoming", methods=['POST'])
def incoming_message():
    message = request.form.get('Body').strip().lower()
    response = MessagingResponse()

    if message.startswith("stock:"):
        stock_symbol = message.split(":")[1].strip().upper()
        try:
            stock = yf.Ticker(stock_symbol)
            data = stock.history(period="1d")

            if data.empty:
                response.message(f"⚠️ Couldn't find data for {stock_symbol}")
            else:
                price = round(data['Close'][-1], 2)
                info = stock.info
                high_52w = round(info.get('fiftyTwoWeekHigh', 0), 2)
                low_52w = round(info.get('fiftyTwoWeekLow', 0), 2)

                response.message(
                    f"📊 *{stock_symbol}*\n"
                    f"Price: ₹{price}\n"
                    f"52W High: ₹{high_52w}\n"
                    f"52W Low: ₹{low_52w}\n"
                    f"Suggested Entry: ₹{round(price * 0.98, 2)}\n"
                    f"Suggested Exit: ₹{round(price * 1.05, 2)}"
                )
        except Exception as e:
            response.message("⚠️ Error fetching stock data. Please try again.")
    else:
        response.message("Hi! To get stock info, send:\n*stock: TCS*")

    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
