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
import requests
import pytesseract
from PIL import Image
import tempfile
import cv2
import numpy as np
import uuid
import pyotp
from pg_db import init_db, is_user_authorized, add_user
from SmartApi.smartConnect import SmartConnect
import inspect
from datetime import datetime, timedelta

# 🛠️ Patch SmartConnect to ignore unexpected 'proxies' argument
sig = inspect.signature(SmartConnect.__init__)
if 'proxies' in sig.parameters:
    params = [p for p in sig.parameters.values() if p.name != 'proxies']
    SmartConnect.__init__.__signature__ = sig.replace(parameters=params)

# Remove any HTTP(S) proxy env vars
for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(key, None)

app = Flask(__name__)
init_db()
# 🔁 Keeps track of user interaction state (e.g., menu, stock_mode)
user_states = {}
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
openai.api_key = os.getenv("OPENAI_API_KEY")

# Angel One credentials
angel_key = os.getenv("ANGEL_API_KEY")
angel_id = os.getenv("ANGEL_CLIENT_ID")
angel_pin = os.getenv("ANGEL_PIN")
angel_totp = os.getenv("ANGEL_TOTP")

# Authenticate with Angel One
totp_code = pyotp.TOTP(angel_totp).now()
smart = SmartConnect(api_key=angel_key)
login_data = smart.generateSession(angel_id, angel_pin, totp_code)
if not login_data.get("data"):
    logging.error("Angel login failed: %s", login_data)

# Load scrip master CSV
df = pd.read_csv("scrip_master.csv")
df.columns = df.columns.str.strip().str.lower()
df["symbol_clean"] = df["symbol_clean"].str.strip().str.lower()
symbol_to_name = dict(zip(df["symbol"].str.upper(), df["name"]))
name_to_symbol = {n.strip().lower(): s for s, n in symbol_to_name.items()}
name_to_symbol.update({c: s for c, s in zip(df["symbol_clean"], df["symbol"].str.upper())})

REJECTION_SOLUTIONS = {
    "MTF Scripwise exposure breached": "You’ve hit the MTF limit for this stock...",
    "Security is not allowed to trade in this market": "This security is restricted...",
    "No holdings present": "You are trying to sell a stock you don't currently hold...",
    "Only board lot market orders are allowed": "Try placing your order in market lot size...",
    "Assigned basket for entity account": "This stock is tied to a specific basket...",
    "Check T1 holdings": "This may be a T1 settlement stock or under restrictions..."
}

def get_angel_daily_data(symbol):
    row = df[df["symbol"].str.upper() == symbol].iloc[0]
    token = str(row["token"])
    to_date = datetime.now()
    from_date = to_date - timedelta(days=180)
    params = {
        "exchange": "NSE",
        "symboltoken": token,
        "interval": "ONE_DAY",
        "fromdate": from_date.strftime('%Y-%m-%d 09:15'),
        "todate": to_date.strftime('%Y-%m-%d 15:30')
    }
    resp = smart.getCandleData(params)
    candles = resp.get("data", [])
    if not candles:
        raise ValueError("No candle data returned")
    dfc = pd.DataFrame(candles, columns=['date','Open','High','Low','Close','Volume'])
    dfc['date'] = pd.to_datetime(dfc['date'])
    dfc.set_index('date', inplace=True)
    return dfc

def preprocess_image_for_ocr(img_path):
    img = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    denoised = cv2.medianBlur(thresh, 3)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    cv2.imwrite(tmp.name, denoised)
    return tmp.name

def detect_reason_with_fuzzy(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        for reason, sol in REJECTION_SOLUTIONS.items():
            if get_close_matches(reason.lower(), [line.lower()], n=1, cutoff=0.5):
                return reason, sol
    return None, "We couldn’t match the reason. Please contact support."

def extract_rejection_reason(path):
    proc = preprocess_image_for_ocr(path)
    img = Image.open(proc)
    txt = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
    return detect_reason_with_fuzzy(txt)

def is_authorized(sender):
    s = sender.replace("whatsapp:", "").replace("+91", "").strip()
    return is_user_authorized(s)

@app.route("/")
def home():
    return "✅ WhatsApp Stock Bot is live!"

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From", "")
    body = request.form.get("Body", "").strip()
    media = request.form.get("MediaUrl0")
    state = user_states.get(sender, "initial")
    resp = MessagingResponse()

    if not is_authorized(sender):
        resp.message("🛑 Access denied. Contact admin.")
        return str(resp)

    if media:
        if state == "awaiting_rejection_image":
            r = requests.get(media, auth=HTTPBasicAuth(os.getenv("TWILIO_SID"), os.getenv("TWILIO_AUTH_TOKEN")))
            if r.status_code == 200:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                tmp.write(r.content); tmp_path = tmp.name
                reason, sol = extract_rejection_reason(tmp_path)
                resp.message(f"❌ *Reason:* {reason}\n*Solution:* {sol}")
            else:
                resp.message("⚠️ Can't fetch image, try again.")
            user_states[sender] = "initial"
        else:
            resp.message("📸 Image received! Type '2' first for support.")
        return str(resp)

    if body.lower() in ("hi","hello"):
        resp.message("Welcome! 1️⃣ Stock Analysis  2️⃣ App Support")
        user_states[sender] = "menu"
        return str(resp)

    if user_states.get(sender) == "menu":
        if body == "1":
            resp.message("📈 Enter stock symbol or company name.")
            user_states[sender] = "stock_mode"
        elif body == "2":
            resp.message("📷 Upload order rejection screenshot.")
            user_states[sender] = "awaiting_rejection_image"
        else:
            resp.message("❗ Reply with 1 or 2.")
        return str(resp)

    symbol = None
    if body.upper() in symbol_to_name:
        symbol = body.upper()
    else:
        match = get_close_matches(body.lower(), name_to_symbol, n=1, cutoff=0.6)
        if match:
            symbol = name_to_symbol[match[0]]

    if symbol:
        try:
            dfc = get_angel_daily_data(symbol)
            price = dfc["Close"].iat[-1]
            resp.message(f"📈 {symbol}: ₹{price}\nGenerating chart...")
            if not os.path.isdir("static"):
                os.mkdir("static")
            fname = f"{symbol}_{uuid.uuid4().hex[:6]}.png"
            path = os.path.join("static", fname)
            mpf.plot(dfc[-120:], type='candle', style='yahoo', volume=True, savefig=path)
            with open(path, "rb") as imgf:
                data = base64.b64encode(imgf.read()).decode()
            ai = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role":"system","content":"You are a stock expert."},
                    {"role":"user","content":[{"type":"text","text":f"Analyze {symbol} at ₹{price}."},
                                              {"type":"image_url","image_url":{"url":f"data:image/png;base64,{data}"}}]}
                ],
                max_tokens=300
            )
            msg = resp.message(f"📊 {symbol}: ₹{price}\n\n{ai.choices[0].message.content}")
            msg.media(f"https://YOUR_APP_URL/static/{fname}")
        except Exception as e:
            logging.error("%s", e)
            resp.message(f"⚠️ Couldn't fetch data: {e}")
        user_states[sender] = "initial"
    else:
        resp.message("❌ Stock not found. Type 'Hi' to start.")

    return str(resp)

@app.route("/static/<path:fn>")
def serve(fn):
    return send_from_directory("static", fn)

@app.route("/add_user/<mobile>/<email>/<name>")
def add_test(mobile, email, name):
    add_user(mobile, email, name)
    return f"✅ Added {name}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
