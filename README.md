# Meet Master

## Backend folder

Backend code lives in `backend/server.py`, `backend/cloud.py`, and `backend/agent.py`.
Put private configuration in `backend/.env` (ignored by Git). See
`backend/.env.example` for the expected variables. The web server loads this file
automatically; terminal environment variables take precedence. The older root
`.env` is a fallback only. Restart the server after editing configuration.

Start from the project directory with `python server.py`, or run
`python backend/server.py`. Frontend assets stay in `web/`, SQL setup in
`supabase/`, and existing local data in `data/`.

For direct SMTP delivery, set the EMAIL_* variables, DEFAULT_FROM_EMAIL and
SUPABASE_SECRET_KEY in backend/.env (see its example). The backend generates
an Auth OTP through the admin API and sends only the numeric code through your
SMTP server. Supabase does not send this email. Verification still creates a
Supabase user session so database RLS remains enforced. Signup, resend and
recovery use the same custom delivery path. Codes expire locally, allow five
verification attempts and have a resend cooldown. Pending codes are held in
memory and expire on server restart; this deployment supports one server process.
Without EMAIL_HOST, delivery uses the Supabase Auth email configuration instead.

A local meeting-assistant web app inspired by your supplied screenshots. Includes a matching sidebar/dashboard, reusable meeting agents, meeting directory, transcript import, searchable notes, profile settings, and integration status.

Requires Python 3.10+. No third-party runtime packages are needed.

## Start

### Supabase cloud setup

Your supplied project URL and publishable key are saved in the ignored `backend/.env` file.
`DATABASE_BACKEND=supabase` activates cloud storage when `python server.py` starts.
No secret/service-role key is required or stored.

1. In your Supabase project, open **SQL Editor → New query** and run the complete
   [supabase/schema.sql](supabase/schema.sql) file. The publishable key cannot create tables.
2. Open the app, create an account, confirm your email if requested, then sign in.
3. In **Integrations**, choose **Import local workspace** to copy existing SQLite data
   into your empty cloud account. This is atomic and refuses to overwrite cloud data.
4. Create an agent/meeting, reload, and verify it in Supabase Table Editor.

The cloud backend stores agents in `mm_agents`, meetings/transcripts/notes in
`mm_meetings`, and profile data in `mm_profiles`. Each table has owner-based RLS
and authenticated-only grants. Session JWTs and refresh tokens remain in server
memory, with an HttpOnly SameSite cookie in the browser. Passwords are forwarded
to Supabase Auth over HTTPS and are not saved by this app. Server restart requires
sign-in again. The local server remains bound to loopback; public hosting requires
HTTPS cookies, rate limits, durable session storage, and production infrastructure.

Cloud errors never silently fall back to local storage. Existing SQLite data is
preserved. To deliberately use the original local mode, set `DATABASE_BACKEND=sqlite`
in the terminal before starting the server. Explicit environment settings take
precedence over `.env`. Live cloud CRUD remains unverified until the schema is
installed and a user signs in.

### Local server

```powershell
python server.py
```

Open **http://127.0.0.1:8787**. Choose another port with `--port 9000` if needed. The app binds only to loopback and is intended for one local user.

1. Create or edit an agent in **Agents**.
2. Import a consent-approved transcript from the dashboard, or save a meeting link.
3. Open the meeting and extract source lines, or generate AI notes when configured.
4. Search sessions in **History**, and export notes as Markdown.

SQLite stores data in `data/meetmaster.sqlite3`, excluded from Git. File imports support UTF-8 text, up to 120,000 characters. The app starts with one general agent and no invented meetings, balances, or billing transactions.

## Optional live integrations

Set keys privately in the terminal environment before starting the server. Never paste keys into transcripts or commit them.

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | AI summaries, decisions and action items |
| `OPENAI_MODEL` | Responses API model; default `gpt-5.4` |
| `RECALL_API_KEY` | Live bot creation and transcript retrieval |
| `RECALL_REGION` | Your Recall region; default `us-west-2` |

Recall regions accepted: `us-west-2`, `us-east-1`, `eu-central-1`, `ap-northeast-1`. Check region and account capabilities against your provider configuration. Provider usage can incur charges in your own OpenAI and Recall accounts.

**Saving a meeting does not send a bot.** After consent is confirmed, explicitly choose **Send recording bot** inside a saved Google Meet, Teams or Zoom session. Host admission may still be required. **Refresh from provider** retrieves current status and a completed transcript from the recording artifact. There is no background polling. Production needs verified webhooks, durable jobs, and provider reconciliation.

If bot creation has an uncertain outcome, the app prevents blind retries to avoid duplicate recordings. Check the Recall dashboard before further action. The adapter supports provider-returned S3 transcript download URLs; other hosts require manual transcript import.

AI notes use the selected agent's preferences and transcript, with structured JSON output. Review results against the original transcript. Without a key, **Extract source lines** uses simple keyword matching and labels the result as extraction, not an AI summary.

Official references:

- [Recall bot quickstart](https://docs.recall.ai/docs/quickstart)
- [Recall transcript retrieval](https://docs.recall.ai/docs/bot-real-time-transcription)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

## Scope and data

Working locally: agent create/edit/delete, consent timestamps, meeting links, transcript import/editing, history search and filters, extracted notes, note export, profile persistence, and provider configuration status.

Implemented but not live-tested: AI notes, recording bot creation, manual provider refresh, and completed transcript import. Tests use mocked provider responses.

Not implemented: calendar OAuth/sync, scheduled auto-join, recording audio uploads, public hosting, team roles and shared-workspace access, email invitations, payment checkout, and paid-credit ledger. Billing and team screens explain this and keep those actions disabled. Local profile settings do not create a cloud account.

Transcripts and notes stay in the local database. AI generation sends transcript text to OpenAI with `store: false`, which does not imply zero provider retention. Sending a bot submits the meeting link to Recall and captures the call through that provider. Consent confirmation records the user's attestation; it cannot independently verify participant consent.

The HTTP server validates Host headers and uses a mutation token. It is not a hosted multi-tenant security boundary; do not expose it publicly without authentication and production infrastructure.

## Verify

```powershell
python -m unittest discover -s tests -v
python -m py_compile server.py agent.py
node --check web/app.js
```

Thirty-one offline tests cover consent, persistence, URL validation, missing keys, duplicate and uncertain joins, provider transcript parsing, structured AI notes, HTTP mutation protection, signup metadata, OTP, password recovery, OAuth PKCE, and the original CLI agent's controls.

Optional browser test (requires Playwright and installed Edge):

```powershell
node tests/browser.cjs
node tests/auth_browser.cjs
```

Set `PLAYWRIGHT_MODULE` to an existing Playwright module path if it is not installed in the project; set `BROWSER_CHANNEL` for another installed browser. The test uses a separate temporary database on port 8788 and does not call external APIs. Screenshots in `artifacts/` contain test data, not real user meetings.

The auth browser test uses the running app on port 8787, reads its logged-out state,
and mocks auth responses to check desktop/mobile login, signup, OTP and recovery
transitions without sending emails or creating accounts. Live account creation,
email delivery and Google sign-in have not been verified with a real user account.
See [Supabase auth setup](supabase/auth-email-templates.md) for the required
email templates and Google provider settings.

## Original CLI agent

The earlier agent remains available as `python agent.py`, using your complete prompt in `agent-instructions.txt`. It supports approved file writes and command execution, separate from the meeting app. Approved CLI commands run with your account permissions and are not sandboxed.

