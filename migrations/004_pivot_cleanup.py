"""
Migration 004: Pivot Cleanup
Adds is_pinned columns and removes canon law dependencies.

Auto-run on startup if not yet applied.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


def is_applied(database_url: str):
    """Check if migration has already been applied."""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    try:
        # Check if is_pinned exists in all tables
        for table in ['self_cards', 'character_cards', 'world_events']:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'is_pinned'
            """, (table,))
            if not cursor.fetchone():
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def migrate(db_path: str):
    """Execute migration with explicit db_path parameter."""
    logger.info("[MIGRATION 004] Starting pivot cleanup migration")

    if is_applied(db_path):
        logger.info("[SKIP] Migration 004 already applied, skipping...")
        return

    conn = psycopg2.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add is_pinned columns
        for table in ['self_cards', 'character_cards', 'world_events']:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'is_pinned'
            """, (table,))
            if not cursor.fetchone():
                cursor.execute(f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE
                """)
                logger.info(f"[OK] Added is_pinned column to {table}")
            else:
                logger.info(f"[SKIP] is_pinned already exists in {table}")

        # Create indexes for pinned cards
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_self_cards_pinned
            ON self_cards(client_id, is_pinned)
        """)
        logger.info("[OK] Created idx_self_cards_pinned")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_character_cards_pinned
            ON character_cards(client_id, is_pinned)
        """)
        logger.info("[OK] Created idx_character_cards_pinned")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_world_events_pinned
            ON world_events(client_id, is_pinned)
        """)
        logger.info("[OK] Created idx_world_events_pinned")

        conn.commit()
        logger.info("[OK] Migration 004 completed successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Migration 004 failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.config import settings
    migrate(settings.database_url)
