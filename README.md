# AutoDS AI

An Autonomous Data Scientist platform.

## Architecture

This project consists of two main components:
- **Backend**: FastAPI, SQLAlchemy (Async), PostgreSQL
- **Frontend**: Next.js 15, React 19, Tailwind CSS 4, shadcn/ui

## Prerequisites

- Python 3.12+
- Node.js 22 LTS
- PostgreSQL 16+

## Setup & Development

### 1. Database
Ensure PostgreSQL is running and create a database named `autods` (or adjust the URL in `.env`).

### 2. Backend
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Unix
source venv/bin/activate

pip install -r requirements.txt -r requirements-dev.txt

# Run migrations
alembic upgrade head

# Start server
fastapi run app/main.py --reload
# Or uvicorn app.main:app --reload
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables
See `.env.example` at the root for a unified view of all configurable variables.
