"""
Migration tracking system
Ensures migrations run once and in order
"""

import psycopg2
from datetime import datetime


def initialize_tracker(database_url: str):
    """Create migration tracking table if not exists."""
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
    conn.close()


def is_migration_applied(database_url: str, migration_id: str) -> bool:
    """Check if migration already applied."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM _migrations WHERE migration_id = %s", (migration_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def record_migration(database_url: str, migration_id: str, migration_name: str):
    """Record successful migration."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO _migrations (migration_id, migration_name)
            VALUES (%s, %s)
        """, (migration_id, migration_name))
        conn.commit()
    except psycopg2.IntegrityError:
        # Migration already recorded, ignore
        pass
    finally:
        conn.close()
