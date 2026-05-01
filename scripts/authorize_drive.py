"""
One-time OAuth authorization flow.

Run this ONCE to grant the bookkeeping engine read-only access to your
Google Drive. After running, a token.json file is saved alongside the
client credentials. The engine reads token.json on every run; you don't
need to authorize again unless the token is revoked or expires (typically
6+ months for properly used Desktop apps).
"""

from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Read-only scopes - engine can fetch files but cannot modify or delete
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

CREDS_DIR = Path(__file__).parent.parent / "credentials"
CLIENT_FILE = CREDS_DIR / "google_oauth_client.json"
TOKEN_FILE = CREDS_DIR / "token.json"

if not CLIENT_FILE.exists():
    raise SystemExit(f"ERROR: Missing client credentials at {CLIENT_FILE}")

print("Starting OAuth flow...")
print("Your browser will open. Sign in with joshkravets@gmail.com and grant access.")
print()

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
creds = flow.run_local_server(port=0)

with TOKEN_FILE.open("w") as f:
    f.write(creds.to_json())

print()
print(f"SUCCESS - token saved to {TOKEN_FILE}")
print("The engine can now read Drive files via OAuth.")
print("You won't need to run this again unless token is revoked.")
