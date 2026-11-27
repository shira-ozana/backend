# SDLC Platform - Backend

FastAPI backend that receives a user, GitHub user, GitHub password/token and repo URL,
and stores them in Supabase. The GitHub password is encrypted (Fernet) before saving
and is never returned by the API.

## Setup (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

1. Open `.env` and paste the **service_role** key from
   Supabase Dashboard > Project Settings > API Keys into `SUPABASE_SERVICE_ROLE_KEY`.
2. `ENCRYPTION_KEY` is already generated. Don't change it after data is saved
   (old passwords won't decrypt). To make a new one: `python generate_key.py`.
3. The table is defined in `sql/schema.sql` (run it in the Supabase SQL Editor if it doesn't exist).

## Run

```powershell
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/users` | Register a user, returns a unique `user_id` and sets the `shipai_session` cookie |
| GET | `/api/auth/me` | The signed-in user (session cookie), or 401 |
| POST | `/api/auth/sign-in/request` | Email a one-time code to the account's address (`{identifier}`: username or email) |
| POST | `/api/auth/sign-in/verify` | Exchange `{challenge, code}` for the session cookie |
| POST | `/api/auth/sign-out` | Clear the session cookie |
| POST | `/api/repositories` | Requires a session; `username` must match it. Saves a repo + GitHub credentials |
| POST | `/api/features` | Create a feature for a registered repo, returns a unique `feature_id` |
| GET | `/api/features?username=...&repo_url=...` | All feature IDs of a user in a repo |
| POST | `/api/tasks` | Add a task to a feature, returns a unique `task_id` |
| GET | `/api/tasks?username=...&repo_url=...&feature_id=...` | All tasks of a feature, sorted by creation time |

Example body for POST:

```json
{
  "username": "shira",
  "github_user": "shira-dev",
  "github_password": "ghp_xxx",
  "repo_url": "https://github.com/org/repo"
}
```

> GitHub no longer accepts account passwords for git/API operations -
> send a Personal Access Token in `github_password`.

## Sign-in codes by email (Gmail SMTP)

`POST /api/auth/sign-in/request` emails a one-time code to the address stored on the matching
account. The response is always the same `202` (`challenge`, `expires_in`, `delivery`) for
existing and unknown accounts, and never contains the code. Unknown accounts get no email.
`POST /api/auth/sign-in/verify` exchanges `{challenge, code}` for the `shipai_session` cookie.

If delivery is not configured the request endpoint answers `503` (nothing is silently skipped).

### Configuration

Create a Google App Password for the sender account (needs 2-Step Verification:
Google Account > Security > App passwords). Put the real values in the backend's local `.env`
(git-ignored) or in the deployment's secret store - never in tracked files:

```env
AUTH_EMAIL_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USER=<full Gmail sender address>
SMTP_PASSWORD=<Google App Password>
SMTP_FROM=<same Gmail sender address>
```

Notes:

- The connection uses STARTTLS with certificate and hostname verification, completed before
  SMTP authentication. The connection timeout is 15 seconds.
- Spaces in the App Password (Google shows it as `abcd efgh ijkl mnop`) are ignored.
- With `SMTP_USER` set, `SMTP_PASSWORD` is required and `SMTP_STARTTLS` must be `true`;
  otherwise the endpoint answers `503` rather than send a login without TLS.
- For local development keep `AUTH_EMAIL_MODE=console`: the code is written to the uvicorn
  log (`DEV sign-in code for ...`) and never returned by the API.
- Delivery failures are logged by the server as
  `Sign-in code email was not delivered: category=<category> ...` with one of `authentication`,
  `tls`, `timeout`, `connection`, `recipient_rejected`, `sender_rejected`, `smtp`. Passwords,
  codes, recipient addresses and message bodies are not logged. The HTTP response stays `202`.

### Restart

Settings are read once at startup, so restart after editing `.env` or the secrets:

```powershell
# stop uvicorn (Ctrl+C), then
uvicorn app.main:app --reload
```

(`--reload` only watches Python files; it does not pick up `.env` changes.)

### Manual smoke test

Use an account whose stored email is a Gmail (or any) inbox you can read. Create one with
`POST /api/users` if needed. Use a cookie jar so the session persists:

```bash
# 1. Request a code (replace with the test account's username or email)
curl -i -X POST http://127.0.0.1:8000/api/auth/sign-in/request \
  -H "Content-Type: application/json" -d '{"identifier": "<test username>"}'
# -> 202 with {"challenge": "...", "expires_in": 600, "delivery": "email"}; no code in the body

# 2. Confirm the "<app name> sign-in code" email arrives in the account's inbox
#    (check Spam if it does not), and read the 6-digit code.

# 3. Enter the code (challenge from step 1)
curl -i -c jar.txt -X POST http://127.0.0.1:8000/api/auth/sign-in/verify \
  -H "Content-Type: application/json" \
  -d '{"challenge": "<challenge from step 1>", "code": "<6-digit code>"}'
# -> 200 and a Set-Cookie: shipai_session=...

# 4. Confirm the session
curl -b jar.txt http://127.0.0.1:8000/api/auth/me
# -> 200 with the signed-in user (user_id, username, email, ...)
```

If no email arrives, look in the uvicorn log for `category=...`: `authentication` means the
sender address / App Password are wrong, `tls` a certificate or STARTTLS problem,
`timeout`/`connection` a blocked network (outbound port 587), `recipient_rejected` that
the server refused the account's address.

### Tests

The SMTP path is tested with a mocked transport (no network, no credentials):

```powershell
pip install -r requirements-dev.txt
python -m pytest
```
