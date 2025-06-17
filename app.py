app = Flask(__name__)

# Track user session state
user_state = {}

@app.route("/incoming", methods=["POST"])
def whatsapp_bot():
    sender = request.form.get("From")
    user_msg = request.form.get("Body", "").strip().lower()
    response = MessagingResponse()
    reply = response.message()

    state = user_state.get(sender, "initial")

    # Step 1: Welcome message on "hi"
    if user_msg in ["hi", "hello"]:
        reply.body(
            "👋 G. Satish చాట్‌బాట్‌కి స్వాగతం!\n"
            "ఈ రోజు నేను మీకు ఎలా సహాయపడగలను?\n\n"
            "1️⃣ స్టాక్ విశ్లేషణ 📈\n"
            "2️⃣ కొనుగోలు/అమ్మకం సమస్యలు ⚙️\n\n"
            "దయచేసి 1 లేదా 2 అని రిప్లై ఇవ్వండి."
        )
        user_state[sender] = "menu"
        return str(response)

    # Step 2: Handle menu choices
    if state == "menu":
        if user_msg == "1":
            reply.body("✅ You've selected *Stock Analysis*.")
        elif user_msg == "2":
            reply.body("🔧 This feature is currently under maintenance.")
        else:
            reply.body("❗ దయచేసి సరైన ఎంపికను ఎంచుకోండి: 1 లేదా 2.")
        user_state[sender] = "initial"
        return str(response)

    # Fallback
    reply.body("⚠️ దయచేసి 'Hi' అని టైప్ చేయండి.")
    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
