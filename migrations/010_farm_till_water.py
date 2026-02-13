"""
Database migration 010: Farm Till and Water
Adds farm_plots table, is_watered and growth_stage columns to planted_crops

Migration ID: 010
Migration Name: farm_till_water
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


def run_migration(database_url: str):
    """Apply migration 010"""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        # Create farm_plots table (for tilled but unplanted plots)
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS farm_plots (
                    id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
                    plot_index INTEGER NOT NULL,
                    state TEXT DEFAULT 'tilled',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(client_id, plot_index)
                )
            """)
            logger.info("[MIGRATION 010] Created farm_plots table")
        except Exception as e:
            logger.info(f"[MIGRATION 010] farm_plots table may already exist: {e}")
        
        # Add is_watered column to planted_crops
        try:
            cursor.execute("""
                ALTER TABLE planted_crops ADD COLUMN IF NOT EXISTS is_watered BOOLEAN DEFAULT FALSE
            """)
            logger.info("[MIGRATION 010] Added is_watered column to planted_crops")
        except Exception as e:
            logger.info(f"[MIGRATION 010] is_watered column may already exist: {e}")
        
        # Add growth_stage column to planted_crops
        try:
            cursor.execute("""
                ALTER TABLE planted_crops ADD COLUMN IF NOT EXISTS growth_stage INTEGER DEFAULT 0
            """)
            logger.info("[MIGRATION 010] Added growth_stage column to planted_crops")
        except Exception as e:
            logger.info(f"[MIGRATION 010] growth_stage column may already exist: {e}")
        
        # Create index on farm_plots
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_plots_client ON farm_plots(client_id)")
            logger.info("[MIGRATION 010] Created farm_plots index")
        except Exception as e:
            logger.info(f"[MIGRATION 010] Index may already exist: {e}")
        
        conn.commit()
        logger.info("[MIGRATION 010] Complete!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"[MIGRATION 010] Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("This migration should be run via the main.py migration system")
