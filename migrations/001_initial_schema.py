"""
Initial Schema Migration: Complete Database Setup
Creates all tables from schema.sql if they don't exist.

Migration ID: 001
Migration Name: initial_schema

This is a consolidated migration containing all schema changes through v3.7.
It includes: base tables, is_pinned columns, is_hidden flag, relationship_label,
recovery codes, and custom advisors support.

IMPORTANT: This migration checks ACTUAL table existence, not just migration records.
This makes it idempotent and safe to re-run if tables are missing.
"""

import psycopg2
import psycopg2.extras
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent

REQUIRED_TABLES = [
    'client_profiles', 'counselor_profiles', 'sessions', 'messages',
    'game_state', 'farm_items', 'character_cards', 'card_updates',
    'self_cards', 'world_events', 'entity_mentions',
    'progress_tracking', 'session_insights', 'change_log',
    'performance_metrics'
]


def get_existing_tables(cursor) -> set:
    """Get set of existing table names in public schema."""
    cursor.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
    """)
    return {row[0] for row in cursor.fetchall()}


def execute_schema_sql(database_url: str):
    """Execute schema.sql file to create all tables."""
    schema_path = BASE_DIR / "schema.sql"
    
    if not schema_path.exists():
        raise FileNotFoundError(f"schema.sql not found at {schema_path}")
    
    logger.info(f"[SCHEMA] Reading schema from {schema_path}")
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        logger.info("[SCHEMA] Executing schema.sql...")
        cursor.execute(schema_sql)
        conn.commit()
        logger.info("[SCHEMA] schema.sql executed successfully")
    except Exception as e:
        conn.rollback()
        logger.error(f"[SCHEMA] Failed to execute schema.sql: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def ensure_migrations_table(database_url: str):
    """Create _migrations table if it doesn't exist."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                migration_id TEXT UNIQUE NOT NULL,
                migration_name TEXT NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def record_migration(database_url: str, migration_id: str, migration_name: str):
    """Record migration as applied."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO _migrations (migration_id, migration_name) VALUES (%s, %s) "
            "ON CONFLICT (migration_id) DO NOTHING",
            (migration_id, migration_name)
        )
        conn.commit()
        logger.info(f"[RECORD] Migration {migration_id} recorded")
    except Exception as e:
        logger.warning(f"[RECORD] Could not record migration: {e}")
    finally:
        cursor.close()
        conn.close()


def run_migration(db_path: str):
    """Apply initial schema - creates all tables if missing."""
    MIGRATION_ID = "001"
    MIGRATION_NAME = "initial_schema"
    
    logger.info(f"[MIGRATION 001] Starting: {MIGRATION_NAME}")
    logger.info(f"[MIGRATION 001] Database URL: {db_path[:30]}...")
    
    ensure_migrations_table(db_path)
    
    conn = psycopg2.connect(db_path)
    cursor = conn.cursor()
    
    try:
        existing_tables = get_existing_tables(cursor)
        logger.info(f"[MIGRATION 001] Found {len(existing_tables)} existing tables")
        
        missing_tables = [t for t in REQUIRED_TABLES if t not in existing_tables]
        
        if missing_tables:
            logger.warning(f"[MIGRATION 001] Missing tables: {missing_tables}")
            logger.info("[MIGRATION 001] Creating all tables from schema.sql...")
            
            cursor.close()
            conn.close()
            
            execute_schema_sql(db_path)
            
            conn = psycopg2.connect(db_path)
            cursor = conn.cursor()
            
            existing_tables = get_existing_tables(cursor)
            still_missing = [t for t in REQUIRED_TABLES if t not in existing_tables]
            
            if still_missing:
                raise RuntimeError(f"Tables still missing after schema.sql: {still_missing}")
            
            logger.info(f"[MIGRATION 001] All {len(REQUIRED_TABLES)} tables now exist")
        else:
            logger.info("[MIGRATION 001] All required tables already exist")
        
        conn.commit()
        
        record_migration(db_path, MIGRATION_ID, MIGRATION_NAME)
        
        logger.info(f"[MIGRATION 001] Completed successfully")
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[MIGRATION 001] Failed: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    import os
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL", "postgresql://localhost/gameapy")
    run_migration(db_path)
