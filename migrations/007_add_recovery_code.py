#!/usr/bin/env python3
"""
Migration 007: Add recovery code columns to client_profiles

This adds support for account recovery via recovery codes:
- recovery_code_hash: Hashed recovery code for validation
- recovery_code_expires_at: Optional expiration (NULL = never expires)
- last_recovery_at: Track when account was last recovered

For alpha stage: codes do not expire by default
"""

import os
import sys
import psycopg2
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def migrate(database_url: str):
    """Add recovery code columns to client_profiles table with explicit database_url."""
    logger.info("[MIGRATION 007] Adding recovery code columns to client_profiles")

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    try:
        # Check which columns already exist
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'client_profiles'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]

        # Add recovery_code_hash column
        if 'recovery_code_hash' not in existing_columns:
            logger.info("[INFO] Adding recovery_code_hash column...")
            cursor.execute("""
                ALTER TABLE client_profiles
                ADD COLUMN IF NOT EXISTS recovery_code_hash TEXT
            """)
            logger.info("[OK] recovery_code_hash column added")
        else:
            logger.info("[SKIP] recovery_code_hash column already exists")

        # Add recovery_code_expires_at column
        if 'recovery_code_expires_at' not in existing_columns:
            logger.info("[INFO] Adding recovery_code_expires_at column...")
            cursor.execute("""
                ALTER TABLE client_profiles
                ADD COLUMN IF NOT EXISTS recovery_code_expires_at TIMESTAMPTZ
            """)
            logger.info("[OK] recovery_code_expires_at column added")
        else:
            logger.info("[SKIP] recovery_code_expires_at column already exists")

        # Add last_recovery_at column
        if 'last_recovery_at' not in existing_columns:
            logger.info("[INFO] Adding last_recovery_at column...")
            cursor.execute("""
                ALTER TABLE client_profiles
                ADD COLUMN IF NOT EXISTS last_recovery_at TIMESTAMPTZ
            """)
            logger.info("[OK] last_recovery_at column added")
        else:
            logger.info("[SKIP] last_recovery_at column already exists")

        conn.commit()
        logger.info("[OK] Migration 007 completed successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Migration 007 failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from app.core.config import settings
    migrate(settings.database_url)
