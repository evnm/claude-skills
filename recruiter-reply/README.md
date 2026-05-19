# recruiter-reply

Scans unread emails in a Gmail inbox for recruiter pitches and sends
templated replies.

## One-time setup

### 1. Create a Google Cloud project and enable the Gmail API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top → **New Project**. Name it anything (e.g. `recruiter-reply`).
3. In the left sidebar: **APIs & Services** → **Library**
4. Search for **Gmail API** → click it → **Enable**

### 2. Configure the OAuth consent screen

Before creating credentials you need a consent screen (even for personal use):

1. In the left sidebar: **APIs & Services** → **OAuth consent screen**
2. Click **Get started**
3. Fill in App name (e.g. `recruiter-reply`) and your Gmail address for the support email → **Next**
4. Audience: select **External** → **Next** (Internal is only available for Google Workspace accounts; External apps in Testing mode are private to listed test users, so this is fine for personal use)
5. Add your Gmail address as a contact email → **Next**
6. Agree to the policy checkbox → **Create**
7. Back on the OAuth consent screen, go to the **Audience** tab → **Test users** → **Add users**, enter your Gmail address → **Save**

### 3. Create OAuth2 credentials

1. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
2. Application type: **Desktop app**
3. Name: anything → **Create**
4. Click **Download JSON** on the confirmation dialog (or download it later from the Credentials list)
5. Save the downloaded file as `credentials.json` in this directory:
   ```
   ~/.claude/skills/recruiter-reply/credentials.json
   ```

### 4. Install dependencies and authenticate

```bash
cd ~/.claude/skills/recruiter-reply
make
```

`make` creates the virtualenv, installs packages, and runs the OAuth flow — skipping any step already done. A browser window will open for you to grant Gmail access. A `token.json` file is saved in this directory and subsequent runs are fully headless.

Run `make auth` to force re-authentication if a token ever needs to be refreshed.

## Usage

Invoke with `/recruiter-reply` in Claude Code.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill instructions read by Claude |
| `gmail_helper.py` | Gmail API helper (fetch, send, label, archive) |
| `templates/` | Response templates — edit freely |
| `state.json` | Last-run timestamp — gitignored |
| `credentials.json` | OAuth2 client credentials — gitignored, you provide this |
| `token.json` | OAuth2 access/refresh token — gitignored, auto-generated |

## Customizing templates

Templates live in `templates/`. Add a new `.md` file there and it will automatically appear as an option the next time the skill runs — no changes to `SKILL.md` needed.

Each template must start with a YAML frontmatter block containing a `name` field, which is used as the label in the numbered list:

```markdown
---
name: My new template
---

Hello, {name}. ...
```

Supported placeholders:

- `{name}` — sender's first name
- `{company}` — company name extracted from the email (Claude will ask if it can't determine it)
