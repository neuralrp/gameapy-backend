"""
Migration 008: Add Custom Advisors Support

Adds columns to counselor_profiles table to support user-created custom advisors.
This is a non-breaking migration that extends existing functionality.

Migration ID: 008
Applied: 2026-02-12
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


def upgrade(database_url: str) -> None:
    """
    Apply migration 008.

    Adds:
    - client_id: Links custom advisor to creating client (NULL for system personas)
    - is_custom: Flag to distinguish user-created vs system personas
    - image_url: Future use for generated avatar images
    - last_image_regenerated: Future use for daily regeneration cooldown
    - Index: idx_counselor_profiles_client_custom for efficient filtering
    """
    logger.info("[MIGRATION 008] Adding custom advisors support to counselor_profiles")

    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'counselor_profiles'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]

        # Add client_id column (nullable, only set for custom advisors)
        if "client_id" not in existing_columns:
            cursor.execute("""
                ALTER TABLE counselor_profiles
                ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client_profiles(id)
            """)
            logger.info("[MIGRATION 008] Added client_id column")
        else:
            logger.info("[MIGRATION 008] client_id column already exists, skipping")

        # Add is_custom flag (default FALSE for existing system personas)
        if "is_custom" not in existing_columns:
            cursor.execute("""
                ALTER TABLE counselor_profiles
                ADD COLUMN IF NOT EXISTS is_custom BOOLEAN DEFAULT FALSE
            """)
            logger.info("[MIGRATION 008] Added is_custom column")
        else:
            logger.info("[MIGRATION 008] is_custom column already exists, skipping")

        # Add image_url for future image generation (nullable)
        if "image_url" not in existing_columns:
            cursor.execute("""
                ALTER TABLE counselor_profiles
                ADD COLUMN IF NOT EXISTS image_url TEXT
            """)
            logger.info("[MIGRATION 008] Added image_url column")
        else:
            logger.info("[MIGRATION 008] image_url column already exists, skipping")

        # Add last_image_regenerated for future cooldown tracking (nullable)
        if "last_image_regenerated" not in existing_columns:
            cursor.execute("""
                ALTER TABLE counselor_profiles
                ADD COLUMN IF NOT EXISTS last_image_regenerated TIMESTAMPTZ
            """)
            logger.info("[MIGRATION 008] Added last_image_regenerated column")
        else:
            logger.info("[MIGRATION 008] last_image_regenerated column already exists, skipping")

        # Create index for efficient filtering of client's custom advisors
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_counselor_profiles_client_custom
            ON counselor_profiles(client_id, is_custom)
        """)
        logger.info("[MIGRATION 008] Created idx_counselor_profiles_client_custom index")

        # Create performance_metrics table for tracking advisor performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                operation_type TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                metadata JSONB,
                timestamp TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        logger.info("[MIGRATION 008] Created performance_metrics table")

        conn.commit()
        logger.info("[MIGRATION 008] Custom advisors migration completed successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"[MIGRATION 008] Failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.config import settings
    upgrade(settings.database_url)
