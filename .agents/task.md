# AutoDS AI — Phase 1 Task Tracker

## Phase 1: Project Setup

### Infrastructure
- [x] Create monorepo directory structure
- [x] docker-compose.yml (PostgreSQL, Redis, MinIO, MLflow, Nginx)
- [x] Dockerfile.backend
- [x] Dockerfile.frontend
- [x] nginx.conf

### Backend — Foundation
- [x] pyproject.toml + requirements.txt
- [x] .env.example
- [x] app/main.py (FastAPI factory, CORS, lifespan)
- [x] app/config.py (pydantic BaseSettings)
- [x] app/database.py (async SQLAlchemy engine + session)
- [x] app/dependencies.py (get_db, get_current_user)
- [x] app/utils/logging.py (structlog)
- [x] app/utils/security.py (JWT, password hashing)
- [x] app/utils/file_utils.py

### Backend — ORM Models
- [x] app/models/user.py
- [x] app/models/project.py
- [x] app/models/dataset.py
- [x] app/models/pipeline_run.py
- [x] app/models/ml_model.py
- [x] app/models/prediction.py
- [x] app/models/report.py

### Backend — Pydantic Schemas
- [x] app/schemas/user.py
- [x] app/schemas/project.py
- [x] app/schemas/dataset.py
- [x] app/schemas/pipeline.py
- [x] app/schemas/model.py
- [x] app/schemas/report.py

### Backend — Services
- [x] app/services/auth_service.py
- [x] app/services/project_service.py
- [x] app/services/dataset_service.py
- [x] app/services/pipeline_service.py
- [x] app/services/model_service.py
- [x] app/services/storage_service.py (MinIO)

### Backend — API Routes
- [x] app/api/v1/auth.py
- [x] app/api/v1/users.py
- [x] app/api/v1/projects.py
- [x] app/api/v1/datasets.py
- [x] app/api/v1/pipelines.py
- [x] app/api/v1/models.py
- [x] app/api/v1/predictions.py
- [x] app/api/v1/reports.py
- [x] app/api/v1/ws.py (WebSocket)
- [x] app/api/router.py

### Backend — Alembic Migrations
- [x] alembic.ini
- [x] alembic/env.py
- [x] Initial migration (all tables)

### Frontend — Scaffold
- [x] npx create-next-app@latest
- [x] tailwind.config.ts
- [x] globals.css (design tokens)
- [x] Shadcn UI init + components

### Frontend — Layout
- [x] src/app/layout.tsx
- [x] src/components/layout/Sidebar.tsx
- [x] src/components/layout/Topbar.tsx
- [x] src/components/layout/PageShell.tsx

### Frontend — Auth
- [x] src/lib/api.ts (Axios instance)
- [x] src/lib/auth.ts (token management)
- [x] src/store/pipelineStore.ts (Zustand)
- [x] src/types/index.ts
- [x] src/app/(auth)/login/page.tsx
- [x] src/app/(auth)/register/page.tsx
- [x] src/middleware.ts (protected routes)

### Frontend — Dashboard
- [x] src/app/dashboard/page.tsx
- [x] src/app/projects/page.tsx
