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
