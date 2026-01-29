import google.auth
from googleapiclient.discovery import build
from google.oauth2 import service_account

# The path to your downloaded service account JSON file
SERVICE_ACCOUNT_FILE = 'credentials.json'
# Define the scopes required (read access to spreadsheets)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def get_sheet_data(sheet_id, sheet_range):
    # Authenticate and create the service object
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('sheets', 'v4', credentials=credentials)

    # Call the Sheets API to get data
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=sheet_range
    ).execute()
    return result.get('values', [])

# get_sheet_data('17dta0BdPbPpZTLLdcTHr-MvaoSCl3sqkg1AgzCMP7Ew', 'Sheet1!A1:B2')
