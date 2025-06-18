# stock_analysis.py

import yfinance as yf
import mplfinance as mpf
import base64
import os
import openai
from io import BytesIO
from PIL import Image
import logging

openai.api_key = os.getenv("OPENAI_API_KEY")

def fetch_stock_chart(symbol):
    try:
        stock = yf.Ticker(symbol + ".NS")
        price = stock.info.get("regularMarketPrice", None)
        if not price:
            return None, None, "Price data not available."

        hist = stock.history(period="6mo")
        chart_path = f"static/{symbol}_chart.png"

        if not os.path.exists("static"):
            os.makedirs("static")

        mpf.plot(hist[-120:], type='candle', style='yahoo', title=symbol, volume=True, savefig=chart_path)

        with open(chart_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode("utf-8")

        return price, chart_path, encoded_image
    except Exception as e:
        logging.error(f"Stock chart generation failed: {e}")
        return None, None, str(e)


def get_ai_stock_analysis(company_name, symbol, price, encoded_chart_image):
    try:
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
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_chart_image}"}}
                ]
            }
        ]

        chat_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=300
        )

        return chat_response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI analysis failed: {e}")
        return "⚠️ AI analysis could not be completed due to an internal error."
