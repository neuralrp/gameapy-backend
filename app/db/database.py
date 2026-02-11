import sqlite3
import json
import uuid
import os
from contextlib import contextmanager
from typing import List, Dict, Optional, Any
from datetime import datetime


class Database:
    """Thread-safe database operations with connection pooling."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from app.core.config import settings
            db_path = settings.database_path or "gameapy.db"
        
        self.db_path = db_path
        self.vector_support = False
        
        # Log database location for debugging
        print(f"[INFO] Database path: {db_path}")
        
        # Ensure database directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"[INFO] Created database directory: {db_dir}")

        # Keyword-only search (no vector embeddings - pivot v3.1 design decision)
        self.vector_support = False
        print("[OK] Keyword-only search enabled (fast, simple matching)")

        self._ensure_schema()
        self._run_auto_migrations()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self):
        """Ensure all tables exist."""
        with self._get_connection() as conn:
            # Read schema from separate file
            import os
            schema_path = os.path.join(os.path.dirname(__file__), '..', '..', 'schema.sql')
            with open(schema_path, 'r') as f:
                schema = f.read()
            
            # Remove SQL comments that start with #
            lines = [line for line in schema.split('\n') if not line.strip().startswith('#')]
            clean_schema = '\n'.join(lines)
            
            conn.executescript(clean_schema)
    
    def _run_auto_migrations(self):
        """Run automatic migrations on startup."""
        try:
            # Import and run migration
            import os
            import sys
            import subprocess
            migration_path = os.path.join(os.path.dirname(__file__), '..', '..', 'migrations', '004_pivot_cleanup.py')
            if os.path.exists(migration_path):
                try:
                    subprocess.run([sys.executable, migration_path], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    print(f"[WARN] Migration failed: {e}")
                except Exception as e:
                    print(f"[WARN] Could not run migration: {e}")
        except Exception as e:
            print(f"[WARN] Failed to run auto-migration: {e}")
            # Continue startup even if migration fails

    # Client Profile Operations
    def create_client_profile(self, profile_data: Dict[str, Any]) -> int:
        """Create a new client profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            entity_id = f"client_{uuid.uuid4().hex}"

            cursor.execute("""
                INSERT INTO client_profiles (entity_id, name, profile_json, tags)
                VALUES (?, ?, ?, ?)
            """, (
                entity_id,
                profile_data['data']['name'],
                json.dumps(profile_data),
                json.dumps(profile_data['data'].get('tags', []))
            ))

            profile_id = cursor.lastrowid
            if profile_id is None:
                raise Exception("Failed to create client profile")

            # Initialize game state for new client
            cursor.execute("""
                INSERT INTO game_state (client_id, gold_coins, farm_level)
                VALUES (?, ?, ?)
            """, (profile_id, 0, 1))

            # Log creation
            self._log_change(conn, 'client_profile', profile_id, 'created', None, profile_data)

            return profile_id

    def get_client_profile(self, profile_id: int) -> Optional[Dict]:
        """Get client profile by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, entity_id, name, profile_json, tags, created_at, updated_at
                FROM client_profiles
                WHERE id = ? AND is_active = TRUE AND deleted_at IS NULL
            """, (profile_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row[0],
                'entity_id': row[1],
                'name': row[2],
                'profile': json.loads(row[3]),
                'tags': json.loads(row[4]),
                'created_at': row[5],
                'updated_at': row[6]
            }

    # Counselor Profile Operations
    def create_counselor_profile(self, profile_data: Dict[str, Any]) -> int:
        """Create a new counselor profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            entity_id = f"counselor_{uuid.uuid4().hex}"

            # Map JSON fields to DB columns
            # credentials column now stores your_worldview
            # is_hidden is an optional field for Easter egg counselors
            cursor.execute("""
                INSERT INTO counselor_profiles (entity_id, name, specialization, therapeutic_style, credentials, profile_json, tags, is_hidden)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity_id,
                profile_data['data']['name'],
                profile_data['data'].get('who_you_are', ''),  # specialization column
                profile_data['data'].get('your_vibe', ''),  # therapeutic_style column
                profile_data['data'].get('your_worldview', ''),  # credentials column now stores worldview
                json.dumps(profile_data),
                json.dumps(profile_data['data'].get('tags', [])),
                profile_data['data'].get('is_hidden', False)  # is_hidden field (optional, default False)
            ))

            profile_id = cursor.lastrowid
            if profile_id is None:
                raise Exception("Failed to create counselor profile")

            # Log creation
            self._log_change(conn, 'counselor_profile', profile_id, 'created', None, profile_data)


            return profile_id

    def get_counselor_profile(self, profile_id: int) -> Optional[Dict]:
        """Get counselor profile by ID (includes hidden counselors)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, entity_id, name, specialization, therapeutic_style, credentials, profile_json, tags, created_at, updated_at
                FROM counselor_profiles
                WHERE id = ? AND is_active = TRUE AND deleted_at IS NULL
            """, (profile_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row[0],
                'entity_id': row[1],
                'name': row[2],
                'specialization': row[3],
                'therapeutic_style': row[4],
                'credentials': row[5],
                'profile': json.loads(row[6]),
                'tags': json.loads(row[7]),
                'created_at': row[8],
                'updated_at': row[9]
            }

    def get_all_counselors(self) -> List[Dict]:
        """Get all active counselor profiles (excluding hidden counselors)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, entity_id, name, specialization, therapeutic_style, credentials, profile_json, tags, created_at, updated_at
                FROM counselor_profiles
                WHERE is_active = TRUE AND deleted_at IS NULL AND is_hidden = FALSE
                ORDER BY name
            """)

            return [
                {
                    'id': row[0],
                    'entity_id': row[1],
                    'name': row[2],
                    'specialization': row[3],
                    'therapeutic_style': row[4],
                    'credentials': row[5],
                    'profile': json.loads(row[6]),
                    'tags': json.loads(row[7]),
                    'created_at': row[8],
                    'updated_at': row[9]
                }
                for row in cursor.fetchall()
            ]

    def get_counselor_by_name(self, name: str) -> Optional[Dict]:
        """Get counselor profile by name (case-insensitive)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, entity_id, name, specialization, therapeutic_style, credentials, profile_json, tags, created_at, updated_at
                FROM counselor_profiles
                WHERE LOWER(name) = LOWER(?) AND is_active = TRUE AND deleted_at IS NULL
            """, (name,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row[0],
                'entity_id': row[1],
                'name': row[2],
                'specialization': row[3],
                'therapeutic_style': row[4],
                'credentials': row[5],
                'profile': json.loads(row[6]),
                'tags': json.loads(row[7]),
                'created_at': row[8],
                'updated_at': row[9]
            }

    # Session Operations
    def create_session(self, client_id: int, counselor_id: int) -> int:
        """Create a new counseling session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get session number for this client-counselor pair
            cursor.execute("""
                SELECT COALESCE(MAX(session_number), 0) + 1
                FROM sessions
                WHERE client_id = ? AND counselor_id = ?
            """, (client_id, counselor_id))
            session_number = cursor.fetchone()[0]

            # Create session
            cursor.execute("""
                INSERT INTO sessions (client_id, counselor_id, session_number)
                VALUES (?, ?, ?)
            """, (client_id, counselor_id, session_number))

            session_id = cursor.lastrowid
            if session_id is None:
                raise Exception("Failed to create session")
            return session_id

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        speaker: Optional[str] = None
    ) -> int:
        """Add a message to a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, speaker)
                VALUES (?, ?, ?, ?)
            """, (session_id, role, content, speaker))
            message_id = cursor.lastrowid
            if message_id is None:
                raise Exception("Failed to add message")
            return message_id

    def get_session_messages(
        self,
        session_id: int,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get messages from a session (most recent first, reversed for chronological order)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = """
                SELECT id, role, content, speaker, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
            """
            if limit:
                sql += f" LIMIT {limit}"

            cursor.execute(sql, (session_id,))
            rows = cursor.fetchall()
            # Reverse to return in chronological order (oldest first)
            return [dict(row) for row in reversed(rows)]

    # Character Card Operations
    def create_character_card(
        self,
        client_id: int,
        card_name: str,
        relationship_type: str,
        card_data: Dict[str, Any],
        relationship_label: Optional[str] = None
    ) -> int:
        """Create a new character card."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO character_cards (client_id, card_name, relationship_type, relationship_label, card_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                client_id,
                card_name,
                relationship_type,
                relationship_label,
                json.dumps(card_data)
            ))

            card_id = cursor.lastrowid
            if card_id is None:
                raise Exception("Failed to create character card")

            # Log creation
            self._log_change(conn, 'character_card', card_id, 'created', None, card_data)

            return card_id

    def get_character_cards(self, client_id: int) -> List[Dict]:
        """Get all character cards for a client."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, card_name, relationship_type, relationship_label, card_json, auto_update_enabled, last_updated, created_at, is_pinned
                FROM character_cards
                WHERE client_id = ?
                ORDER BY card_name
            """, (client_id,))

            return [
                {
                    'id': row[0],
                    'card_name': row[1],
                    'relationship_type': row[2],
                    'relationship_label': row[3],
                    'card': json.loads(row[4]),
                    'auto_update_enabled': row[5],
                    'last_updated': row[6],
                    'created_at': row[7],
                    'is_pinned': row[8]
                }
                for row in cursor.fetchall()
            ]

    def get_character_card_by_id(self, card_id: int) -> Optional[Dict]:
        """Get a character card by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, card_name, relationship_type, relationship_label, card_json, auto_update_enabled, last_updated, created_at, is_pinned
                FROM character_cards
                WHERE id = ?
            """, (card_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'card_name': row[1],
                    'relationship_type': row[2],
                    'relationship_label': row[3],
                    'card_json': row[4],
                    'card': json.loads(row[4]),
                    'auto_update_enabled': row[5],
                    'last_updated': row[6],
                    'created_at': row[7],
                    'is_pinned': row[8]
                }
            return None

    def update_character_card(self, card_id: int, **kwargs) -> bool:
        """
        Update a character card with partial field updates.

        Allowed fields: card_name, relationship_type, relationship_label, card_json
        """
        allowed_fields = ['card_name', 'relationship_type', 'relationship_label', 'card_json', 'changed_by']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields and k != 'changed_by'}
        changed_by = kwargs.get('changed_by', 'system')

        if not updates:
            return False

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [card_id]

        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                UPDATE character_cards
                SET {set_clause}, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, values)

            if cursor.rowcount > 0:
                self._log_change(conn, 'character_card', card_id, 'updated', None, updates, changed_by)

            return cursor.rowcount > 0

    # Game State Operations
    def get_game_state(self, client_id: int) -> Optional[Dict]:
        """Get game state for a client."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, client_id, gold_coins, farm_level, last_coin_award, created_at, updated_at
                FROM game_state
                WHERE client_id = ?
            """, (client_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row[0],
                'client_id': row[1],
                'gold_coins': row[2],
                'farm_level': row[3],
                'last_coin_award': row[4],
                'created_at': row[5],
                'updated_at': row[6]
            }

    def update_gold_coins(self, client_id: int, coins_earned: int, reason: str = "session_completion") -> bool:
        """Update gold coins for a client."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE game_state
                SET gold_coins = gold_coins + ?,
                    last_coin_award = ?,
                    updated_at = ?
                WHERE client_id = ?
            """, (
                coins_earned,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                client_id
            ))

            # Get current state
            cursor.execute("SELECT gold_coins FROM game_state WHERE client_id = ?", (client_id,))
            new_total = cursor.fetchone()[0]

            # Log change
            self._log_change(
                conn,
                'game_state',
                client_id,
                'gold_coins_added',
                {'gold_coins': new_total - coins_earned},
                {'gold_coins': new_total, 'reason': reason}
            )

            return cursor.rowcount > 0

    def get_farm_items(self, client_id: int) -> List[Dict]:
        """Get all farm items for a client."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, item_type, item_name, item_metadata, created_at, updated_at
                FROM farm_items
                WHERE client_id = ?
                ORDER BY created_at DESC
            """, (client_id,))

            return [
                {
                    'id': row[0],
                    'item_type': row[1],
                    'item_name': row[2],
                    'metadata': json.loads(row[3]) if row[3] else {},
                    'created_at': row[4],
                    'updated_at': row[5]
                }
                for row in cursor.fetchall()
            ]

    def add_farm_item(
        self,
        client_id: int,
        item_type: str,
        item_name: str,
        item_metadata: Optional[Dict] = None
    ) -> int:
        """Add a new farm item."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO farm_items (client_id, item_type, item_name, item_metadata)
                VALUES (?, ?, ?, ?)
            """, (
                client_id,
                item_type,
                item_name,
                json.dumps(item_metadata) if item_metadata else None
            ))

            item_id = cursor.lastrowid
            if item_id is None:
                raise Exception("Failed to add farm item")
            
            # Deduct gold coins if applicable
            if item_type in ['egg', 'seed']:
                self.update_gold_coins(client_id, -10, f"purchased_{item_type}")
            elif item_type == 'hay':
                self.update_gold_coins(client_id, -10, "purchased_hay")
            elif 'hatch' in item_name.lower():
                self.update_gold_coins(client_id, -20, f"hatched_{item_type}")

            return item_id

    # Change Log Operations
    def _log_change(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: Optional[Any],
        new_value: Optional[Any],
        changed_by: str = 'system'
    ):
        """Log a change to the change log table."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO change_log (entity_type, entity_id, action, old_value, new_value, changed_by, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entity_type, entity_id, action,
            json.dumps(old_value) if old_value else None,
            json.dumps(new_value) if new_value else None,
            changed_by,
            datetime.now().isoformat()
        ))

    def get_change_history(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 50
    ) -> List[Dict]:
        """Get change history for an entity."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT action, old_value, new_value, changed_by, changed_at, metadata
                FROM change_log
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY changed_at DESC
                LIMIT ?
            """, (entity_type, entity_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_user_edit(
        self,
        entity_type: str,
        entity_id: int,
        since_timestamp: Optional[datetime] = None
    ) -> Optional[Dict]:
        """Check if user has edited this entity since given timestamp."""
        with self._get_connection() as conn:
            query = """
                SELECT * FROM change_log
                WHERE entity_type = ? AND entity_id = ? AND changed_by = 'user'
            """
            params = [entity_type, entity_id]
            
            if since_timestamp:
                query += " AND changed_at > ?"
                params.append(since_timestamp.isoformat())
            
            query += " ORDER BY changed_at DESC LIMIT 1"
            
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_last_ai_update(
        self,
        card_type: str,
        card_id: int
    ) -> Optional[datetime]:
        """Get timestamp of last AI update for a card."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT changed_at FROM change_log
                WHERE entity_type = ? AND entity_id = ? AND changed_by = 'system'
                ORDER BY changed_at DESC LIMIT 1
            """, (f"{card_type}_card", card_id))
            row = cursor.fetchone()
            if row:
                return datetime.fromisoformat(row[0])
            return None

    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get session by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, client_id, counselor_id, session_number,
                       started_at, ended_at, metadata
                FROM sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_session_counselor(self, session_id: int, new_counselor_id: int) -> bool:
        """Update the counselor for a session."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE sessions
                SET counselor_id = ?
                WHERE id = ?
            """, (new_counselor_id, session_id))
            return cursor.rowcount > 0

    # ============================================================
    # Pin/Unpin Methods
    # ============================================================
    
    def pin_card(self, card_type: str, card_id: int) -> bool:
        """Pin a card to always load in context."""
        table_map = {
            'self': 'self_cards',
            'character': 'character_cards',
            'world': 'world_events'
        }
        table = table_map.get(card_type)
        if not table:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {table} SET is_pinned = TRUE WHERE id = ?",
                (card_id,)
            )
            return cursor.rowcount > 0
    
    def unpin_card(self, card_type: str, card_id: int) -> bool:
        """Unpin a card."""
        table_map = {
            'self': 'self_cards',
            'character': 'character_cards',
            'world': 'world_events'
        }
        table = table_map.get(card_type)
        if not table:
            return False
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE {table} SET is_pinned = FALSE WHERE id = ?",
                (card_id,)
            )
            return cursor.rowcount > 0
    
    def get_pinned_cards(self, client_id: int) -> List[Dict]:
        """Get all pinned cards for a client (unified format)."""
        pinned = []
        
        with self._get_connection() as conn:
            # Self cards
            cursor = conn.execute("""
                SELECT id, card_json, auto_update_enabled, created_at, last_updated 
                FROM self_cards 
                WHERE client_id = ? AND is_pinned = TRUE
            """, (client_id,))
            for row in cursor.fetchall():
                pinned.append({
                    'id': row[0],
                    'card_type': 'self',
                    'payload': json.loads(row[1]),
                    'auto_update_enabled': row[2],
                    'is_pinned': True,
                    'created_at': row[3],
                    'updated_at': row[4]
                })
            
            # Character cards
            cursor = conn.execute("""
                SELECT id, card_name, relationship_label, card_json, auto_update_enabled, created_at, last_updated
                FROM character_cards
                WHERE client_id = ? AND is_pinned = TRUE
            """, (client_id,))
            for row in cursor.fetchall():
                card_json = json.loads(row[3])
                payload = {**card_json, 'name': row[1]}
                if row[2]:
                    payload['relationship_label'] = row[2]
                pinned.append({
                    'id': row[0],
                    'card_type': 'character',
                    'payload': payload,
                    'auto_update_enabled': row[4],
                    'is_pinned': True,
                    'created_at': row[5],
                    'updated_at': row[6]
                })
            
            # World events (Life Events)
            cursor = conn.execute("""
                SELECT id, title, description, key_array, event_type, 
                       auto_update_enabled, resolved, created_at, updated_at 
                FROM world_events 
                WHERE client_id = ? AND is_pinned = TRUE
            """, (client_id,))
            for row in cursor.fetchall():
                pinned.append({
                    'id': row[0],
                    'card_type': 'world',
                    'payload': {
                        'title': row[1],
                        'description': row[2],
                        'key_array': json.loads(row[3]),
                        'event_type': row[4],
                        'resolved': row[6]
                    },
                    'auto_update_enabled': row[5],
                    'is_pinned': True,
                    'created_at': row[7],
                    'updated_at': row[8]
                })
        
        return pinned
    
    def get_all_sessions_for_client(self, client_id: int) -> List[Dict]:
        """Get all sessions for a client (for session counting)."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, client_id, counselor_id, session_number, 
                       started_at, ended_at, metadata
                FROM sessions
                WHERE client_id = ?
                ORDER BY started_at DESC
            """, (client_id,))
            return [dict(row) for row in cursor.fetchall()]

    # ============================================================
    # Phase 1: Self Card Methods
    # ============================================================

    def create_self_card(self, client_id: int, card_json: str, auto_update_enabled: bool = True) -> int:
        """Create a self card for a client."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO self_cards (client_id, card_json, auto_update_enabled, last_updated)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (client_id, card_json, auto_update_enabled))
            card_id = cursor.lastrowid
            if card_id is not None:
                self._log_change(conn, 'self_card', card_id, 'created', None, {'card_json': card_json})
            return card_id or 0

    def get_self_card(self, client_id: int) -> Optional[Dict]:
        """Get self card for a client."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM self_cards WHERE client_id = ?
            """, (client_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_self_card_by_id(self, card_id: int) -> Optional[Dict]:
        """Get self card by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM self_cards WHERE id = ?
            """, (card_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_self_card(self, client_id: int, card_json: str, changed_by: str = 'system') -> bool:
        """Update self card for a client."""
        with self._get_connection() as conn:
            old_card = self.get_self_card(client_id)
            cursor = conn.execute("""
                UPDATE self_cards
                SET card_json = ?, last_updated = CURRENT_TIMESTAMP
                WHERE client_id = ?
            """, (card_json, client_id))
            if cursor.rowcount > 0:
                self._log_change(
                    conn,
                    'self_card',
                    client_id,
                    'updated',
                    old_card,
                    json.loads(card_json),
                    changed_by
                )
            return cursor.rowcount > 0

    # ============================================================
    # PHASE 1: World Event Methods
    # ============================================================

    def create_world_event(self, client_id: int, entity_id: str, title: str,
                          key_array: str, description: str, event_type: str,
                          is_canon_law: bool = False, auto_update_enabled: bool = True,
                          resolved: bool = False) -> int:
        """Create a world event."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO world_events
                (client_id, entity_id, title, key_array, description, event_type,
                 is_canon_law, auto_update_enabled, resolved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (client_id, entity_id, title, key_array, description, event_type,
                  is_canon_law, auto_update_enabled, resolved))
            event_id = cursor.lastrowid
            if event_id is not None:
                self._log_change(conn, 'world_event', event_id, 'created', None, {'title': title})
            return event_id or 0

    def get_world_events(self, client_id: int, canon_law_only: bool = False) -> List[Dict]:
        """Get world events for a client."""
        with self._get_connection() as conn:
            if canon_law_only:
                cursor = conn.execute("""
                    SELECT * FROM world_events
                    WHERE client_id = ? AND is_canon_law = TRUE
                    ORDER BY created_at DESC
                """, (client_id,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM world_events
                    WHERE client_id = ?
                    ORDER BY created_at DESC
                """, (client_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_world_event(self, event_id: int, **kwargs) -> bool:
        """Update a world event."""
        allowed_fields = ['title', 'key_array', 'description', 'event_type',
                         'is_canon_law', 'auto_update_enabled', 'resolved', 'changed_by']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields and k != 'changed_by'}
        changed_by = kwargs.get('changed_by', 'system')

        if not updates:
            return False

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(updates.values()) + [event_id]

        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                UPDATE world_events SET {set_clause}
                WHERE id = ?
            """, values)
            if cursor.rowcount > 0:
                self._log_change(conn, 'world_event', event_id, 'updated', None, updates, changed_by)
            return cursor.rowcount > 0

    # ============================================================
    # PHASE 1: Entity Mention Methods
    # ============================================================

    def add_entity_mention(self, client_id: int, session_id: int, entity_type: str,
                          entity_ref: str, mention_context: str) -> int:
        """Add an entity mention."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO entity_mentions
                (client_id, session_id, entity_type, entity_ref, mention_context)
                VALUES (?, ?, ?, ?, ?)
            """, (client_id, session_id, entity_type, entity_ref, mention_context))
            return cursor.lastrowid or 0

    def get_entity_mentions(self, client_id: int, entity_ref: Optional[str] = None,
                          entity_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get entity mentions with optional filtering."""
        with self._get_connection() as conn:
            query = "SELECT * FROM entity_mentions WHERE client_id = ?"
            params = [client_id]

            if entity_ref:
                query += " AND entity_ref = ?"
                params.append(str(entity_ref))

            if entity_type:
                query += " AND entity_type = ?"
                params.append(str(entity_type))

            query += " ORDER BY mentioned_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_entity_mentions_by_session(self, session_id: int) -> List[Dict]:
        """Get entity mentions for a specific session."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM entity_mentions WHERE session_id = ? ORDER BY mentioned_at DESC",
                (session_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # ============================================================
    # PHASE 1: Unified Card Management Methods
    # ============================================================

    def update_auto_update_enabled(self, card_type: str, card_id: int, enabled: bool) -> bool:
        """Toggle auto-update for any card type."""
        table_map = {
            'self': 'self_cards',
            'character': 'character_cards',
            'world': 'world_events'
        }

        table = table_map.get(card_type)
        if not table:
            return False

        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                UPDATE {table}
                SET auto_update_enabled = ?
                WHERE id = ?
            """, (enabled, card_id))
            return cursor.rowcount > 0

    def delete_card(self, card_type: str, card_id: int) -> bool:
        """Delete a card of any type."""
        table_map = {
            'self': 'self_cards',
            'character': 'character_cards',
            'world': 'world_events'
        }

        table = table_map.get(card_type)
        if not table:
            return False

        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                DELETE FROM {table}
                WHERE id = ?
            """, (card_id,))
            return cursor.rowcount > 0

    # ============================================================
    # PHASE 3: Unified Card Management Helper Methods
    # ============================================================

    def _get_auto_update_enabled(self, card_type: str, card_id: int) -> Optional[bool]:
        """Get current auto_update_enabled value for a card."""
        table_map = {
            'self': 'self_cards',
            'character': 'character_cards',
            'world': 'world_events'
        }
        table = table_map.get(card_type)
        if not table:
            return None

        with self._get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT auto_update_enabled FROM {table} WHERE id = ?
            """, (card_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def search_cards(self, query: str, card_types: Optional[List[str]] = None,
                    client_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """
        Search cards across all types using SQL LIKE.

        Searches text fields: names, descriptions, personalities, etc.
        """
        search_term = f"%{query.lower()}%"
        results = []

        search_types = card_types or ['self', 'character', 'world']

        with self._get_connection() as conn:
            if 'self' in search_types:
                sql = "SELECT id, 'self' as card_type, card_json, auto_update_enabled, created_at, last_updated FROM self_cards"
                params = []
                if client_id:
                    sql += " WHERE client_id = ?"
                    params.append(client_id)
                    sql += " AND card_json LIKE ? COLLATE NOCASE"
                    params.append(search_term)
                else:
                    sql += " WHERE card_json LIKE ? COLLATE NOCASE"
                    params.append(search_term)

                sql += " ORDER BY last_updated DESC"

                cursor = conn.execute(sql, params)
                for row in cursor.fetchall():
                    card_json = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                    if any(query.lower() in str(v).lower() for v in card_json.values()):
                        results.append({
                            'id': row[0],
                            'card_type': row[1],
                            'payload': card_json,
                            'relevance': 1.0
                        })

            if 'character' in search_types:
                sql = "SELECT id, 'character' as card_type, card_name, relationship_label, card_json, auto_update_enabled, created_at, last_updated FROM character_cards"
                params = []
                if client_id:
                    sql += " WHERE client_id = ?"
                    params.append(client_id)
                    sql += " AND (card_name LIKE ? COLLATE NOCASE OR card_json LIKE ? COLLATE NOCASE)"
                    params.extend([search_term, search_term])
                else:
                    sql += " WHERE card_name LIKE ? COLLATE NOCASE OR card_json LIKE ? COLLATE NOCASE"
                    params.extend([search_term, search_term])

                sql += " ORDER BY last_updated DESC"

                cursor = conn.execute(sql, params)
                for row in cursor.fetchall():
                    card_json = row[4] if isinstance(row[4], dict) else json.loads(row[4])
                    payload = {**card_json, 'name': row[2]}
                    if row[3]:
                        payload['relationship_label'] = row[3]
                    results.append({
                        'id': row[0],
                        'card_type': row[1],
                        'payload': payload,
                        'relevance': 1.0
                    })

            if 'world' in search_types:
                sql = "SELECT id, 'world' as card_type, title, description, key_array, is_canon_law, resolved, auto_update_enabled, created_at, updated_at FROM world_events"
                params = []
                if client_id:
                    sql += " WHERE client_id = ?"
                    params.append(client_id)
                    sql += " AND (title LIKE ? COLLATE NOCASE OR description LIKE ? COLLATE NOCASE)"
                    params.extend([search_term, search_term])
                else:
                    sql += " WHERE title LIKE ? COLLATE NOCASE OR description LIKE ? COLLATE NOCASE"
                    params.extend([search_term, search_term])

                sql += " ORDER BY updated_at DESC"

                cursor = conn.execute(sql, params)
                for row in cursor.fetchall():
                    key_array = json.loads(row[4]) if isinstance(row[4], str) else row[4]
                    results.append({
                        'id': row[0],
                        'card_type': row[1],
                        'payload': {
                            'title': row[2],
                            'description': row[3],
                            'key_array': key_array,
                            'is_canon_law': bool(row[5]),
                            'resolved': bool(row[6])
                        },
                        'relevance': 1.0
                    })

        return results[:limit]

    async def _log_performance_metric(
        self,
        operation: str,
        duration_ms: int,
        status: str,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """Log performance metric to database."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO performance_metrics (operation_type, duration_ms, status, error_message, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                operation,
                duration_ms,
                status,
                error_message,
                json.dumps(metadata) if metadata else None
            ))


# Global database instance
db = Database("gameapy.db")