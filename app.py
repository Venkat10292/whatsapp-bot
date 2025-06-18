from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
from requests.auth import HTTPBasicAuth
import pandas as pd
from difflib import get_close_matches
import yfinance as yf
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
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load OpenAI key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Load CSV and build stock name dictionaries
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()
symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

user_states = {}

# Google Sheets Authentication
def get_authorized_numbers():
    try:
        creds_dict = json.loads(os.getenv("google_sheet_credentials"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("BotAccessList").sheet1  # Change to your sheet name
        numbers = sheet.col_values(1)
        return set(numbers)
    except Exception as e:
        logging.error(f"❌ Error loading Google Sheet: {e}")
        return set()

def is_authorized(sender):
    return sender in get_authorized_numbers()

REJECTION_SOLUTIONS = {
    "MTF Scripwise exposure breached": "You’ve hit the MTF limit for this stock. Try reducing your MTF exposure or placing a CNC order instead.",
    "Security is not allowed to trade in this market": "This security is restricted. Try trading it on a different exchange or contact support.",
    "No holdings present": "You are trying to sell a stock you don't currently hold. Check your demat holdings before retrying.",
    "Only board lot market orders are allowed": "Try placing your order in market lot size or convert it to a market order.",
    "Assigned basket for entity account": "This stock is tied to a specific basket. Please verify your product type or consult with your broker.",
    "Check T1 holdings": "This may be a T1 settlement stock or under restrictions like BE/Z/Trade-to-Trade. Check settlement cycle or try CNC mode."
}

def preprocess_image_for_ocr(img_path):
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"Image at path '{img_path}' could not be loaded.")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    denoised = cv2.medianBlur(thresh, 3)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(temp_file.name, denoised)
    return temp_file.name

def detect_reason_with_fuzzy(text):
    logging.info(f"🔍 Full extracted OCR text:\n{text}")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        for reason in REJECTION_SOLUTIONS:
            matches = get_close_matches(reason.lower(), [line.lower()], n=1, cutoff=0.5)
            if matches:
                logging.info(f"✅ Fuzzy match found: '{reason}' in line: '{line}'")
                return reason, REJECTION_SOLUTIONS[reason]
    logging.warning("⚠️ No match found for rejection reason.")
    return None, "We couldn’t match the reason to known issues. Please contact support with the screenshot."

def extract_rejection_reason(image_path):
    try:
        processed_path = preprocess_image_for_ocr(image_path)
        img = Image.open(processed_path)
        text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
        return detect_reason_with_fuzzy(text)
    except Exception as e:
        logging.error(f"❌ OCR processing error: {e}")
        return None, "Failed to process image. Please send a clearer picture."

@app.route("/")
def home():
    return "WhatsApp Stock Bot is live now 🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    user_state = user_states.get(sender, "initial")
    media_url = request.form.get("MediaUrl0")

    response = MessagingResponse()

    if not is_authorized(sender):
        response.message("🚫 Access denied.\nPlease open an account with AnandRathi under *Satish Kumar G* to use this bot.")
        return str(response)

    logging.info(f"📩 Message: '{user_msg}' | State: {user_state} | Sender: {sender}")

    if media_url:
        logging.info(f"📸 Media received from {sender}: {media_url}")
        if user_state == "awaiting_rejection_image":
            try:
                r = requests.get(
                    media_url,
                    auth=HTTPBasicAuth(os.getenv("TWILIO_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
                )
                if r.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
                        temp.write(r.content)
                        temp_path = temp.name
                    logging.info(f"✅ Image downloaded at: {temp_path}")
                    reason, solution = extract_rejection_reason(temp_path)
                    if reason:
                        response.message(f"❌ *Order Rejection Reason:*\n\n*Reason*: {reason}\n*Solution*: {solution}")
                    else:
                        response.message(solution)
                else:
                    logging.error(f"❌ Failed to download image. Status code: {r.status_code}")
                    response.message("⚠️ Couldn't fetch the image. Please try again.")
            except Exception as e:
                logging.error(f"❌ Exception while handling image: {e}")
                response.message("⚠️ Error analyzing the image. Please upload a clearer one.")
            user_states[sender] = "initial"
            return str(response)
        else:
            response.message("ℹ️ Image received. To analyze a rejection, type '2' first.")
            return str(response)

    if user_msg.lower() in ["hi", "hello"]:
        response.message(
            "👋 Welcome to Stock Bot!\n"
            "What can I help you with today?\n\n"
            "1️⃣ Stock Analysis 📈\n"
            "2️⃣ Application Support ⚙️\n\n"
            "Please reply with 1 or 2."
        )
        user_states[sender] = "menu"
        return str(response)

    if user_state == "menu":
        if user_msg == "1":
            response.message("📊 Please enter a stock symbol or company name.")
            user_states[sender] = "stock_mode"
        elif user_msg == "2":
            response.message("📤 Upload the screenshot of your order rejection. I’ll analyze and respond.")
            user_states[sender] = "awaiting_rejection_image"
        else:
            response.message("❗ Please type 1 or 2.")
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
            stock = yf.Ticker(symbol + ".NS")
            price = stock.info.get("regularMarketPrice", None)

            if price:
                response.message(f"📈 {company_name} ({symbol}): ₹{price}\nGenerating chart...")
                hist = stock.history(period="6mo")

                if not os.path.exists("static"):
                    os.makedirs("static")

                unique_id = uuid.uuid4().hex[:6]
                chart_filename = f"{symbol}_chart_{unique_id}.png"
                chart_path = f"static/{chart_filename}"

                mpf.plot(hist[-120:], type='candle', style='yahoo', title=symbol, volume=True, savefig=chart_path)

                with open(chart_path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode("utf-8")

                chat_response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": (
                            "You are a skilled stock market analyst. Give:\n"
                            "- Trend (bullish/bearish/sideways)\n"
                            "- Entry/exit points\n"
                            "- Patterns\n"
                            "- Support/resistance\n"
                            "- Risk level\n"
                            "- Final advice (buy/sell/wait)"
                        )},
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
            logging.error(f"❌ Stock error: {e}")
            response.message("⚠️ Couldn't retrieve stock data.")
        user_states[sender] = "initial"
    else:
        if user_state == "stock_mode":
            response.message("❌ Stock not found. Try a valid symbol or company name.")
        else:
            response.message("❌ Invalid input. Type 'Hi' to restart.")

    return str(response)

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
