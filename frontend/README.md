# Frontend (Root)

This is the root frontend for the notarial KG-RAG project.

It is intentionally frontend-only and does not implement backend logic.
It consumes existing API endpoints when available.

## What it includes

- Chat tab wired to `POST /api/v1/query`
- Knowledge Graph tab wired to `GET /api/v1/graph/` with optional `?dossier_id=...` filtering
- Metrics tab wired to `GET /api/v1/metrics/summary` and `GET /api/v1/metrics/history`
- Upload drawer wired to `POST /api/v1/ingest/` and polling `GET /api/v1/ingest/status/{job_id}`
- Dossier selector wired to `GET /api/v1/dossiers/`

## No fake data policy

- No mock documents
- No seeded charts
- No placeholder API payloads
- All views show empty/error states until backend returns real data

## Run frontend only

From repository root:

```powershell
cd frontend
python -m http.server 3000
```

Open `http://localhost:3000`.

Set API Base URL in the top-right field (default `http://localhost:8000`).
