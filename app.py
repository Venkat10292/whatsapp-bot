from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
from requests.auth import HTTPBasicAuth
import pandas as pd
from difflib import get_close_matches
import mplfinance as mpf
import os
import logging
import base64
import openai
from io import BytesIO
import pytesseract
from PIL import Image
import tempfile
import requests
import cv2
import numpy as np
import uuid
from pg_db import init_db, is_user_authorized, add_user

app = Flask(__name__)

# Initialize DB
init_db()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load API Keys
openai.api_key = os.getenv("OPENAI_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

print("✅ Alpha Vantage API Key Loaded:", ALPHA_VANTAGE_API_KEY)

# Load CSV and build stock dictionaries
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()
symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

user_states = {}

REJECTION_SOLUTIONS = {
    "MTF Scripwise exposure breached": "You’ve hit the MTF limit for this stock. Try reducing your MTF exposure or placing a CNC order instead.",
    "Security is not allowed to trade in this market": "This security is restricted. Try trading it on a different exchange or contact support.",
    "No holdings present": "You are trying to sell a stock you don't currently hold. Check your demat holdings before retrying.",
    "Only board lot market orders are allowed": "Try placing your order in market lot size or convert it to a market order.",
    "Assigned basket for entity account": "This stock is tied to a specific basket. Please verify your product type or consult with your broker.",
    "Check T1 holdings": "This may be a T1 settlement stock or under restrictions like BE/Z/Trade-to-Trade. Check settlement cycle or try CNC mode."
}

def get_daily_data(symbol, output_size="compact"):
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": f"{symbol}.NS",
        "apikey": ALPHA_VANTAGE_API_KEY,
        "outputsize": output_size,
        "datatype": "json"
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()

    key = "Time Series (Daily)"
    if not data or key not in data:
        raise Exception(f"Alpha Vantage error or rate limit exceeded. Response: {data}")

    df = pd.DataFrame(data[key]).T
    df.columns = [
        "Open", "High", "Low", "Close", "Adjusted Close",
        "Volume", "Dividend Amount", "Split Coefficient"
    ]
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df

def preprocess_image_for_ocr(img_path):
    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    denoised = cv2.medianBlur(thresh, 3)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(temp_file.name, denoised)
    return temp_file.name

def detect_reason_with_fuzzy(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        for reason in REJECTION_SOLUTIONS:
            matches = get_close_matches(reason.lower(), [line.lower()], n=1, cutoff=0.5)
            if matches:
                return reason, REJECTION_SOLUTIONS[reason]
    return None, "We couldn’t match the reason to known issues. Please contact support."

def extract_rejection_reason(image_path):
    processed_path = preprocess_image_for_ocr(image_path)
    img = Image.open(processed_path)
    text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
    return detect_reason_with_fuzzy(text)

def is_authorized(sender):
    if sender.startswith("whatsapp:"):
        sender = sender.replace("whatsapp:", "").strip()
    if sender.startswith("+91"):
        sender = sender[3:]
    return is_user_authorized(sender)

@app.route("/")
def home():
    return "✅ WhatsApp Stock Bot is live!"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    media_url = request.form.get("MediaUrl0")
    user_state = user_states.get(sender, "initial")

    response = MessagingResponse()

    if not is_authorized(sender):
        response.message("🚫 Access denied. Please contact admin to get access.")
        return str(response)

    if media_url:
        if user_state == "awaiting_rejection_image":
            r = requests.get(media_url, auth=HTTPBasicAuth(os.getenv("TWILIO_SID"), os.getenv("TWILIO_AUTH_TOKEN")))
            if r.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
                    temp.write(r.content)
                    temp_path = temp.name
                reason, solution = extract_rejection_reason(temp_path)
                response.message(f"❌ *Reason:* {reason}\n*Solution:* {solution}")
            else:
                response.message("⚠️ Couldn't fetch the image. Please try again.")
            user_states[sender] = "initial"
            return str(response)
        else:
            response.message("📸 Image received. To analyze rejection, type '2' first.")
            return str(response)

    if user_msg.lower() in ["hi", "hello"]:
        response.message("👋 Welcome to Stock Bot!\n1️⃣ Stock Analysis\n2️⃣ Application Support\nType 1 or 2 to continue.")
        user_states[sender] = "menu"
        return str(response)

    if user_state == "menu":
        if user_msg == "1":
            response.message("📈 Enter stock symbol or company name.")
            user_states[sender] = "stock_mode"
        elif user_msg == "2":
            response.message("📷 Upload your order rejection screenshot.")
            user_states[sender] = "awaiting_rejection_image"
        else:
            response.message("❗ Please reply with 1 or 2.")
        return str(response)

    symbol, company_name = None, None
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
            hist_full = get_daily_data(symbol)
            price = hist_full['Close'].iloc[-1]
            if price:
                response.message(f"📈 {company_name} ({symbol}): ₹{price}\nGenerating chart...")
                if not os.path.exists("static"):
                    os.makedirs("static")
                chart_filename = f"{symbol}_{uuid.uuid4().hex[:6]}.png"
                chart_path = os.path.join("static", chart_filename)
                mpf.plot(hist_full[-120:], type='candle', style='yahoo', title=symbol, volume=True, savefig=chart_path)
                with open(chart_path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode("utf-8")
                chat_response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a stock market expert. Give detailed insights."},
                        {"role": "user", "content": [
                            {"type": "text", "text": f"Analyze chart for {company_name} (₹{price})."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
                        ]}
                    ],
                    max_tokens=300
                )
                ai_reply = chat_response.choices[0].message.content.strip()
                msg = response.message(f"📊 {company_name} ({symbol}): ₹{price}\n\n{ai_reply}")
                msg.media(f"https://whatsapp-bot-production-20ba.up.railway.app/static/{chart_filename}")
            else:
                response.message(f"ℹ️ Found {company_name} but no market price available.")
        except Exception as e:
            logging.error(f"❌ Stock error for {symbol}: {e}")
            response.message(f"⚠️ Couldn't retrieve stock data: {e}")
        user_states[sender] = "initial"
    else:
        if user_state == "stock_mode":
            response.message("❌ Stock not found. Try a valid symbol or name.")
        else:
            response.message("❌ Invalid input. Type 'Hi' to restart.")

    return str(response)

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

@app.route("/add_user/<mobile>/<email>/<longname>")
def add_test_user(mobile, email, longname):
    add_user(mobile, email, longname)
    return f"✅ Added user: {longname} ({mobile})"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
