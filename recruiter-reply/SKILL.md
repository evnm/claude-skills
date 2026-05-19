# recruiter-reply

Scan unread emails since the last run for recruiter pitches, let the user choose a response for each, send replies, and update state.

## Steps

### 1. Load state

Read `~/.claude/skills/recruiter-reply/state.json`. Use the `last_run` value as the cutoff timestamp. If the file is missing or `last_run` is null, default to 7 days before today in ISO 8601 UTC format (e.g. `2026-05-12T00:00:00Z`).

### 2. Fetch unread emails

```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py fetch --since "<last_run>"
```

This prints a JSON array of email objects with fields: `gmail_message_id`, `rfc_message_id`, `thread_id`, `from_name`, `from_email`, `subject`, `body_text`, `date`.

### 3. Classify recruiter emails

For each email, decide if it is a recruiter pitch. Signals:
- Sender identifies as a recruiter, sourcer, talent acquisition rep, or engineering/technical leader at a company
- Describes a software engineering role or opportunity
- Pitches the company or asks to schedule a call, chat, or interview

Exclude everything else: newsletters, GitHub notifications, billing, personal mail, etc.

### 4. Load templates

Read all `.md` files in `~/.claude/skills/recruiter-reply/templates/`. For each file, parse the YAML frontmatter to extract the `name` field. Sort the files alphabetically by filename. Build a numbered list with these templates followed by a fixed final option: **Skip** (no reply; leave email unread).

### 5. Interactive loop

If no recruiter emails are found, tell the user and skip to step 7 to still update state.

For each recruiter email in chronological order:

a. Print the email as plain text in this format (no markdown blockquotes):
```
From: <from_name> <<from_email>>
Subject: <subject>

│ <body line 1>
│ <body line 2>
│ ...
```

b. Print the numbered option list built in step 4, followed by the prompt:
```
1. <template name>
2. <template name>
...
N. Skip

Enter a number:
```

c. Wait for the user to type a number in the chat and proceed accordingly.

### 6. Process each choice

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
f. Add label, archive, mark read:
```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py label --message-id "<gmail_message_id>" --label "recruitment"
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py archive --message-id "<gmail_message_id>"
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py mark-read --message-id "<gmail_message_id>"
```

**For Skip:**

Add label and archive, but do NOT mark as read (the user wants to see the unread badge under the "recruitment" label):
```bash
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py label --message-id "<gmail_message_id>" --label "recruitment"
~/.claude/skills/recruiter-reply/.venv/bin/python ~/.claude/skills/recruiter-reply/gmail_helper.py archive --message-id "<gmail_message_id>"
```

### 7. Update state

Write the current UTC timestamp to `~/.claude/skills/recruiter-reply/state.json`:
```json
{"last_run": "<current ISO 8601 UTC timestamp>"}
```
