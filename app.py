from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/incoming", methods=['POST'])
def incoming_message():
    message = request.form.get('Body')
    sender = request.form.get('From')

    print(f"Received message from {sender}: {message}")  # For debugging logs

    response = MessagingResponse()
    response.message(f"Hello! You said: {message}")

    return str(response), 200, {'Content-Type': 'application/xml'}
