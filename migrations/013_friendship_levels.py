"""
Database migration 013: Friendship Levels
Creates friendship_levels table for tracking user-counselor relationship depth.

Migration ID: 013
Migration Name: friendship_levels
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


def run_migration(database_url: str):
    """Apply migration 013 - friendship levels system"""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friendship_levels (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                counselor_id INTEGER NOT NULL REFERENCES counselor_profiles(id),
                level INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                last_interaction TIMESTAMPTZ,
                last_analyzed_session INTEGER REFERENCES sessions(id),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(client_id, counselor_id)
            )
        """)
        logger.info("[MIGRATION 013] Created friendship_levels table")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_friendship_client ON friendship_levels(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_friendship_counselor ON friendship_levels(counselor_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_friendship_pair ON friendship_levels(client_id, counselor_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_friendship_last_interaction ON friendship_levels(last_interaction)")
        logger.info("[MIGRATION 013] Created indexes")
        
        conn.commit()
        logger.info("[MIGRATION 013] Complete!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"[MIGRATION 013] Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("This migration should be run via the main.py migration system")
