# FitBuddy — AI Fitness Plan Generator

FitBuddy is a complete FastAPI application based on the supplied project brief. It accepts a user profile, creates a practical seven-day workout plan and a nutrition/recovery tip, stores both in SQLite, and lets the user revise the plan with feedback. It includes a browser UI, JSON API, OpenAPI docs, and an admin/coach view.

## What is included

```text
fitbuddy/
├── app/
│   ├── config.py              # environment configuration
│   ├── database.py            # SQLAlchemy engine/session setup
│   ├── models.py              # User and Plan tables
│   ├── schemas.py             # request/response validation
│   ├── routes.py              # HTML and JSON endpoints
│   ├── main.py                # FastAPI application entry point
│   └── services/
│       ├── gemini.py          # Google GenAI SDK adapter
│       └── plan_generator.py  # prompts plus offline-safe fallbacks
├── templates/                 # Jinja2 pages
├── static/                    # CSS, JavaScript, image placeholder
├── tests/                     # endpoint and validation tests
├── requirements.txt
├── .env.example
├── Dockerfile
└── README.md
```

## Install and run in VS Code

1. Open this `fitbuddy` folder in VS Code.
2. Create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   On macOS/Linux use `source .venv/bin/activate`.

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Optional live Gemini setup: copy `.env.example` to `.env` and add a Google AI Studio key as `GEMINI_API_KEY`. The app still runs without a key using deterministic offline starter plans, which makes UI development and tests possible without network access.

5. Start the server:

   ```bash
   uvicorn app.main:app --reload
   ```

6. Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Main endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Browser form for creating a plan |
| POST | `/generate-workout` | Browser form submission |
| POST | `/submit-feedback` | Browser feedback update |
| GET | `/view-all-users` | Admin/coach HTML dashboard |
| GET | `/health` | Service health check |
| POST | `/api/plans/generate` | Generate a plan from JSON |
| POST | `/api/plans/{user_id}/feedback` | Update a saved plan |
| POST | `/api/nutrition-tip` | Generate one nutrition/recovery tip |
| GET | `/api/users` | List saved users and plans |
| GET/DELETE | `/api/users/{user_id}` | Inspect or delete a user |

JSON generation example:

```json
{
  "name": "Alex Morgan",
  "user_id": "alex-001",
  "age": 28,
  "weight_kg": 70,
  "goal": "muscle gain",
  "intensity": "medium"
}
```

Supported goals are `weight loss`, `muscle gain`, `general wellness`, `flexibility`, and `endurance`. Supported intensities are `low`, `medium`, and `high`. User IDs may contain letters, numbers, underscores, and hyphens.

## Test and validate

Run the automated checks with:

```bash
pytest
```

The tests cover health/homepage rendering, HTML form generation, JSON generation, validation failures, feedback updates, and admin listing. The test suite clears the Gemini key and verifies the offline fallback, so it does not consume API quota.

## Gemini integration notes

The app uses the current `google-genai` Python SDK. Workout generation and feedback revision use `GEMINI_WORKOUT_MODEL`; the short nutrition request uses `GEMINI_TIP_MODEL`. Both are configurable in `.env` so a model available to your account can be selected without changing application code. If a key is absent or a provider request fails, the service returns a safe local starter response and marks the plan source as `fallback`.

The generated content is general wellness guidance. It is not medical advice, does not diagnose conditions, and should be reviewed by a qualified professional for users with injuries, symptoms, or health conditions.

## Optional admin protection

Set `ADMIN_TOKEN` in `.env` to protect `/view-all-users` and `/api/users`. For the JSON endpoints send `X-Admin-Token: your-token`. For the browser dashboard use `/view-all-users?token=your-token`. Leave it blank for local development.

## Docker

```bash
docker build -t fitbuddy .
docker run --rm -p 8000:8000 --env-file .env fitbuddy
```

The default SQLite file lives inside the container unless a volume is mounted. For a persistent deployment, use a managed database by setting `DATABASE_URL` to a SQLAlchemy-compatible database URL and review the deployment security settings first.

