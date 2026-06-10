# FastAPI Template

## Setup

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload
```

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/version`
- `GET /docs`

## Agent Tracing

Each `/api/v1/query` request can be traced to a JSON file containing LangChain/LangGraph callback events (chain starts/ends, tool calls, model calls, and final result).

- Enable/disable with `AGENT_TRACING_ENABLED` (default: `true`)
- Output directory with `AGENT_TRACES_DIR` (default: `data/traces`)

When enabled, the query response metrics include a `trace_file` path.
