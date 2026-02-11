"""
Phase 1 Migration: Database Schema Updates
Adds support for self cards, world events, and entity tracking

Migration ID: 001
Migration Name: phase1_schema
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def column_exists(cursor, table, column):
    """Check if column exists in table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run_migration(db_path: str = "gameapy.db"):
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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # DEBUG: Check what tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"[DEBUG] Existing tables: {tables}")
        print(f"[DEBUG] character_cards exists: {'character_cards' in tables}")
        
        # Task 1: Extend character_cards
        print("\n--- Extending character_cards table ---")

        # Check for auto_update_enabled first (may already exist)
        if column_exists(cursor, 'character_cards', 'auto_update_enabled'):
            print("[SKIP] auto_update_enabled already exists in character_cards, skipping...")
        else:
            cursor.execute("ALTER TABLE character_cards ADD COLUMN auto_update_enabled BOOLEAN DEFAULT TRUE")
            print("[OK] Added auto_update_enabled to character_cards")

        # Add other new columns
        # Note: entity_id added without UNIQUE constraint (can't add UNIQUE to non-empty table)
        # The unique index will be created separately
        new_columns = [
            ("entity_id", "TEXT"),
            ("mention_count", "INTEGER DEFAULT 0"),
            ("last_mentioned", "TIMESTAMP"),
            ("first_mentioned", "TIMESTAMP"),
            ("vector_embedding", "BLOB")
        ]

        for col_name, col_type in new_columns:
            if column_exists(cursor, 'character_cards', col_name):
                print(f"[SKIP] {col_name} already exists in character_cards, skipping...")
            else:
                cursor.execute(f"ALTER TABLE character_cards ADD COLUMN {col_name} {col_type}")
                print(f"[OK] Added {col_name} to character_cards")

        # Indexes for character_cards
        print("\nCreating indexes for character_cards...")
        # Create unique index separately (can't add UNIQUE column to non-empty table)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_character_cards_entity ON character_cards(entity_id)")
        print("[OK] Created idx_character_cards_entity (unique)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_character_cards_auto_update ON character_cards(auto_update_enabled)")
        print("[OK] Created idx_character_cards_auto_update")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_character_cards_mentions ON character_cards(mention_count DESC)")
        print("[OK] Created idx_character_cards_mentions")

        # Task 2: Create self_cards
        print("\n--- Creating self_cards table ---")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS self_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL UNIQUE,
                card_json TEXT NOT NULL,
                auto_update_enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES client_profiles(id)
            )
        """)
        print("[OK] Created self_cards table")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_self_cards_client ON self_cards(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_self_cards_auto_update ON self_cards(auto_update_enabled)")
        print("[OK] Created indexes for self_cards")

        # Task 3: Create world_events
        print("\n--- Creating world_events table ---")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS world_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                entity_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                key_array TEXT NOT NULL,
                description TEXT NOT NULL,
                event_type TEXT NOT NULL,
                is_canon_law BOOLEAN DEFAULT FALSE,
                auto_update_enabled BOOLEAN DEFAULT TRUE,
                resolved BOOLEAN DEFAULT FALSE,
                vector_embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES client_profiles(id)
            )
        """)
        print("[OK] Created world_events table")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_world_events_client ON world_events(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_world_events_canon ON world_events(is_canon_law)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_world_events_entity ON world_events(entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_world_events_auto_update ON world_events(auto_update_enabled)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_world_events_type ON world_events(event_type)")
        print("[OK] Created indexes for world_events")

        # Task 4: Create entity_mentions
        print("\n--- Creating entity_mentions table ---")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_ref TEXT NOT NULL,
                mention_context TEXT NOT NULL,
                vector_embedding BLOB,
                mentioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES client_profiles(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        print("[OK] Created entity_mentions table")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_client ON entity_mentions(client_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_session ON entity_mentions(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_type ON entity_mentions(entity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_ref ON entity_mentions(entity_ref)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_time ON entity_mentions(mentioned_at DESC)")
        print("[OK] Created indexes for entity_mentions")

        # Task 5: Add change_log index
        print("\n--- Adding change_log index ---")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_change_log_entity_time ON change_log(entity_type, entity_id, changed_at DESC)")
        print("[OK] Created idx_change_log_entity_time")

        # Verify existing data preserved
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
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gameapy.db"
    run_migration(db_path)
