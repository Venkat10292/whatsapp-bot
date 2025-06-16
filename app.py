from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/", methods=['GET'])
def home():
    return "WhatsApp Bot Running"

@app.route("/incoming", methods=['POST'])
def incoming_message():
    message = request.form.get('Body')
    sender = request.form.get('From')
    
    print(f"Received message from {sender}: {message}")  # Debug

    response = MessagingResponse()
    response.message(f"Hello! You said: {message}")

    return str(response), 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
