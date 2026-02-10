#!/usr/bin/env python3
"""
Migration 005: Add is_hidden flag to counselor_profiles

This adds a flag to mark counselors as hidden (e.g., Easter egg characters
that can only be summoned, not selected directly).
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Database


def migrate():
    """Add is_hidden column to counselor_profiles table."""

    print("[MIGRATION 005] Adding is_hidden column to counselor_profiles")

    db = Database()
    db_path = db.db_path

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(counselor_profiles)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'is_hidden' in columns:
            print("[OK] Column is_hidden already exists")
            return

        # Add is_hidden column
        print("[INFO] Adding is_hidden column...")
        cursor.execute("""
            ALTER TABLE counselor_profiles
            ADD COLUMN is_hidden BOOLEAN DEFAULT FALSE
        """)

        # Mark Deirdre as hidden (Easter egg)
        print("[INFO] Marking Deirdre as hidden (Easter egg)...")
        cursor.execute("""
            UPDATE counselor_profiles
            SET is_hidden = TRUE
            WHERE LOWER(name) = 'deirdre'
        """)

        conn.commit()
        print("[OK] Migration completed successfully")
        print("[INFO] Deirdre is now hidden from counselor selection")
        print("[INFO] Deirdre can still be summoned with 'Summon Deirdre' phrase")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
