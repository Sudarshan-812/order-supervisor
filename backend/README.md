# Backend

FastAPI + Temporal worker + asyncpg. See the repo root `README.md` for full
setup and `ARCHITECTURE.md` for design.

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

uvicorn app.main:app --reload --port 8000     # terminal 1
python -m app.temporal.worker                 # terminal 2  (needs: temporal server start-dev)
pytest                                        # tests (mock LLM, no network)
```

Module map: `app/api` (HTTP) · `app/temporal` (workflow + activities + worker) ·
`app/agent` (runtime, classifier, memory, prompts, llm) · `app/event_generator.py`.
