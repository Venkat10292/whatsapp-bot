import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Define the scope for accessing Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Load credentials
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)

# Authorize the client
client = gspread.authorize(creds)

# Replace with the name of your actual Google Sheet
sheet_name = "Authorized Users"  # <-- change this if needed

def get_allowed_users():
    try:
        sheet = client.open(sheet_name).sheet1
        users = sheet.col_values(1)  # Assume phone numbers are in column A
        return users
    except Exception as e:
        print(f"Error fetching users from sheet: {e}")
        return []
