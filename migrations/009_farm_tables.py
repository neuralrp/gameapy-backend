"""
Database migration 009: Farm Tables
Adds message_counter, planted_crops, farm_animals, and farm_decorations tables

Migration ID: 009
Migration Name: farm_tables
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


def run_migration(database_url: str):
    """Apply migration 009"""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        # Add columns to game_state if they don't exist
        try:
            cursor.execute("""
                ALTER TABLE game_state ADD COLUMN IF NOT EXISTS message_counter INTEGER DEFAULT 0
            """)
            logger.info("[MIGRATION 009] Added message_counter column to game_state")
        except Exception as e:
            logger.info(f"[MIGRATION 009] message_counter column may already exist: {e}")
        
        try:
            cursor.execute("""
                ALTER TABLE game_state ADD COLUMN IF NOT EXISTS last_login_date DATE
            """)
            logger.info("[MIGRATION 009] Added last_login_date column to game_state")
        except Exception as e:
            logger.info(f"[MIGRATION 009] last_login_date column may already exist: {e}")
        
        # Create planted_crops table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS planted_crops (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                    crop_type TEXT NOT NULL,
                    plot_index INTEGER NOT NULL,
                    planted_at_message INTEGER NOT NULL,
                    growth_duration INTEGER NOT NULL,
                    is_harvested BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            logger.info("[MIGRATION 009] Created planted_crops table")
        except Exception as e:
            logger.info(f"[MIGRATION 009] planted_crops table may already exist: {e}")
        
        # Create farm_animals table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS farm_animals (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                    animal_type TEXT NOT NULL,
                    slot_index INTEGER NOT NULL,
                    acquired_at_message INTEGER NOT NULL,
                    maturity_duration INTEGER NOT NULL,
                    is_mature BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            logger.info("[MIGRATION 009] Created farm_animals table")
        except Exception as e:
            logger.info(f"[MIGRATION 009] farm_animals table may already exist: {e}")
        
        # Create farm_decorations table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS farm_decorations (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                    decoration_type TEXT NOT NULL,
                    x_position INTEGER NOT NULL,
                    y_position INTEGER NOT NULL,
                    variant INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            logger.info("[MIGRATION 009] Created farm_decorations table")
        except Exception as e:
            logger.info(f"[MIGRATION 009] farm_decorations table may already exist: {e}")
        
        # Create indexes
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_planted_crops_client ON planted_crops(client_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_animals_client ON farm_animals(client_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_decorations_client ON farm_decorations(client_id)")
            logger.info("[MIGRATION 009] Created indexes")
        except Exception as e:
            logger.info(f"[MIGRATION 009] Indexes may already exist: {e}")
        
        conn.commit()
        logger.info("[MIGRATION 009] Complete!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"[MIGRATION 009] Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("This migration should be run via the main.py migration system")
