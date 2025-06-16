from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import re

app = Flask(__name__)

# Load stock data
df = None
symbol_to_name = {}
name_to_symbol = {}

def load_stock_data():
    global df, symbol_to_name, name_to_symbol
    if df is None:
        try:
            STOCKS_CSV_URL = "https://raw.githubusercontent.com/Venkat10292/whatsapp-bot/main/nse_stocks.csv"
            df = pd.read_csv(STOCKS_CSV_URL)
            
            # Create mappings
            symbol_to_name = dict(zip(
                df['Symbol'].str.upper().str.strip(),
                df['Company Name'].str.strip()
            ))
            
            name_to_symbol = dict(zip(
                df['Company Name'].str.lower().str.strip(),
                df['Symbol'].str.upper().str.strip()
            ))
            
        except Exception as e:
            print(f"Error loading stock data: {e}")

def clean_query(query):
    """Clean the search query"""
    query = query.lower().strip()
    # Remove common words and punctuation
    query = re.sub(r'[^\w\s]', '', query)
    query = re.sub(r'\b(?:stock|of|the|and|limited|ltd|co|corporation|inc)\b', '', query)
    return ' '.join(query.split())

def find_best_match(query):
    """Find the best matching stock"""
    query = clean_query(query)
    
    # 1. Check if query matches a symbol exactly
    if query.upper() in symbol_to_name:
        return query.upper(), symbol_to_name[query.upper()]
    
    # 2. Check if query matches a company name exactly (case insensitive)
    if query in name_to_symbol:
        return name_to_symbol[query], symbol_to_name[name_to_symbol[query]]
    
    # 3. Try partial matching in company names
    for company_name in name_to_symbol:
        if query in company_name:
            return name_to_symbol[company_name], symbol_to_name[name_to_symbol[company_name]]
    
    # 4. Try partial matching in symbols
    for symbol in symbol_to_name:
        if query in symbol.lower():
            return symbol, symbol_to_name[symbol]
    
    return None, None

def get_stock_info(symbol):
    return {
        "price": "₹18.74",
        "high": "₹23.63",
        "low": "₹15.82",
        "entry": "₹18.37",
        "exit": "₹19.68"
    }

user_sessions = {}

@app.route("/incoming", methods=['POST'])
def incoming_message():
    load_stock_data()
    
    message = request.form.get('Body', '').strip()
    sender = request.form.get('From')
    response = MessagingResponse()
    
    session = user_sessions.get(sender, {})

    # Handle confirmation
    if session.get("awaiting_confirmation"):
        if message.lower() == "yes":
            symbol = session["suggested"]
            info = get_stock_info(symbol)
            reply = f"""📊 {symbol} ({symbol_to_name.get(symbol, '')})
Price: {info['price']}
52W High: {info['high']}
52W Low: {info['low']}
Suggested Entry: {info['entry']}
Suggested Exit: {info['exit']}"""
        else:
            reply = "Please enter the stock name again (e.g., 'stock: TCS')"
        user_sessions.pop(sender, None)
        response.message(reply)
        return str(response)

    # Handle stock lookup
    if message.lower().startswith(('stock:', 'stock ')):
        query = message.split(':', 1)[-1].strip()
        symbol, company = find_best_match(query)
        
        if symbol:
            user_sessions[sender] = {
                "suggested": symbol,
                "awaiting_confirmation": True
            }
            reply = f"Did you mean: {company} ({symbol})? Reply 'yes' to confirm."
        else:
            # Show suggestions for similar names
            all_names = list(name_to_symbol.keys())
            similar = [name for name in all_names if query in name][:3]
            if similar:
                reply = "Not found. Did you mean:\n" + "\n".join(
                    f"- {name_to_symbol[name]}: {name.title()}" for name in similar
                )
            else:
                reply = "Stock not found. Please try with the exact company name or symbol."
    else:
        reply = ("Welcome to Stock Bot!\n"
                "To search for a stock, send:\n"
                "'stock: COMPANY_NAME' or 'stock: SYMBOL'\n"
                "Example: 'stock: TCS' or 'stock: Tata Consultancy'")

    response.message(reply)
    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
