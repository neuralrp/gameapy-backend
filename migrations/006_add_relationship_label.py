#!/usr/bin/env python3
"""
Migration 006: Add relationship_label column to character_cards

This adds a custom label field for character cards (e.g., "Sister", "Mother")
that allows specific matching instead of generic relationship categories.
"""

import os
import sys
import psycopg2
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def migrate(database_url: str):
    """Add relationship_label column to character_cards table with explicit database_url."""
    logger.info("[MIGRATION 006] Adding relationship_label column to character_cards")

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'character_cards'
            AND column_name = 'relationship_label'
        """)
        if cursor.fetchone():
            logger.info("[OK] Column relationship_label already exists")
            return

        # Add relationship_label column
        logger.info("[INFO] Adding relationship_label column...")
        cursor.execute("""
            ALTER TABLE character_cards
            ADD COLUMN IF NOT EXISTS relationship_label TEXT
        """)

        conn.commit()
        logger.info("[OK] Migration completed successfully")
        logger.info("[INFO] Character cards can now have custom relationship labels")

    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from app.core.config import settings
    migrate(settings.database_url)
