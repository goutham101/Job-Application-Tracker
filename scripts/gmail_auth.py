"""One-time interactive Gmail OAuth flow — run this yourself, once, locally:

    GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... python scripts/gmail_auth.py

It opens a browser for you to sign in and grant read-only Gmail access, then
prints a refresh token. Save that as the GMAIL_REFRESH_TOKEN environment
variable wherever the API runs — never commit it to the repo.

GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET come from Google Cloud Console:
APIs & Services > Credentials > Create Credentials > OAuth client ID > Desktop app.
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
    client_config = {
        "installed": {
            "client_id": os.environ["GMAIL_CLIENT_ID"],
            "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    print("\nSave this as the GMAIL_REFRESH_TOKEN environment variable:\n")
    print(creds.refresh_token)


if __name__ == "__main__":
    main()
