from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
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

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Load and normalize the CSV
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()

# Build lookup dictionaries
symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

# Track user states
user_states = {}

# Known rejection reasons and solutions
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
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    denoised = cv2.medianBlur(thresh, 3)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(temp_file.name, denoised)
    return temp_file.name

def detect_reason_with_fuzzy(text):
    for reason in REJECTION_SOLUTIONS:
        matches = get_close_matches(reason.lower(), [text.lower()], n=1, cutoff=0.5)
        if matches:
            return reason, REJECTION_SOLUTIONS[reason]
    return None, "We couldn’t match the reason to known issues. Please contact support with the screenshot."

def extract_rejection_reason(image_path):
    try:
        processed_path = preprocess_image_for_ocr(image_path)
        img = Image.open(processed_path)
        text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
        logging.info(f"OCR Extracted Text:\n{text}")

        reason, solution = detect_reason_with_fuzzy(text)
        return reason, solution

    except Exception as e:
        logging.error(f"OCR error: {e}")
        return None, "Failed to process image. Please send a clearer picture."

@app.route("/")
def home():
    return "WhatsApp Stock Bot is live now🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    user_state = user_states.get(sender, "initial")
    media_url = request.form.get("MediaUrl0")

    logging.info(f"Received message: '{user_msg}' from {sender} (state: {user_state})")

    response = MessagingResponse()

    # Handle image upload
    if media_url:
        logging.info(f"Received media from {sender}: {media_url}")
        if user_state == "awaiting_rejection_image":
            try:
                r = requests.get(media_url)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
                    temp.write(r.content)
                    temp_path = temp.name

                reason, solution = extract_rejection_reason(temp_path)

                if reason:
                    response.message(
                        f"❌ *Order Rejection Reason Detected:*\n\n"
                        f"*Reason*: {reason}\n"
                        f"*Solution*: {solution}"
                    )
                else:
                    response.message(solution)

            except Exception as e:
                logging.error(f"Failed to process image: {e}")
                response.message("⚠️ Failed to analyze the rejection reason. Please try again with a clearer image.")
            
            user_states[sender] = "initial"
            return str(response)
        else:
            response.message("ℹ️ You sent an image. To analyze a rejection, please first choose '2' from the menu.")
            return str(response)

    # Main menu
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

    # Handle menu selection
    if user_state == "menu":
        if user_msg == "1":
            response.message("You have selected Stock Analysis.\nPlease enter the company name or stock symbol.")
            user_states[sender] = "stock_mode"
            return str(response)
        elif user_msg == "2":
            response.message("📤 Please upload a screenshot of your order rejection message.\nI’ll analyze it and share the solution.")
            user_states[sender] = "awaiting_rejection_image"
            return str(response)
        else:
            response.message("❗ Invalid choice. Please reply with 1 or 2.")
            return str(response)

    # Stock analysis
    symbol = None
    company_name = None

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
                response.message(f"📈 {company_name} ({symbol}): ₹{price}\nGenerating analysis, please wait...")

                hist = stock.history(period="6mo")
                chart_path = f"static/{symbol}_chart.png"

                if not os.path.exists("static"):
                    os.makedirs("static")

                mpf.plot(hist[-120:], type='candle', style='yahoo', title=symbol, volume=True, savefig=chart_path)
                logging.info(f"Chart generated: {chart_path}")

                with open(chart_path, "rb") as img_file:
                    encoded_image = base64.b64encode(img_file.read()).decode("utf-8")

                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a highly skilled stock market analyst. Your job is to analyze candlestick charts and provide actionable trading insights. "
                            "Based on the chart image, give a concise summary that includes:\n"
                            "- Current trend (bullish, bearish, or sideways)\n"
                            "- Safe entry and exit points\n"
                            "- Aggressive entry and exit points if visible\n"
                            "- Identified patterns (like head and shoulders, double top, triangle, etc.)\n"
                            "- Strong support and resistance levels\n"
                            "- Risk level (low/medium/high)\n"
                            "- Your final opinion: whether it's a good time to enter the trade or wait"
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Analyze this chart of {company_name} (₹{price})."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
                        ]
                    }
                ]

                chat_response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=300
                )

                ai_reply = chat_response.choices[0].message.content.strip()

                msg = response.message(f"📈 {company_name} ({symbol}): ₹{price}\n\n{ai_reply}")
                msg.media(f"https://whatsapp-bot-production-20ba.up.railway.app/static/{symbol}_chart.png")
            else:
                response.message(f"ℹ️ {company_name} ({symbol}) found, but price is unavailable.")
        except Exception as e:
            logging.error(f"Error fetching stock price or generating chart: {e}")
            response.message("⚠️ Could not fetch stock details or generate chart.")
        user_states[sender] = "initial"
    else:
        if user_state == "stock_mode":
            response.message("❌ Stock not found. Please enter a valid company name or symbol.")
        else:
            response.message("❌ Stock not found. Type 'Hi' to see the menu or enter a valid company name/symbol.")

    return str(response)

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
