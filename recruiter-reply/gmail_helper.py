#!/usr/bin/env python3
"""Gmail helper for recruiter-reply skill."""

import argparse
import base64
import email.mime.text
import html as html_lib
import json
import re
import sys
import tempfile
from email.utils import parsedate_to_datetime
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
SKILL_DIR = Path(__file__).parent
TEMPLATES_DIR = SKILL_DIR / "templates"
NON_REPLY_ACTIONS = {"leave-unread", "archive"}


def get_service():
    creds = None
    token_path = SKILL_DIR / "token.json"
    creds_path = SKILL_DIR / "credentials.json"

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        needs_reauth = True
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                needs_reauth = False
            except RefreshError:
                pass
        if needs_reauth:
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


def html_to_text(raw):
    raw = re.sub(r"(?is)<(style|script|head)\b.*?</\1>", " ", raw)
    return html_lib.unescape(re.sub(r"<[^>]+>", " ", raw))


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
            return html_to_text(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))

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
                    return html_to_text(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))
        # Recurse into nested multipart
        for part in payload["parts"]:
            result = decode_body(part)
            if result:
                return result

    return ""


def cmd_fetch(args):
    service = get_service()

    results = service.users().messages().list(
        userId="me",
        q="label:recruitment is:unread",
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


def cmd_fetch_thread(args):
    service = get_service()

    thread = service.users().threads().get(
        userId="me",
        id=args.thread_id,
        format="full",
    ).execute()

    messages = []
    for msg in thread.get("messages", []):
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
        messages.append({
            "gmail_message_id": msg["id"],
            "from_name": from_name,
            "from_email": from_email,
            "subject": get_header(headers, "subject"),
            "date": get_header(headers, "date"),
            "body_text": body[:2000],
        })

    print(json.dumps(messages, indent=2))


def body_problems(body):
    problems = []
    if not body.strip():
        problems.append("body is empty")
    if re.search(r"\{[A-Za-z_]+\}", body):
        problems.append("unfilled template placeholder (e.g. {name} or {company})")
    if body.lstrip().startswith("---") or re.search(r"^name:\s", body, re.MULTILINE):
        problems.append("template YAML frontmatter was not stripped")
    return problems


def validate_body(body):
    """Refuse to send anything that is not a fully formed reply."""
    problems = body_problems(body)
    if problems:
        print(json.dumps({"status": "refused", "problems": problems}), file=sys.stderr)
        sys.exit(1)


def send_reply(service, thread_id, message_id, to, subject, body):
    # Fetch original message headers for proper threading
    original = service.users().messages().get(
        userId="me",
        id=message_id,
        format="metadata",
        metadataHeaders=["Message-ID", "References"],
    ).execute()

    orig_headers = original["payload"]["headers"]
    orig_message_id = get_header(orig_headers, "message-id")
    orig_references = get_header(orig_headers, "references")

    references = f"{orig_references} {orig_message_id}".strip() if orig_references else orig_message_id

    subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    msg = email.mime.text.MIMEText(body, "plain")
    msg["To"] = to
    msg["Subject"] = subject
    msg["In-Reply-To"] = orig_message_id
    msg["References"] = references

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": thread_id},
    ).execute()


def cmd_send(args):
    service = get_service()

    if args.body_file:
        with open(args.body_file) as f:
            body = f.read()
    else:
        body = args.body

    validate_body(body)
    send_reply(service, args.thread_id, args.message_id, args.to, args.subject, body)
    print(json.dumps({"status": "sent"}))


def message_time(item):
    try:
        return parsedate_to_datetime(item["date"]).timestamp()
    except (TypeError, ValueError):
        return 0


def digest_text(body):
    """Drop link targets and extra whitespace so Claude reads only the pitch."""
    body = re.sub(r"<https?://[^>]+>", "", body)
    body = re.sub(r"https?://\S{60,}", "[link]", body)
    body = re.sub(r"[ \t]+", " ", body)
    return re.sub(r"\n\s*\n+", "\n\n", body).strip()[:8000]


def cmd_prepare(args):
    """Fetch every unread email and save a private run directory for this batch."""
    service = get_service()

    refs = []
    page_token = None
    while True:
        results = service.users().messages().list(
            userId="me",
            q="label:recruitment is:unread",
            maxResults=100,
            pageToken=page_token,
        ).execute()
        refs.extend(results.get("messages", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break

    emails = []
    for ref in refs:
        msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = msg["payload"]["headers"]
        from_header = get_header(headers, "from")
        match = re.match(r'^"?(.+?)"?\s*<(.+?)>$', from_header)
        from_name, from_email = (
            (match.group(1).strip(), match.group(2).strip()) if match else (from_header, from_header)
        )
        emails.append({
            "gmail_message_id": msg["id"],
            "thread_id": msg["threadId"],
            "from_name": from_name,
            "from_email": from_email,
            "subject": get_header(headers, "subject"),
            "date": get_header(headers, "date"),
            "full_body": decode_body(msg["payload"]),
        })
    emails.sort(key=message_time)

    run_dir = Path(tempfile.mkdtemp(prefix="recruiter-reply-"))
    emails_dir = run_dir / "emails"
    emails_dir.mkdir()
    for i, item in enumerate(emails, 1):
        slug = re.sub(r"[^a-z0-9]+", "-", item["from_name"].lower()).strip("-")[:40] or "email"
        path = emails_dir / f"{i:02d}-{slug}.txt"
        path.write_text(
            f"From: {item['from_name']} <{item['from_email']}>\n"
            f"Date: {item['date']}\n"
            f"Subject: {item['subject']}\n\n"
            f"{item.pop('full_body')}\n"
        )
        item["full_email_path"] = str(path)
        item["body_text"] = digest_text(path.read_text().split("\n\n", 1)[1])

    emails_path = run_dir / "emails.json"
    emails_path.write_text(json.dumps(emails, indent=2))
    print(json.dumps({"run_dir": str(run_dir), "emails_path": str(emails_path), "count": len(emails)}))


def render_template(action, name, company):
    text = (TEMPLATES_DIR / f"{action}.md").read_text()
    match = re.match(r"\A---\s*\n.*?\n---\s*\n", text, re.DOTALL)
    body = text[match.end():].lstrip("\n") if match else text
    return body.replace("{name}", name or "{name}").replace("{company}", company or "{company}")


def build_plan(run_dir):
    """Validate the whole plan up front. Returns (steps, problems)."""
    emails = {e["gmail_message_id"]: e for e in json.loads((run_dir / "emails.json").read_text())}
    decisions = json.loads((run_dir / "plan.json").read_text())["decisions"]
    by_id = {}
    problems = []

    for d in decisions:
        mid = d.get("message_id")
        if mid not in emails:
            problems.append(f"{mid}: not in this run")
        elif mid in by_id:
            problems.append(f"{mid}: listed twice")
        else:
            by_id[mid] = d
    for mid in emails.keys() - by_id.keys():
        problems.append(f"{mid}: no decision")

    steps = []
    for mid, d in by_id.items():
        action = d.get("action", "")
        e = emails[mid]
        step = {"message_id": mid, "action": action, "to": e["from_email"],
                "subject": e["subject"], "thread_id": e["thread_id"], "body": None}
        primary = d.get("duplicate_of")
        if primary:
            if action != "archive":
                problems.append(f"{mid}: a duplicate must use action archive")
            if primary not in by_id or by_id[primary].get("duplicate_of"):
                problems.append(f"{mid}: duplicate_of must name a primary email")
            elif by_id[primary].get("action") == "leave-unread":
                step["action"] = "leave-unread"
        elif action not in NON_REPLY_ACTIONS:
            if not (TEMPLATES_DIR / f"{action}.md").is_file():
                problems.append(f"{mid}: unknown action {action!r}")
            else:
                step["body"] = render_template(action, d.get("name"), d.get("company"))
                problems.extend(f"{mid}: {p}" for p in body_problems(step["body"]))
        steps.append(step)
    return steps, problems


def cmd_apply(args):
    """Carry out a confirmed plan. Safe to rerun: finished steps are not repeated."""
    run_dir = Path(args.run_dir)
    steps, problems = build_plan(run_dir)
    if problems:
        print(json.dumps({"status": "refused", "problems": problems}, indent=2), file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(json.dumps({"status": "dry_run", "steps": [
            {k: s[k] for k in ("message_id", "action", "to", "subject", "body")} for s in steps
        ]}, indent=2))
        return

    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    def save():
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(state_path)

    service = get_service()
    counts = {"sent": 0, "archived": 0, "left_unread": 0}
    unconfirmed = []

    for step in steps:
        mid = step["message_id"]
        if step["action"] == "leave-unread":
            counts["left_unread"] += 1
            continue
        record = state.setdefault(mid, {})
        try:
            if step["body"] is not None and not record.get("sent"):
                # A failed send may still have gone out, so never retry it silently.
                if record.get("send_started") and not args.retry_unconfirmed:
                    unconfirmed.append({"message_id": mid, "to": step["to"], "subject": step["subject"]})
                    continue
                record["send_started"] = True
                save()
                send_reply(service, step["thread_id"], mid, step["to"], step["subject"], step["body"])
                record["sent"] = True
                save()
                counts["sent"] += 1
            if not record.get("archived"):
                service.users().messages().modify(
                    userId="me",
                    id=mid,
                    body={"removeLabelIds": ["INBOX", "UNREAD"]},
                ).execute()
                record["archived"] = True
                save()
                counts["archived"] += 1
        except Exception as exc:
            print(json.dumps({"status": "failed", "message_id": mid, "to": step["to"],
                              "error": str(exc), "completed": counts}), file=sys.stderr)
            sys.exit(1)

    print(json.dumps({"status": "unconfirmed" if unconfirmed else "done",
                      "completed": counts, "unconfirmed": unconfirmed}))
    if unconfirmed:
        sys.exit(1)


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

    sub.add_parser("fetch")
    sub.add_parser("prepare")

    p = sub.add_parser("apply")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--retry-unconfirmed", action="store_true",
                   help="Resend replies whose earlier send attempt had no confirmed result")

    p = sub.add_parser("fetch-thread")
    p.add_argument("--thread-id", required=True)

    p = sub.add_parser("send")
    p.add_argument("--thread-id", required=True)
    p.add_argument("--message-id", required=True, help="Gmail message ID of the message being replied to")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    body_group = p.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body")
    body_group.add_argument("--body-file")

    p = sub.add_parser("archive")
    p.add_argument("--message-id", required=True)

    p = sub.add_parser("mark-read")
    p.add_argument("--message-id", required=True)

    sub.add_parser("auth")

    args = parser.parse_args()

    commands = {
        "auth": cmd_auth,
        "fetch": cmd_fetch,
        "prepare": cmd_prepare,
        "apply": cmd_apply,
        "fetch-thread": cmd_fetch_thread,
        "send": cmd_send,
        "archive": cmd_archive,
        "mark-read": cmd_mark_read,
    }

    if args.command not in commands:
        parser.print_help()
        sys.exit(1)

    commands[args.command](args)


if __name__ == "__main__":
    main()
