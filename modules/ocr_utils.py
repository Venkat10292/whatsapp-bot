# ocr_utils.py

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
