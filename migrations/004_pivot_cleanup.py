"""
Migration 004: Pivot Cleanup
Adds is_pinned columns and removes canon law dependencies.

Auto-run on startup if not yet applied.
"""

import sqlite3
import os
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@contextmanager
def get_connection(db_path: str):
    """Get database connection with explicit db_path."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_applied(db_path: str):
    """Check if migration has already been applied."""
    try:
        with get_connection(db_path) as conn:
            # Check if is_pinned exists in any table
            for table in ['self_cards', 'character_cards', 'world_events']:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if 'is_pinned' not in columns:
                    return False
            return True
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        return False


def migrate(db_path: str):
    """Execute migration with explicit db_path parameter."""
    try:
        with get_connection(db_path) as conn:
            # Ensure tables exist first
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS self_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL UNIQUE,
                    card_json TEXT NOT NULL,
                    auto_update_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES client_profiles(id)
                );
                
                CREATE TABLE IF NOT EXISTS character_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    card_name TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    card_json TEXT NOT NULL,
                    auto_update_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES client_profiles(id)
                );
                
                CREATE TABLE IF NOT EXISTS world_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    entity_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    key_array TEXT NOT NULL,
                    description TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    is_canon_law BOOLEAN DEFAULT FALSE,
                    auto_update_enabled BOOLEAN DEFAULT TRUE,
                    resolved BOOLEAN DEFAULT FALSE,
                    vector_embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES client_profiles(id)
                );
            """)
            
            # Add is_pinned columns if they don't exist
            for table in ['self_cards', 'character_cards', 'world_events']:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if 'is_pinned' not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE")
                    logger.info(f"Added is_pinned to {table}")
            
            # Create indexes for pinned cards lookup
            conn.execute("CREATE INDEX IF NOT EXISTS idx_self_cards_pinned ON self_cards(client_id, is_pinned)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_character_cards_pinned ON character_cards(client_id, is_pinned)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_world_events_pinned ON world_events(client_id, is_pinned)")
            logger.info("Created pinned card indexes")
            
            logger.info("Migration 004 completed successfully")
            
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.warning("Columns already exist, migration already applied")
        else:
            logger.error(f"Migration error: {e}")
            raise
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from app.core.config import settings
    migrate(settings.database_path or "gameapy.db")