from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/bot", methods=['POST'])
def bot():
    incoming_msg = request.form.get('Body')
    print("User sent:", incoming_msg)

    # Create reply
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(f"మీ మెసేజ్ వచ్చింది: {incoming_msg} ✅")
    
    return str(resp)

if __name__ == "__main__":
    app.run(port=5000)
