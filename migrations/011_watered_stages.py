"""
Database migration 011: Watered Stages
Replaces is_watered boolean with watered_stages JSON array
to support watering per growth phase (30% speed bonus per watered stage)

Migration ID: 011
Migration Name: watered_stages
"""

import psycopg2
import logging
import json

logger = logging.getLogger(__name__)


def run_migration(database_url: str):
    """Apply migration 011"""
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    try:
        # Add watered_stages column to planted_crops
        try:
            # First, check if is_watered exists and has data
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'planted_crops' AND column_name = 'is_watered'
            """)
            has_is_watered = cursor.fetchone() is not None
            
            if has_is_watered:
                # Convert existing is_watered=True to watered_stages=[0]
                # (first stage watered)
                cursor.execute("""
                    UPDATE planted_crops 
                    SET watered_stages = '[0]'::jsonb
                    WHERE is_watered = TRUE
                """)
                logger.info("[MIGRATION 011] Migrated existing is_watered data to watered_stages")
                
                # Drop the old column
                cursor.execute("""
                    ALTER TABLE planted_crops DROP COLUMN IF EXISTS is_watered
                """)
                logger.info("[MIGRATION 011] Dropped is_watered column")
            
            # Add watered_stages column if it doesn't exist
            cursor.execute("""
                ALTER TABLE planted_crops ADD COLUMN IF NOT EXISTS watered_stages JSONB DEFAULT '[]'::jsonb
            """)
            logger.info("[MIGRATION 011] Added watered_stages column to planted_crops")
            
        except Exception as e:
            logger.info(f"[MIGRATION 011] Error with watered_stages: {e}")
        
        conn.commit()
        logger.info("[MIGRATION 011] Complete!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"[MIGRATION 011] Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("This migration should be run via the main.py migration system")
