"""
Database migration 012: Farm Consolidated
Creates all farm tables in one migration with correct schema:
- planted_crops (with watered_stages JSONB, growth_stage INTEGER)
- farm_plots (tilled plots)
- farm_animals
- farm_decorations

Migration ID: 012
Migration Name: farm_consolidated
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


def run_migration(database_url: str):
    """Apply migration 012 - consolidated farm schema"""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        # Add columns to game_state if they don't exist
        try:
            cursor.execute("""
                ALTER TABLE game_state ADD COLUMN IF NOT EXISTS message_counter INTEGER DEFAULT 0
            """)
            logger.info("[MIGRATION 012] Added message_counter column to game_state")
        except Exception as e:
            logger.info(f"[MIGRATION 012] message_counter column: {e}")
        
        try:
            cursor.execute("""
                ALTER TABLE game_state ADD COLUMN IF NOT EXISTS last_login_date DATE
            """)
            logger.info("[MIGRATION 012] Added last_login_date column to game_state")
        except Exception as e:
            logger.info(f"[MIGRATION 012] last_login_date column: {e}")
        
        # Drop existing farm tables if they exist (fresh start - no user data)
        cursor.execute("DROP TABLE IF EXISTS farm_decorations CASCADE")
        cursor.execute("DROP TABLE IF EXISTS farm_animals CASCADE")
        cursor.execute("DROP TABLE IF EXISTS planted_crops CASCADE")
        cursor.execute("DROP TABLE IF EXISTS farm_plots CASCADE")
        logger.info("[MIGRATION 012] Dropped existing farm tables")
        
        # Create planted_crops table with correct schema
        cursor.execute("""
            CREATE TABLE planted_crops (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                crop_type TEXT NOT NULL,
                plot_index INTEGER NOT NULL,
                planted_at_message INTEGER NOT NULL,
                growth_duration INTEGER NOT NULL,
                is_harvested BOOLEAN DEFAULT FALSE,
                watered_stages JSONB DEFAULT '[]'::jsonb,
                growth_stage INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(client_id, plot_index, is_harvested)
            )
        """)
        logger.info("[MIGRATION 012] Created planted_crops table")
        
        # Create farm_plots table (for tilled but unplanted plots)
        cursor.execute("""
            CREATE TABLE farm_plots (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                plot_index INTEGER NOT NULL,
                state TEXT DEFAULT 'tilled',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(client_id, plot_index)
            )
        """)
        logger.info("[MIGRATION 012] Created farm_plots table")
        
        # Create farm_animals table
        cursor.execute("""
            CREATE TABLE farm_animals (
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
        logger.info("[MIGRATION 012] Created farm_animals table")
        
        # Create farm_decorations table
        cursor.execute("""
            CREATE TABLE farm_decorations (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                decoration_type TEXT NOT NULL,
                x_position INTEGER NOT NULL,
                y_position INTEGER NOT NULL,
                variant INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        logger.info("[MIGRATION 012] Created farm_decorations table")
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_planted_crops_client ON planted_crops(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_plots_client ON farm_plots(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_animals_client ON farm_animals(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_decorations_client ON farm_decorations(client_id)")
        logger.info("[MIGRATION 012] Created indexes")
        
        conn.commit()
        logger.info("[MIGRATION 012] Complete!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"[MIGRATION 012] Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("This migration should be run via the main.py migration system")
