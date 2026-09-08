from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
FOLDER_ID = "1TKHBLf0XQMJF4LdhMw0n72Jvn0VkaDBL"


def get_credentials():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def create_session_sheet(sorted_json):
    creds = get_credentials()
    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    title = f"Invoices - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    spreadsheet = sheets_service.spreadsheets().create(
        body={"properties": {"title": title}}
    ).execute()
    spreadsheet_id = spreadsheet["spreadsheetId"]

    values = [
        [row['date'], row['seller'], row['price_excl_vat'], row['vat'], row['price_incl_vat']]
        for row in sorted_json
    ]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    drive_service.files().update(
        fileId=spreadsheet_id,
        addParents=FOLDER_ID,
        removeParents="root",
        fields="id, parents",
    ).execute()

    drive_service.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
