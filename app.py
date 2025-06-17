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

# OCR Rejection Handling Function
def identify_rejection_reason(ocr_text):
    ocr_text = ocr_text.lower()

    anand_rathi_remarks = {
        "signature mismatch": "Ensure the signature matches your Aadhaar exactly. Update and resubmit the form.",
        "photo unclear": "Submit a clearer, high-quality passport photo.",
        "document invalid": "Submit valid KYC documents like Aadhaar, PAN, or Voter ID."
    }

    rms_rules = {
        "rms: rule don't allow market order": "Market orders are restricted. Use a limit order instead.",
        "no holdings present": "Your account has no eligible holdings. Verify your demat balance or contact support."
    }

    for reason, solution in anand_rathi_remarks.items():
        if reason in ocr_text:
            return f"\U0001F4CC *Anand Rathi Rejection*: **{reason.capitalize()}**", solution

    for reason, solution in rms_rules.items():
        if reason in ocr_text:
            return f"\U0001F4CC *System RMS Rule Triggered*: **{reason.capitalize()}**", solution

    return "\u2753 Unable to identify the rejection reason clearly.", "Please upload a clearer image or contact support."

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
            response.message("\u2757 Invalid choice. Please reply with 1 or 2.")
            return str(response)

    if user_state == "upload_image" and user_media_url:
        try:
            from urllib.request import urlopen
            img_data = urlopen(user_media_url).read()
            image = Image.open(BytesIO(img_data))
            text = pytesseract.image_to_string(image)
            reason, solution = identify_rejection_reason(text)
            response.message(f"{reason}\n\n📄 Solution:\n{solution}")
        except Exception as e:
            logging.error(f"OCR Error: {e}")
            response.message("\u274c Error processing the image. Please try again.")
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
            response.message("\u26a0️ Could not fetch stock details or generate chart.")

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
