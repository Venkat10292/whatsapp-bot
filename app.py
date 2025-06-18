from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
import os
import logging
from io import BytesIO
from urllib.request import urlopen
import pytesseract
from PIL import Image
import pandas as pd
from difflib import get_close_matches
import openai

from stock_analysis import fetch_stock_chart, get_ai_stock_analysis
from ocr_utils import identify_rejection_reason

app = Flask(__name__)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
openai.api_key = os.getenv("OPENAI_API_KEY")

# Load and normalize stock CSV
df = pd.read_csv("nse_stocks.csv")
df.columns = df.columns.str.strip().str.upper()
symbol_to_name = dict(zip(df["SYMBOL"].str.strip().str.upper(), df["NAME OF COMPANY"].str.strip()))
name_to_symbol = dict(zip(df["NAME OF COMPANY"].str.strip().str.lower(), df["SYMBOL"].str.strip().str.upper()))

# User state tracking
user_states = {}

@app.route("/")
def home():
    return "WhatsApp Stock Bot is live now🚀"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From", "unknown")
    user_msg = request.form.get("Body", "").strip()
    user_media_url = request.form.get("MediaUrl0")
    user_state = user_states.get(sender, "initial")

    logging.info(f"Received message: '{user_msg}' from {sender} (state: {user_state})")
    response = MessagingResponse()

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
            response.message("You have selected Stock Analysis.\nPlease enter the company name or stock symbol.")
            user_states[sender] = "stock_mode"
            return str(response)
        elif user_msg == "2":
            response.message("Please upload the rejection screenshot image.")
            user_states[sender] = "upload_image"
            return str(response)
        else:
            response.message("❗ Invalid choice. Please reply with 1 or 2.")
            return str(response)

    if user_state == "upload_image" and user_media_url:
        try:
            img_data = urlopen(user_media_url).read()
            image = Image.open(BytesIO(img_data))
            text = pytesseract.image_to_string(image)
            reason, solution = identify_rejection_reason(text)
            response.message(f"{reason}\n\n📄 Solution:\n{solution}")
        except Exception as e:
            logging.error(f"OCR Error: {e}")
            response.message("❌ Error processing the image. Please try again.")
        user_states[sender] = "initial"
        return str(response)

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
            stock_price = openai.api_key  # Just to ensure API key is loaded
            chart_path, ai_reply = generate_stock_analysis(symbol, company_name, stock_price, openai)
            msg = response.message(f"📈 {company_name} ({symbol}) Analysis:\n\n{ai_reply}")
            msg.media(f"https://your-url/static/{symbol}_chart.png")
        except Exception as e:
            logging.error(f"Error: {e}")
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
