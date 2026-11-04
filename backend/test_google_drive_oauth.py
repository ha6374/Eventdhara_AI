import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
CLIENT_FILE = ROOT / "credentials.json"
TOKEN_FILE = ROOT / "token.json"

FOLDER_ID = "19BGF1jSqlilxTnEDuaZldYb2yp25yedJ"

SCOPES = ["https://www.googleapis.com/auth/drive"]

def main():
    if not CLIENT_FILE.exists():
        raise FileNotFoundError(f"OAuth credentials not found: {CLIENT_FILE}")

    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CLIENT_FILE), SCOPES
        )
        creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    drive = build("drive", "v3", credentials=creds)

    folder = drive.files().get(
        fileId=FOLDER_ID,
        fields="id,name,mimeType"
    ).execute()

    print("\nGoogle Drive Connected Successfully!")
    print("Folder Name:", folder["name"])
    print("Folder ID:", folder["id"])
    print("Token saved:", TOKEN_FILE)

if __name__ == "__main__":
    main()
