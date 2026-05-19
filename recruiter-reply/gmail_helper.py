#!/usr/bin/env python3
"""Gmail helper for recruiter-reply skill."""

import argparse
import base64
import email.mime.text
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SKILL_DIR = Path(__file__).parent


def get_service():
    creds = None
    token_path = SKILL_DIR / "token.json"
    creds_path = SKILL_DIR / "credentials.json"

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                print(f"Error: credentials.json not found at {creds_path}", file=sys.stderr)
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def decode_body(payload):
    """Extract plain text from a message payload, handling multipart MIME."""
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", html)

    if "parts" in payload:
        # Prefer text/plain parts
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        # Fall back to text/html parts
        for part in payload["parts"]:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    return re.sub(r"<[^>]+>", " ", html)
        # Recurse into nested multipart
        for part in payload["parts"]:
            result = decode_body(part)
            if result:
                return result

    return ""


def cmd_fetch(args):
    service = get_service()

    since_dt = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
    since_unix = int(since_dt.timestamp())

    results = service.users().messages().list(
        userId="me",
        q=f"is:unread after:{since_unix}",
        maxResults=100,
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me",
            id=msg_ref["id"],
            format="full",
        ).execute()

        headers = msg["payload"]["headers"]
        from_header = get_header(headers, "from")

        match = re.match(r'^"?(.+?)"?\s*<(.+?)>$', from_header)
        if match:
            from_name = match.group(1).strip()
            from_email = match.group(2).strip()
        else:
            from_name = from_header
            from_email = from_header

        body = decode_body(msg["payload"])

        emails.append({
            "gmail_message_id": msg["id"],
            "rfc_message_id": get_header(headers, "message-id"),
            "thread_id": msg["threadId"],
            "from_name": from_name,
            "from_email": from_email,
            "subject": get_header(headers, "subject"),
            "body_text": body[:3000],
            "date": get_header(headers, "date"),
        })

    print(json.dumps(emails, indent=2))


def cmd_send(args):
    service = get_service()

    if args.body_file:
        with open(args.body_file) as f:
            body = f.read()
    else:
        body = args.body

    # Fetch original message headers for proper threading
    original = service.users().messages().get(
        userId="me",
        id=args.message_id,
        format="metadata",
        metadataHeaders=["Message-ID", "References"],
    ).execute()

    orig_headers = original["payload"]["headers"]
    orig_message_id = get_header(orig_headers, "message-id")
    orig_references = get_header(orig_headers, "references")

    references = f"{orig_references} {orig_message_id}".strip() if orig_references else orig_message_id

    subject = args.subject if args.subject.lower().startswith("re:") else f"Re: {args.subject}"

    msg = email.mime.text.MIMEText(body, "plain")
    msg["To"] = args.to
    msg["Subject"] = subject
    msg["In-Reply-To"] = orig_message_id
    msg["References"] = references

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": args.thread_id},
    ).execute()

    print(json.dumps({"status": "sent"}))


def ensure_label(service, label_name):
    """Return the ID of an existing label, creating it if necessary."""
    labels = service.users().labels().list(userId="me").execute()
    for label in labels.get("labels", []):
        if label["name"].lower() == label_name.lower():
            return label["id"]

    created = service.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    return created["id"]


def cmd_label(args):
    service = get_service()
    label_id = ensure_label(service, args.label)
    service.users().messages().modify(
        userId="me",
        id=args.message_id,
        body={"addLabelIds": [label_id]},
    ).execute()
    print(json.dumps({"status": "labeled", "label": args.label}))


def cmd_archive(args):
    service = get_service()
    service.users().messages().modify(
        userId="me",
        id=args.message_id,
        body={"removeLabelIds": ["INBOX"]},
    ).execute()
    print(json.dumps({"status": "archived"}))


def cmd_mark_read(args):
    service = get_service()
    service.users().messages().modify(
        userId="me",
        id=args.message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()
    print(json.dumps({"status": "marked_read"}))


def cmd_auth(args):
    """Complete the OAuth flow and verify credentials with a minimal API call."""
    service = get_service()
    profile = service.users().getProfile(userId="me").execute()
    print(f"Authenticated as {profile['emailAddress']}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("fetch")
    p.add_argument("--since", required=True, help="ISO 8601 UTC timestamp")

    p = sub.add_parser("send")
    p.add_argument("--thread-id", required=True)
    p.add_argument("--message-id", required=True, help="Gmail message ID of the message being replied to")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    body_group = p.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body")
    body_group.add_argument("--body-file")

    p = sub.add_parser("label")
    p.add_argument("--message-id", required=True)
    p.add_argument("--label", required=True)

    p = sub.add_parser("archive")
    p.add_argument("--message-id", required=True)

    p = sub.add_parser("mark-read")
    p.add_argument("--message-id", required=True)

    sub.add_parser("auth")

    args = parser.parse_args()

    commands = {
        "auth": cmd_auth,
        "fetch": cmd_fetch,
        "send": cmd_send,
        "label": cmd_label,
        "archive": cmd_archive,
        "mark-read": cmd_mark_read,
    }

    if args.command not in commands:
        parser.print_help()
        sys.exit(1)

    commands[args.command](args)


if __name__ == "__main__":
    main()
