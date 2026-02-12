#!/usr/bin/env python3
"""
Unified migration runner for Gameapy.
Runs all pending migrations in order on startup.
"""

import os
import sys
import logging
import psycopg2
import psycopg2.extras
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


MIGRATIONS = [
    {
        "id": "001",
        "name": "initial_schema",
        "module": "migrations.001_initial_schema",
        "function": "run_migration"
    }
]


def run_migration(database_url: str, migration_id: str, migration_name: str, module_path: str, function_name: str):
    """Run a single migration with explicit database_url."""
    logger.info(f"[MIGRATION {migration_id}] Starting: {migration_name}")

    try:
        # Import migration module
        module = __import__(module_path, fromlist=[function_name])
        migration_func = getattr(module, function_name)

        # Run migration with database_url parameter
        migration_func(database_url)

        # Record successful migration
        _record_migration(database_url, migration_id, migration_name)

        logger.info(f"[MIGRATION {migration_id}] Completed successfully")

    except Exception as e:
        logger.error(f"[MIGRATION {migration_id}] Failed: {e}")
        raise


def _initialize_tracker(database_url: str):
    """Initialize the migrations table."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id SERIAL PRIMARY KEY,
            migration_id TEXT UNIQUE NOT NULL,
            migration_name TEXT NOT NULL,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


def _is_migration_applied(database_url: str, migration_id: str) -> bool:
    """Check if a migration has been applied."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM _migrations WHERE migration_id = %s",
        (migration_id,)
    )
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result is not None


def _record_migration(database_url: str, migration_id: str, migration_name: str):
    """Record a migration as applied."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO _migrations (migration_id, migration_name) VALUES (%s, %s)",
            (migration_id, migration_name)
        )
        conn.commit()
    except psycopg2.IntegrityError:
        # Migration already recorded, ignore
        logger.debug(f"[MIGRATION {migration_id}] Already recorded in migration history")
    finally:
        cursor.close()
        conn.close()


def run_all_migrations():
    """Run all pending migrations in order."""
    logger.info("=" * 60)
    logger.info("Starting automatic migration runner")
    logger.info("=" * 60)

    database_url = settings.database_url
    logger.info(f"Database URL: {database_url}")

    # Initialize migration tracker
    _initialize_tracker(database_url)
    logger.info("Migration tracker initialized")

    # Run each migration if not already applied
    pending_migrations = []
    completed_migrations = []

    for migration in MIGRATIONS:
        migration_id = migration["id"]
        migration_name = migration["name"]

        if _is_migration_applied(database_url, migration_id):
            logger.info(f"[SKIP] Migration {migration_id} ({migration_name}) already applied")
            completed_migrations.append(migration_id)
        else:
            logger.info(f"[PENDING] Migration {migration_id} ({migration_name}) needs to be applied")
            pending_migrations.append(migration)

    # Run pending migrations
    if not pending_migrations:
        logger.info("=" * 60)
        logger.info("All migrations are up to date!")
        logger.info(f"Applied: {', '.join(completed_migrations)}")
        logger.info("=" * 60)
        return

    logger.info(f"Found {len(pending_migrations)} pending migration(s)")
    logger.info("-" * 60)

    for migration in pending_migrations:
        run_migration(
            database_url,
            migration["id"],
            migration["name"],
            migration["module"],
            migration["function"]
        )
        logger.info("-" * 60)

    logger.info("=" * 60)
    logger.info("All migrations completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_all_migrations()
