import os
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def build_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


class RealGmailClient:
    def __init__(self, service):
        self.service = service

    def list_messages(self, query: str) -> list[dict]:
        results = []
        req = self.service.users().messages().list(userId="me", q=query)
        while req is not None:
            resp = req.execute()
            results.extend(resp.get("messages", []))
            req = self.service.users().messages().list_next(req, resp)
        return results

    def get_message(self, message_id: str) -> dict:
        msg = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "Subject"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        return {
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "received_at": datetime.fromtimestamp(
                int(msg["internalDate"]) / 1000, tz=timezone.utc
            ),
        }
