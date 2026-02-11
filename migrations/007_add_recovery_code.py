#!/usr/bin/env python3
"""
Migration 007: Add recovery code columns to client_profiles

This adds support for account recovery via recovery codes:
- recovery_code_hash: Hashed recovery code for validation
- recovery_code_expires_at: Optional expiration (NULL = never expires)
- last_recovery_at: Track when account was last recovered

For alpha stage: codes do not expire by default
"""

import os
import sys
import sqlite3
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def migrate(db_path: str):
    """Add recovery code columns to client_profiles table with explicit db_path."""
    logger.info("[MIGRATION 007] Adding recovery code columns to client_profiles")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check which columns already exist
        cursor.execute("PRAGMA table_info(client_profiles)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add recovery_code_hash column
        if 'recovery_code_hash' not in columns:
            logger.info("[INFO] Adding recovery_code_hash column...")
            cursor.execute("""
                ALTER TABLE client_profiles
                ADD COLUMN recovery_code_hash TEXT
            """)
            logger.info("[OK] recovery_code_hash column added")
        else:
            logger.info("[SKIP] recovery_code_hash column already exists")

        # Add recovery_code_expires_at column
        if 'recovery_code_expires_at' not in columns:
            logger.info("[INFO] Adding recovery_code_expires_at column...")
            cursor.execute("""
                ALTER TABLE client_profiles
                ADD COLUMN recovery_code_expires_at TIMESTAMP
            """)
            logger.info("[OK] recovery_code_expires_at column added")
        else:
            logger.info("[SKIP] recovery_code_expires_at column already exists")

        # Add last_recovery_at column
        if 'last_recovery_at' not in columns:
            logger.info("[INFO] Adding last_recovery_at column...")
            cursor.execute("""
                ALTER TABLE client_profiles
                ADD COLUMN last_recovery_at TIMESTAMP
            """)
            logger.info("[OK] last_recovery_at column added")
        else:
            logger.info("[SKIP] last_recovery_at column already exists")

        conn.commit()
        logger.info("[OK] Migration 007 completed successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Migration 007 failed: {e}")
        raise
    finally:
        conn.close()


def generate_recovery_codes_for_existing_clients(db_path: str):
    """
    Generate recovery codes for all existing clients that don't have one.
    This is a one-time operation for the alpha migration.
    """
    import hashlib
    import base64
    import secrets
    
    logger.info("[MIGRATION 007] Generating recovery codes for existing clients...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Find clients without recovery codes
        cursor.execute("""
            SELECT id FROM client_profiles 
            WHERE recovery_code_hash IS NULL AND is_active = TRUE
        """)
        
        clients = cursor.fetchall()
        
        if not clients:
            logger.info("[OK] No existing clients need recovery codes")
            return []
        
        generated_codes = []
        
        for (client_id,) in clients:
            # Generate recovery code
            code_bytes = secrets.token_bytes(10)
            code = base64.b32encode(code_bytes).decode('ascii').upper()
            formatted_code = '-'.join([code[i:i+4] for i in range(0, 16, 4)])
            
            # Hash the code
            code_hash = hashlib.sha256(formatted_code.encode()).hexdigest()
            
            # Store hash in database
            cursor.execute("""
                UPDATE client_profiles
                SET recovery_code_hash = ?,
                    recovery_code_expires_at = NULL
                WHERE id = ?
            """, (code_hash, client_id))
            
            generated_codes.append({
                'client_id': client_id,
                'recovery_code': formatted_code
            })
        
        conn.commit()
        logger.info(f"[OK] Generated recovery codes for {len(generated_codes)} existing clients")
        
        # Log all generated codes for alpha admin reference
        logger.info("[INFO] Generated recovery codes (save these for your alpha testers):")
        for item in generated_codes:
            logger.info(f"  Client {item['client_id']}: {item['recovery_code']}")
        
        return generated_codes
        
    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Failed to generate recovery codes: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from app.core.config import settings
    
    db_path = settings.database_path or "gameapy.db"
    migrate(db_path)
    
    # Generate codes for existing clients (one-time operation)
    generate_recovery_codes_for_existing_clients(db_path)
