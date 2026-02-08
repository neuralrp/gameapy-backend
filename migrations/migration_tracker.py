"""
Migration tracking system
Ensures migrations run once and in order
"""

import sqlite3
from datetime import datetime


def initialize_tracker(db_path: str = "gameapy.db"):
    """Create migration tracking table if not exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migration_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_id TEXT UNIQUE NOT NULL,
            migration_name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'success'
        )
    """)
    conn.commit()
    conn.close()


def is_migration_applied(db_path: str, migration_id: str) -> bool:
    """Check if migration already applied."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM migration_history WHERE migration_id = ?", (migration_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def record_migration(db_path: str, migration_id: str, migration_name: str):
    """Record successful migration."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO migration_history (migration_id, migration_name)
        VALUES (?, ?)
    """, (migration_id, migration_name))
    conn.commit()
    conn.close()
