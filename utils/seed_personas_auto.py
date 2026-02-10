#!/usr/bin/env python3
"""
Auto-seed Personas on Startup

This module provides automatic persona seeding for Gameapy on startup.
It checks if any counselors exist in the database, and if none are found,
it runs the seed_personas script to import all personas from JSON files.

Environment Variables:
    AUTO_SEED_PERSONAS: Enable/disable auto-seeding (default: "true")

Usage:
    from utils.seed_personas_auto import ensure_personas_sealed
    ensure_personas_sealed()
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)


def is_auto_seed_enabled():
    """Check if auto-seeding is enabled via environment variable."""
    return os.getenv("AUTO_SEED_PERSONAS", "true").lower() in ("true", "1", "yes", "on")


def has_counselors(db):
    """Check if any counselors exist in the database."""
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            result = cursor.execute(
                "SELECT COUNT(*) FROM counselor_profiles WHERE is_active = TRUE"
            ).fetchone()
            return result[0] > 0
    except Exception as e:
        logger.error(f"Error checking for existing counselors: {e}")
        return False


def ensure_personas_sealed(db_path: str = None):
    """
    Ensure personas are seeded in the database.
    
    This function checks if auto-seeding is enabled and if any counselors
    exist. If no counselors are found and auto-seeding is enabled, it runs
    the seed_personas script to import all personas from JSON files.
    
    Args:
        db_path: Optional database path. If not provided, uses default "gameapy.db"
    """
    if not is_auto_seed_enabled():
        logger.info("[AUTO-SEED] Auto-seeding disabled via AUTO_SEED_PERSONAS")
        return
    
    # Import Database after ensuring we're in the right path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.db.database import Database
    
    db = Database(db_path) if db_path else Database()
    
    # Check if counselors already exist
    if has_counselors(db):
        logger.info("[AUTO-SEED] Counselors already exist, skipping seed")
        return
    
    logger.info("[AUTO-SEED] No counselors found, starting seed process...")
    
    try:
        # Import seed_personas module
        from scripts.seed_personas import load_persona_files, seed_personas
        
        # Load all persona files
        personas = load_persona_files(name_filter=None)
        
        if not personas:
            logger.warning("[AUTO-SEED] No persona files found in data/personas/")
            return
        
        # Seed to database
        summary = seed_personas(db, personas)
        
        # Log summary
        if summary['created']:
            logger.info(f"[AUTO-SEED] Created {len(summary['created'])} persona(s): {', '.join(summary['created'])}")
        
        if summary['updated']:
            logger.info(f"[AUTO-SEED] Updated {len(summary['updated'])} persona(s): {', '.join(summary['updated'])}")
        
        if summary['failed']:
            logger.error(f"[AUTO-SEED] Failed to seed {len(summary['failed'])} persona(s)")
            for failure in summary['failed']:
                logger.error(f"  - {failure['name']}: {failure['error']}")
        
        if not summary['failed']:
            logger.info("[AUTO-SEED] All personas seeded successfully")
        
    except Exception as e:
        logger.error(f"[AUTO-SEED] Failed to seed personas: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - we don't want to prevent the server from starting


if __name__ == "__main__":
    # Allow running this module directly for testing
    logging.basicConfig(level=logging.INFO)
    ensure_personas_sealed()
