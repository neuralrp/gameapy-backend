#!/usr/bin/env python3
"""
Migration 005: Add is_hidden flag to counselor_profiles

This adds a flag to mark counselors as hidden (e.g., Easter egg characters
that can only be summoned, not selected directly).
"""

import os
import sys
import sqlite3
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def migrate(db_path: str):
    """Add is_hidden column to counselor_profiles table with explicit db_path."""
    logger.info("[MIGRATION 005] Adding is_hidden column to counselor_profiles")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(counselor_profiles)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'is_hidden' in columns:
            logger.info("[OK] Column is_hidden already exists")
            return

        # Add is_hidden column
        logger.info("[INFO] Adding is_hidden column...")
        cursor.execute("""
            ALTER TABLE counselor_profiles
            ADD COLUMN is_hidden BOOLEAN DEFAULT FALSE
        """)

        # Mark Deirdre as hidden (Easter egg) - if she exists
        logger.info("[INFO] Checking for Deirdre to mark as hidden...")
        cursor.execute("""
            SELECT COUNT(*) FROM counselor_profiles WHERE LOWER(name) = 'deirdre'
        """)
        deirdre_exists = cursor.fetchone()[0]
        
        if deirdre_exists > 0:
            cursor.execute("""
                UPDATE counselor_profiles
                SET is_hidden = TRUE
                WHERE LOWER(name) = 'deirdre'
            """)
            logger.info("[INFO] Deirdre is now hidden from counselor selection")
            logger.info("[INFO] Deirdre can still be summoned with 'Summon Deirdre' phrase")
        else:
            logger.info("[INFO] Deirdre not found in database yet (will be marked hidden when seeded)")

        conn.commit()
        logger.info("[OK] Migration completed successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from app.core.config import settings
    migrate(settings.database_path or "gameapy.db")
