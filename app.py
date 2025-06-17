@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    user_msg = request.form.get("Body", "").strip().upper()
    print(f"Received message: {user_msg}")  # Debug log

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
            print(f"Fetching price for: {symbol}.NS")
            price = stock.info.get("regularMarketPrice", None)
            if price:
                reply.body(f"📈 {company_name} ({symbol}): ₹{price}")
            else:
                reply.body(f"ℹ️ {company_name} ({symbol}) found, but price is unavailable.")
        except Exception as e:
            print("Error fetching from yfinance:", e)
            reply.body("⚠️ Failed to get stock price.")
    else:
        reply.body("❌ No matching stock found. Please enter a valid company name or symbol.")

    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
