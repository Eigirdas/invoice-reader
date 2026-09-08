from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from sheets import get_credentials, FOLDER_ID

def cleanup_old_sheets():
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    query = f"'{FOLDER_ID}' in parents and createdTime < '{cutoff_str}' and trashed = false"
    response = drive_service.files().list(q=query, fields="files(id, name, createdTime)").execute()
    old_files = response.get("files", [])

    for file in old_files:
        print(f"Deleting {file['name']} (created {file['createdTime']})")
        drive_service.files().delete(fileId=file['id']).execute()

    print(f"Cleanup done. Deleted {len(old_files)} file(s).")

if __name__ == "__main__":
    cleanup_old_sheets()