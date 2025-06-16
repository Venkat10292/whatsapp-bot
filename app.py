from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/incoming", methods=['POST'])
def incoming_message():
    message = request.form.get('Body').strip().lower()
    response = MessagingResponse()
    
    if message == '/help':
        response.message("Available commands:\n/help\n/about\n/weather Hyderabad")
    elif message == '/about':
        response.message("This is an AI-powered WhatsApp assistant built by Satish.G!")
    elif message.startswith('/weather'):
        city = message.split('/weather ')[-1] if ' ' in message else 'Hyderabad'
        response.message(f"Fetching weather for {city}... (feature coming soon)")
    else:
        response.message("Sorry, I didn’t understand that. Type /help for commands.")
    
    return str(response)
