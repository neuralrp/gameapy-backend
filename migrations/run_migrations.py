#!/usr/bin/env python3
"""
Unified migration runner for Gameapy.
Runs all pending migrations in order on startup.
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import Database
from migrations.migration_tracker import initialize_tracker, is_migration_applied, record_migration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


MIGRATIONS = [
    {
        "id": "001",
        "name": "phase1_schema",
        "module": "migrations.001_phase1_schema",
        "function": "run_migration"
    },
    {
        "id": "004",
        "name": "pivot_cleanup",
        "module": "migrations.004_pivot_cleanup",
        "function": "apply"
    },
    {
        "id": "005",
        "name": "add_hidden_flag",
        "module": "migrations.005_add_hidden_flag",
        "function": "migrate"
    },
    {
        "id": "006",
        "name": "add_relationship_label",
        "module": "migrations.006_add_relationship_label",
        "function": "migrate"
    }
]


def run_migration(db_path: str, migration_id: str, migration_name: str, module_path: str, function_name: str):
    """Run a single migration."""
    logger.info(f"[MIGRATION {migration_id}] Starting: {migration_name}")
    
    try:
        # Import the migration module
        module = __import__(module_path, fromlist=[function_name])
        migration_func = getattr(module, function_name)
        
        # Run the migration
        migration_func()
        
        # Record successful migration (some migrations may have already recorded themselves)
        try:
            record_migration(db_path, migration_id, migration_name)
        except sqlite3.IntegrityError:
            # Migration already recorded, ignore
            logger.debug(f"[MIGRATION {migration_id}] Already recorded in migration history")
        
        logger.info(f"[MIGRATION {migration_id}] Completed successfully")
        
    except Exception as e:
        logger.error(f"[MIGRATION {migration_id}] Failed: {e}")
        raise


def run_all_migrations():
    """Run all pending migrations in order."""
    logger.info("=" * 60)
    logger.info("Starting automatic migration runner")
    logger.info("=" * 60)
    
    # Get database path
    db = Database()
    db_path = db.db_path
    logger.info(f"Database path: {db_path}")
    
    # Initialize migration tracker
    initialize_tracker(db_path)
    logger.info("Migration tracker initialized")
    
    # Run each migration if not already applied
    pending_migrations = []
    completed_migrations = []
    
    for migration in MIGRATIONS:
        migration_id = migration["id"]
        migration_name = migration["name"]
        
        if is_migration_applied(db_path, migration_id):
            logger.info(f"[SKIP] Migration {migration_id} ({migration_name}) already applied")
            completed_migrations.append(migration_id)
        else:
            logger.info(f"[PENDING] Migration {migration_id} ({migration_name}) needs to be applied")
            pending_migrations.append(migration)
    
    # Run pending migrations
    if not pending_migrations:
        logger.info("=" * 60)
        logger.info("All migrations are up to date!")
        logger.info(f"Applied: {', '.join(completed_migrations)}")
        logger.info("=" * 60)
        return
    
    logger.info(f"Found {len(pending_migrations)} pending migration(s)")
    logger.info("-" * 60)
    
    for migration in pending_migrations:
        run_migration(
            db_path,
            migration["id"],
            migration["name"],
            migration["module"],
            migration["function"]
        )
        logger.info("-" * 60)
    
    logger.info("=" * 60)
    logger.info("All migrations completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_all_migrations()
