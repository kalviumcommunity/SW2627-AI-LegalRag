"""Database management and initialization system.

Provides programmatic and CLI commands to:
- Verify database connectivity and schema readiness
- Apply Alembic migrations to HEAD
- Reset/wipe the database cleanly if requested
- Seed initial demonstration users
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.models import User

logger = logging.getLogger("app.db.init_db")

EXPECTED_TABLES = [
    "alembic_version",
    "chunks",
    "documents",
    "properties",
    "property_documents",
    "property_extractions",
    "property_risk_assessments",
    "property_risk_findings",
    "users",
]


def get_backend_dir() -> Path:
    """Return absolute path to backend directory."""
    return Path(__file__).resolve().parent.parent.parent


def get_alembic_config(settings: Settings | None = None, direct: bool = True) -> Config:
    """Construct Alembic Config targeting the configured PostgreSQL database."""
    settings = settings or get_settings()
    backend_dir = get_backend_dir()
    ini_path = backend_dir / "alembic.ini"
    migrations_dir = backend_dir / "migrations"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(migrations_dir))
    url = settings.get_database_url(direct=direct)
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def check_database(settings: Settings | None = None) -> dict[str, Any]:
    """Check database connection, tables, vector extension, and Alembic version."""
    settings = settings or get_settings()
    url = settings.get_database_url(direct=False)
    if not url:
        return {"status": "error", "message": "DATABASE_URL is not configured."}

    engine = create_engine(url, connect_args={"connect_timeout": 10})
    with engine.connect() as conn:
        db_info = conn.execute(
            text("SELECT current_database(), current_user, version();")
        ).fetchone()

        tables_res = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name;"
            )
        ).fetchall()
        table_names = [t[0] for t in tables_res]

        alembic_v = None
        if "alembic_version" in table_names:
            alembic_v = conn.execute(
                text("SELECT version_num FROM alembic_version;")
            ).scalar()

        missing_tables = [t for t in EXPECTED_TABLES if t not in table_names]

        # Vector extension check
        ext_res = conn.execute(
            text(
                "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
            )
        ).fetchone()

        return {
            "status": "ready" if not missing_tables else "incomplete",
            "database": db_info[0] if db_info else None,
            "user": db_info[1] if db_info else None,
            "version": db_info[2][:40] if db_info else None,
            "alembic_revision": alembic_v,
            "tables_found": table_names,
            "missing_tables": missing_tables,
            "pgvector_installed": ext_res is not None,
            "pgvector_version": ext_res[1] if ext_res else None,
        }


def migrate_database(settings: Settings | None = None) -> str:
    """Run Alembic migrations to HEAD using direct connection."""
    settings = settings or get_settings()
    cfg = get_alembic_config(settings, direct=True)
    command.upgrade(cfg, "head")
    return "Successfully upgraded database schema to HEAD."


def reset_database(settings: Settings | None = None) -> None:
    """Wipe all public tables in the database and re-run all migrations."""
    settings = settings or get_settings()
    direct_url = settings.get_database_url(direct=True)
    if not direct_url:
        raise ValueError("Cannot reset database: DATABASE_URL is not configured.")

    engine = create_engine(direct_url, connect_args={"connect_timeout": 15})
    with engine.connect() as conn:
        drop_statements = [
            "DROP TABLE IF EXISTS property_risk_findings CASCADE",
            "DROP TABLE IF EXISTS property_risk_assessments CASCADE",
            "DROP TABLE IF EXISTS property_extractions CASCADE",
            "DROP TABLE IF EXISTS property_documents CASCADE",
            "DROP TABLE IF EXISTS properties CASCADE",
            "DROP TABLE IF EXISTS chunks CASCADE",
            "DROP TABLE IF EXISTS documents CASCADE",
            "DROP TABLE IF EXISTS users CASCADE",
            "DROP TABLE IF EXISTS alembic_version CASCADE",
            "CREATE EXTENSION IF NOT EXISTS vector",
        ]
        for stmt in drop_statements:
            conn.execute(text(stmt))
        conn.commit()

    migrate_database(settings)


def seed_demo_user(
    email: str = "demo@propertyintel.com",
    password: str = "DemoUser123!",
    settings: Settings | None = None,
) -> User:
    """Seed or retrieve an active user account for demonstration and testing."""
    settings = settings or get_settings()
    direct_url = settings.get_database_url(direct=True)
    if not direct_url:
        raise ValueError("DATABASE_URL is not configured.")

    engine = create_engine(direct_url)
    with Session(engine) as session:
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            return existing

        user = User(
            id=f"usr_{uuid.uuid4().hex[:16]}",
            email=email,
            hashed_password=hash_password(password),
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def main() -> None:
    """CLI entrypoint for database commands."""
    parser = argparse.ArgumentParser(
        description="Property Intelligence Platform Database Management CLI"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check database connection and schema health"
    )
    parser.add_argument(
        "--migrate", action="store_true", help="Apply Alembic migrations to HEAD"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe all database tables and rebuild from scratch",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Create default active demo user account (demo@propertyintel.com)",
    )

    args = parser.parse_args()

    # Default to check if no args provided
    if not (args.check or args.migrate or args.reset or args.seed):
        args.check = True

    if args.reset:
        print("[!] Resetting database and applying migrations to HEAD...")
        reset_database()
        print("[OK] Database reset and migrated successfully.")

    if args.migrate:
        print("[*] Running migrations to HEAD...")
        res = migrate_database()
        print(f"[OK] {res}")

    if args.seed:
        print("[*] Seeding demo user account...")
        user = seed_demo_user()
        print(f"[OK] Seeded user: {user.email} (ID: {user.id})")

    if args.check:
        print("[*] Checking database health and schema status...")
        info = check_database()
        print(f"  Status: {info.get('status', 'unknown').upper()}")
        print(f"  Database: {info.get('database')} (user: {info.get('user')})")
        print(f"  Alembic Head: {info.get('alembic_revision')}")
        print(f"  pgvector: installed={info.get('pgvector_installed')} (v{info.get('pgvector_version')})")
        print(f"  Tables Present ({len(info.get('tables_found', []))}): {', '.join(info.get('tables_found', []))}")
        if info.get("missing_tables"):
            print(f"  [!] Missing Tables: {', '.join(info['missing_tables'])}")
        else:
            print("  [OK] All required tables and vector schemas are fully operational.")


if __name__ == "__main__":
    main()
