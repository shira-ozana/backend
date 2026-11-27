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
| POST | `/api/users` | Register a user, returns a unique `user_id` |
| POST | `/api/repositories` | Save a repo + GitHub credentials for a registered username |
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
