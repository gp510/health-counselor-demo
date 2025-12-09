# Repository Guidelines

## Project Structure & Module Organization
- `configs/` holds shared Solace settings plus agent and gateway YAML files; use these as templates when adding agents.
- `src/` contains Python agent logic (wearable listener, automation tools); keep new utilities here.
- `server/dashboard_api/` is the FastAPI backend for the dashboard; models and DB wiring live under `models/`.
- `client/dashboard/` is the React UI (Vite); assets and components live in `src/`.
- `scripts/` includes helpers such as `wearable_simulator.py` and database population scripts; prefer extending these over ad‑hoc scripts.
- `tests/` contains pytest suites; CSV_Data and `*.db` SQLite files provide sample data fixtures.

## Build, Test, and Development Commands
- Install Python deps: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt`.
- Run agents (set `DATA_PATH="$(pwd)"`): `sam run configs/agents/health-orchestrator.yaml` plus companion agent configs in separate terminals; gateway via `sam run configs/gateways/webui.yaml`.
- Backend API (hot reload): `DATA_PATH="$(pwd)" uvicorn server.dashboard_api.main:app --port 8082 --reload`.
- Frontend: `cd client/dashboard && npm install && npm run dev` (or `npm run build` for production).
- Tests: `DATA_PATH="$(pwd)" pytest tests/ -v`; add `--cov=src` for coverage and `-m "not integration"` to skip integration-marked tests.

## Coding Style & Naming Conventions
- Python: 4-space indent, type hints where practical, snake_case modules/functions; keep agent tool functions small and pure where possible.
- YAML configs: reuse anchors/aliases in `configs/shared_config.yaml`; prefer lowercase dashed file names (e.g., `sleep-agent.yaml`).
- Frontend: follow existing Vite/React patterns; keep components in `client/dashboard/src`, SCSS/TSX names in PascalCase.

## Testing Guidelines
- Framework: pytest with settings in `pytest.ini` (`test_*.py`, `timeout=30`, integration marker).
- Tests should set `DATA_PATH` to the repo root so SQLite fixtures resolve.
- Favor deterministic unit tests over DB-heavy integration runs; seed CSV/DB fixtures when adding new agents or metrics.

## Commit & Pull Request Guidelines
- Commits: concise, imperative subjects (e.g., `Add sleep agent config`, `Harden wearable simulator`); group related changes together.
- PRs: include what/why, key commands run (`pytest`, `npm test` if added), screenshots for UI changes, and notes on data/schema updates.
- Link issues or tickets when available; highlight breaking config changes (env vars, Solace topics, DB schema) in the description.

## Security & Configuration Tips
- Keep secrets in `.env` (see `.env.example`); never commit credentials or broker passwords.
- Ensure `DATA_PATH` matches the repo root when running agents, tests, or scripts so DB paths resolve correctly.
- For production-like tests, run against non-production Solace brokers and scrub generated logs before sharing.
