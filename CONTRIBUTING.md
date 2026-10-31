# Contributing to Stash

Thanks for your interest in improving Stash. Bug reports, fixes, docs and new features are all welcome. This guide
covers how to get set up, what we expect in a pull request, and how to report security issues.

## Ways to contribute

- **Report a bug.** Open an issue with steps to reproduce, what you expected, what happened, and your browser/OS.
  Screenshots or the failing request (with personal data removed) help a lot.
- **Suggest a feature.** Open an issue describing the problem it solves before writing code, so we can agree on the
  approach first. Small, focused proposals land faster.
- **Fix something.** Issues labelled `good first issue` or `help wanted` are a good place to start. Comment on the
  issue so others know you are on it.
- **Improve the docs.** Typos, unclear steps and missing explanations in the README or `deploy/README.md` are fair game.

## Development setup

You need Python 3.11+ with [uv](https://docs.astral.sh/uv/), Node.js 22 and PostgreSQL 16+. pgvector is optional.

```bash
git clone https://github.com/<your-username>/stash.git && cd stash

# Backend (http://localhost:4000)
cd backend
cp .env.example .env          # set DATABASE_URL and JWT_SECRET; add SAFETY_REQUIRED=false to work without AI keys
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --port 4000 --reload

# Worker, in a second terminal
cd backend && uv run python -m app.worker

# Frontend, in a third terminal (http://localhost:5173)
cd frontend && npm ci && npm run dev
```

Without AI keys the canvas, sharing and reminders still work and chat reports that the assistant is off. Without SMTP,
emails are printed to the API log. Without S3, uploads go to `backend/.uploads`.

## Running the checks

CI runs exactly these on every push and pull request; please run them before opening a PR.

```bash
# Backend
cd backend
createdb stash_test                              # once; the tests reset this database on every run
uv run ruff check .
uv run pytest -q                                 # uses TEST_DATABASE_URL, default: local socket, db stash_test

# Frontend
cd frontend
npm run build                                    # type-check and production build
```

Point the tests at another server with `TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/stash_test`.
**Never point it at a database you care about:** the test suite drops and recreates its schema.

Tests marked `eval` call real AI providers and are skipped by default. Run them only if you are changing retrieval or
prompts and have keys: `uv run python -m pytest tests/test_eval.py -s`.

## Project layout

| Path | What lives there |
| --- | --- |
| `backend/app/routes/` | HTTP endpoints |
| `backend/app/services/` | Domain logic: chat agents, search, safety, mail, reminders, uploads |
| `backend/migrations/versions/` | Alembic migrations |
| `backend/tests/` | Pytest suite (one file per area, e.g. `test_security.py`) |
| `frontend/src/canvas/` | The canvas, cards and their sync logic |
| `frontend/src/pages/` | Dashboard, settings, reminders and public pages |
| `deploy/` | Server setup, nginx, systemd and deploy scripts |

See [`AI.md`](AI.md) for the AI pipeline and [`PLAN.md`](PLAN.md) for design decisions.

## Making changes

1. Fork the repo and create a branch from `main`: `git checkout -b fix/reminder-timezone`.
2. Keep each PR to one logical change. Unrelated refactors belong in their own PR.
3. Add or update tests for any behaviour change. Bug fixes should include a test that fails without the fix.
4. If you change the database schema, add an Alembic migration
   (`uv run alembic revision -m "short description"`) and make sure `upgrade head` works on a fresh database.
5. If you add a setting, document it in `backend/.env.example` and, if it is user-facing, in the README.
6. Update docs that your change makes out of date.

### Code style

- **Python:** formatted and linted by ruff (line length 120, rules in `backend/pyproject.toml`). Use type hints and
  async SQLAlchemy, matching the surrounding code.
- **TypeScript/React:** strict TypeScript, function components and hooks, Tailwind classes using the design tokens
  in `frontend/src/styles.css`. `npm run build` must pass with no type errors.
- Prefer small, readable functions and clear names over comments. Add a comment when the *why* isn't obvious.
- Match the existing patterns: API responses use the `{ "data": ... }` / `{ "error": { "code", "message" } }`
  envelope, and every route checks that the signed-in user owns the resource.

### Commit messages

Write the subject in the imperative mood, under about 72 characters, describing the effect
(e.g. `Fix reminders firing an hour late after DST change`). Add a body explaining *why* when it isn't obvious.

## Pull requests

- Fill in what the change does, why, and how you tested it. Add screenshots or a short clip for UI changes.
- Link the issue it closes (`Closes #123`).
- Make sure CI is green. A maintainer will review, and may ask for changes; please push follow-up commits rather than
  force-pushing during review so the conversation stays readable.
- PRs are squash-merged into `main`. Merging to `main` deploys to production, so only maintainers merge.

## Things that need extra care

These areas protect user data. Changes to them get a closer review, and should come with tests:

- **Authentication and sessions** (`app/routes/auth.py`, cookies, tokens, OAuth)
- **Tenant isolation:** every query must be scoped to the current user; see `tests/test_security.py`
- **Content safety** (`app/services/safety`): flagged content must never be shown, indexed, emailed or used in
  answers. Do not add bypasses, even for testing.
- **Link fetching / SSRF protection** (`app/services/links/fetch.py`)
- **Security headers, CSP and nginx config** (`app/middleware`, `deploy/nginx`)

Never commit secrets, real credentials, production hostnames or IP addresses. Use placeholders such as
`YOUR_RDS_ENDPOINT` in docs and examples.

## Reporting security issues

Please **do not open a public issue** for vulnerabilities. Report them privately through
[GitHub Security Advisories](https://github.com/SurajsinghBayas/stash/security/advisories/new) with a description,
steps to reproduce and the impact you expect. You'll get a response as soon as possible, and credit in the fix if you
would like it.

## Code of conduct

Be respectful and constructive. Assume good intent, keep feedback about the code rather than the person, and help
newcomers find their way. Harassment or abusive behaviour is not tolerated and may get you blocked from the project.
