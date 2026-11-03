# Docker Containerization and Deployment Guide

This document describes containerizing the platform using Docker and Docker Compose for production and staging deployments.

## 1. Overview

The platform is decomposed into three containerized services:
1. **`db`**: PostgreSQL 16 image with pre-installed `pgvector/pgvector:pg16`.
2. **`backend`**: FastAPI ASGI server executed via Uvicorn with Gunicorn process management.
3. **`frontend`**: Vite application built into static assets and served via high-performance Nginx.

---

## 2. Docker Compose Configuration

Example `docker-compose.yml` configuration:

```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    restart: always
    environment:
      POSTGRES_DB: legal_rag
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: rag_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    environment:
      DATABASE_URL: postgresql+asyncpg://rag_user:rag_password@db:5432/legal_rag
      GROQ_API_KEY: ${GROQ_API_KEY}
    depends_on:
      - db
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

---

## 3. Production Deployment Commands

```bash
# Build and start all services in detached mode
docker compose up --build -d

# Check running container health
docker compose ps

# View service logs
docker compose logs -f backend
```
