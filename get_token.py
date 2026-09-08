from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

creds = Credentials.from_authorized_user_file("token.json", SCOPES)
print("Has refresh token:", bool(creds.refresh_token))