# recruiter-reply

Scan unread emails labeled "recruitment" for recruiter pitches, let the user choose a response for each, send replies, and update labels/read status.

## Steps

### 1. Fetch labeled emails

```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py fetch
```

This prints a JSON array of unread emails with the "recruitment" label, with fields: `gmail_message_id`, `rfc_message_id`, `thread_id`, `from_name`, `from_email`, `subject`, `body_text`, `date`. The `thread_id` can be passed to `fetch-thread` to retrieve all messages in a conversation thread.

If the array is empty, tell the user there's nothing to process and stop.

### 2. Group by sender/company and auto-skip duplicates

Sort all fetched emails chronologically (oldest first). Then walk through them and assign each one a **dedup key** identifying the recruiter/company behind it:

- Prefer the company name — pull it from the subject line, the body, or the sender's email domain (e.g. `jacobduligall@ivo.ai` → Ivo, a LinkedIn InMail pitching "Suno" → Suno).
- If no company can be confidently identified, fall back to the sender's `from_name` (the human recruiter), since the same person may email from more than one address (e.g. a direct company address and `inmail-hit-reply@linkedin.com`).
- If neither is identifiable, fall back to `from_email`.

For each email, check whether its dedup key has already been seen earlier in this same run (including plain thread replies — `Re:` subject or quoted prior messages — which always share a key with the message they reply to). 

- The **first (earliest)** email for a given dedup key is a "primary" email — it goes through the normal interactive loop in step 4.
- Every **later** email sharing that key is a duplicate or "bump" (a follow-up nudge, a repeat pitch for a different role at the same company, or the same recruiter reaching out from a different address). Auto-skip it without prompting: archive and mark read using the same commands as the Skip action in step 5, and print one line per auto-skipped email, e.g.:
```
Auto-skipped (duplicate of "<subject of primary email>"): <from_name> <<from_email>> — <subject>
```

Only primary emails proceed to step 3.

### 3. Load templates

Read all `.md` files in `~/.claude/skills/recruiter-reply/templates/`. For each file, parse the YAML frontmatter to extract the `name` field. Sort the files alphabetically by filename. Build a numbered list with these templates followed by a fixed final option: **Skip** (no reply; leave email unread).

### 4. Interactive loop

For each primary email in chronological order:

a. Check whether this email is a follow-up in a longer thread. A follow-up is indicated by a `Re:` prefix in the subject, or by the email body containing quoted prior messages. If it is a follow-up, fetch the full thread:
```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py fetch-thread --thread-id "<thread_id>"
```
This returns a JSON array of all messages in the thread. Read the earlier messages and produce a 2–4 sentence **Thread summary** covering: the role/company being pitched, any compensation or remote/hybrid/in-office details mentioned, and how many times the recruiter has followed up.

b. Print the email as plain text in this format (no markdown blockquotes):
```
From: <from_name> <<from_email>>
Subject: <subject>
```
If a thread summary was produced in step (a), print it next:
```
Thread summary: <summary>
```
Then print the latest message body:
```
│ <body line 1>
│ <body line 2>
│ ...
```

c. Print the numbered option list built in step 3, followed by the prompt:
```
1. <template name>
2. <template name>
...
N. Skip

Enter a number:
```

d. Wait for the user to type a number in the chat and proceed accordingly.

### 5. Process each choice

**For any template option (not Skip):**

a. Read the selected template file. Strip the YAML frontmatter block (everything between the opening and closing `---` lines) before using the body.
b. Replace `{name}` with the sender's first name.
c. If the template body contains `{company}`: replace it with the company name from the email. If you cannot determine the company name, ask the user before sending.
d. Write the filled body to `/tmp/recruiter_reply_body.txt`
e. Send the reply:
```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py send \
  --thread-id "<thread_id>" \
  --message-id "<gmail_message_id>" \
  --to "<from_email>" \
  --subject "<subject>" \
  --body-file /tmp/recruiter_reply_body.txt
```
f. Archive and mark read:
```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py archive --message-id "<gmail_message_id>"
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py mark-read --message-id "<gmail_message_id>"
```

**For Skip:**

Archive and mark read (the email keeps its "recruitment" label, so it stays out of future runs):
```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py archive --message-id "<gmail_message_id>"
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py mark-read --message-id "<gmail_message_id>"
```
