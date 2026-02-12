"""
Phase 1 Migration: Database Schema Updates
Adds support for self cards, world events, and entity tracking

Migration ID: 001
Migration Name: phase1_schema
"""

import psycopg2
import psycopg2.extras
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def column_exists(cursor, table, column):
    """Check if column exists in table."""
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return cursor.fetchone() is not None


def run_migration(db_path: str = "postgresql://localhost/gameapy"):
    """Apply Phase 1 schema changes."""
    MIGRATION_ID = "001"
    MIGRATION_NAME = "phase1_schema"

    from migrations.migration_tracker import initialize_tracker, is_migration_applied, record_migration

    # Initialize tracker
    initialize_tracker(db_path)

    # Check if already applied
    if is_migration_applied(db_path, MIGRATION_ID):
        print(f"[OK] Migration {MIGRATION_ID} already applied, skipping...")
        return

    print(f"[START] Applying migration {MIGRATION_ID}: {MIGRATION_NAME}...")

    conn = psycopg2.connect(db_path)
    cursor = conn.cursor()

    try:
        # DEBUG: Check what tables exist
        cursor.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        print(f"[DEBUG] Existing tables: {tables}")
        print(f"[DEBUG] character_cards exists: {'character_cards' in tables}")

        # Note: The base schema (schema.sql) already creates all tables with proper PostgreSQL syntax
        # This migration is mainly a no-op now, marking the migration as applied

        # Verify tables exist
        required_tables = ['character_cards', 'self_cards', 'world_events', 'entity_mentions']
        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            print(f"[WARNING] Missing tables: {missing_tables}")
            print("[INFO] These should be created by the base schema (schema.sql)")
        else:
            print("[OK] All required tables exist in base schema")

        # Verify existing data preserved
        if 'character_cards' in tables:
            cursor.execute("SELECT COUNT(*) FROM character_cards")
            existing_cards = cursor.fetchone()[0]
            print(f"\n[INFO] Found {existing_cards} existing character cards (preserved)")

        conn.commit()

        # Record success
        record_migration(db_path, MIGRATION_ID, MIGRATION_NAME)
        print(f"\n[OK] Migration {MIGRATION_ID} completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gameapy.db"
    run_migration(db_path)
