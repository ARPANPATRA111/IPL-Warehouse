# IPL Cricket Data Warehouse

A complete Cricket Analytics Data Warehouse system featuring an incremental ETL pipeline, star schema design, data quality checks, a FastAPI analytics backend, and a modern React frontend.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)
![React](https://img.shields.io/badge/React-18-61dafb)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Documentation

- `guide.md` contains the exact commands to run, test, and troubleshoot the project.
- `docs/project_documentation.md` explains the project scope, architecture, runtime modes, and future enhancement roadmap.
- `docs/project_report.md` is the presentation-ready report and jury talk track.
- `docs/architecture.md` describes the current system design.
- `docs/future_enhancements.md` lists the next product, analytics, AI, deployment, and quality upgrades grounded in the current implementation.

---

## Features

- **Incremental ETL Pipeline**: Checksum-based extraction from Cricsheet, validation, transformation, and loading
- **Star Schema**: 8 dimension tables + 2 fact tables (~300K delivery records)
- **Data Quality**: 10 automated checks with pass/warn/fail reporting
- **Analytics**: 22 SQL queries with OLAP operations (ROLLUP, CUBE, WINDOW functions)
- **Backend API**: FastAPI service exposing warehouse analytics as JSON endpoints
- **Frontend**: React + Vite dashboard with seven analytics views, Query Lab, and Recharts visualizations
- **Docker**: Local database and ETL container workflow
- **CI/CD**: GitHub Actions pipeline (lint → test → build → deploy)
- **Cloud Ready**: Supabase (database) + deployable API/frontend split

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Docker (optional)

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/your-username/ipl-data-warehouse.git
cd ipl-data-warehouse
docker compose up -d postgres
```

Then use the local setup flow below to start the API and frontend.

### Option 2: Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m etl.pipeline --schema-only
python -m etl.pipeline --local-data ./ipl_json
uvicorn api.main:app --host 127.0.0.1 --port 8000
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 after both services are running.

For hosted deployments, set `FRONTEND_ORIGINS` on the API host and `VITE_API_BASE_URL` on the frontend host.

---

## Project Structure

```
ipl-data-warehouse/
├── config/
│   ├── settings.py
│   └── logging_config.py
├── sql/
│   ├── 01_create_schema.sql
│   ├── 02_create_indexes.sql
│   ├── 03_seed_dimensions.sql
│   ├── 04_analytical_queries.sql
│   ├── 05_olap_operations.sql
│   ├── 06_create_views.sql
│   └── 07_stored_procedures.sql
├── etl/
│   ├── extract.py
│   ├── validate.py
│   ├── transform_helpers.py
│   ├── transform.py
│   ├── load.py
│   ├── data_quality.py
│   └── pipeline.py
├── api/
│   ├── main.py
│   ├── queries.py
│   └── db.py
├── frontend/
│   ├── src/App.tsx
│   ├── src/styles.css
│   └── vite.config.ts
├── dashboard/
├── tests/
│   ├── conftest.py
│   ├── test_transform.py
│   ├── test_validate.py
│   ├── test_helpers.py
│   ├── test_extract.py
│   ├── test_load.py
│   ├── test_data_quality.py
│   ├── test_pipeline.py
│   └── test_config.py
├── docs/
│   ├── architecture.md
│   ├── schema_diagram.md
│   ├── deployment_guide.md
│   └── supabase_local_runbook.md
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── Procfile
├── runtime.txt
└── README.md
```

---

## Data Pipeline

```
Cricsheet (1193 JSON files)
        │
        ▼
   ┌─── Extract ───┐
   │  Download ZIP  │
   │  SHA256 verify │
   └───────┬────────┘
           ▼
   ┌─── Validate ──┐
   │  Schema check  │
   │  Type check    │
   │  Business rules│
   └───────┬────────┘
           ▼
   ┌─── Transform ─┐
   │  Flatten JSON  │
   │  Normalize     │
   │  Compute dims  │
   └───────┬────────┘
           ▼
   ┌─── Load ──────┐
   │  Upsert dims   │
   │  Insert facts  │
   │  Batch 1000    │
   └───────┬────────┘
           ▼
   ┌─── Quality ───┐
   │  10 DQ checks  │
   │  Log results   │
   └────────────────┘
```

---

## Frontend Views

| Page | Key Visualizations |
|------|-------------------|
| **Overview** | 8 KPIs, season trends, top performers |
| **Batting** | Leaderboard, strike rate scatter, player profiles |
| **Bowling** | Economy charts, wicket leaders, bowler profiles |
| **Teams** | Win %, season performance, toss analysis |
| **Venues** | Run rates, boundary %, bat-first vs chase |
| **Head-to-Head** | Matchup records, season breakdown, top performers |
| **Query Lab** | Natural-language prompt to SQL, result table, auto chart |

---

## Analytical Queries

The project includes 22 analytical queries demonstrating:

- `GROUP BY ROLLUP` — Season → team aggregations
- `GROUP BY CUBE` — Multi-dimensional summaries
- `RANK() / DENSE_RANK()` — Leaderboards
- `NTILE()` — Performance percentiles
- `LAG() / LEAD()` — Season-over-season comparisons
- `Running totals` — Cumulative career milestones
- `PARTITION BY` — Within-group analytics

---

## Testing

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=etl --cov=config --cov-report=html
python -m pytest tests/test_transform.py -v
```

---

## Cloud Deployment

| Service | Provider | Purpose |
|---------|----------|---------|
| Database | Supabase | Managed PostgreSQL |
| API | Railway / Render / Fly.io | Backend hosting |
| Frontend | Vercel / Netlify / Static host | Web hosting |
| CI/CD | GitHub Actions | Automated pipeline |

### Vercel Frontend Checklist

1. Import the `frontend` directory as a Vercel project.
2. Set `VITE_API_BASE_URL` to your deployed FastAPI base URL.
3. Set `FRONTEND_ORIGINS` on the API host to include the Vercel domain.
4. Use the generated `frontend/vercel.json` so Vercel builds from `npm run build` and serves the Vite `dist` folder.

See [docs/deployment_guide.md](docs/deployment_guide.md) for detailed instructions.
See [docs/supabase_local_runbook.md](docs/supabase_local_runbook.md) for the exact local commands used with Supabase.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [Cricsheet](https://cricsheet.org/) for providing open cricket data
- [FastAPI](https://fastapi.tiangolo.com/) for the backend API
- [React](https://react.dev/) and [Vite](https://vitejs.dev/) for the frontend
- [Recharts](https://recharts.org/) for interactive visualizations
