import psycopg2
import psycopg2.extras
import psycopg2.pool
import json
import uuid
import hashlib
import base64
import secrets
from contextlib import contextmanager
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def _json_serializer(obj):
    """Custom JSON serializer for datetime and other non-serializable objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _prepare_for_json(data):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(data, dict):
        return {k: _prepare_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_prepare_for_json(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    return data


SELF_CARD_DEFAULTS = {
    "name": "",
    "personality": "",
    "background": "",
    "description": "",
    "summary": "",
    "traits": [],
    "interests": [],
    "values": [],
    "strengths": [],
    "challenges": [],
    "goals": [],
    "triggers": [],
    "coping_strategies": [],
    "patterns": [],
    "current_themes": [],
    "risk_flags": {},
}


class Database:
    """PostgreSQL database operations with connection pooling."""

    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._init_pool()
        return cls._instance

    def _init_pool(self):
        """Initialize connection pool."""
        from app.core.config import settings

        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=settings.db_pool_min,
                maxconn=settings.db_pool_max,
                dsn=settings.database_url,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            logger.info("[OK] PostgreSQL connection pool initialized")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize connection pool: {e}")
            raise

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections from pool."""
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    def normalize_self_card_payload(self, payload: Any) -> Dict[str, Any]:
        if payload is None:
            normalized = {}
        elif isinstance(payload, str):
            try:
                normalized = json.loads(payload)
            except json.JSONDecodeError:
                normalized = {}
        elif isinstance(payload, dict):
            if isinstance(payload.get("data"), dict):
                normalized = dict(payload["data"])
                for key, value in payload.items():
                    if key in ("spec", "spec_version", "data", "_metadata"):
                        continue
                    normalized[key] = value
                if "_metadata" in payload:
                    normalized["_metadata"] = payload["_metadata"]
            else:
                normalized = dict(payload)
        else:
            normalized = {}

        for key, default_value in SELF_CARD_DEFAULTS.items():
            if key not in normalized or normalized[key] is None:
                normalized[key] = default_value

        return normalized

    def create_user(self, username: str, password_hash: str, profile_data: Dict[str, Any]) -> int:
        """Create new user with username and password."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            entity_id = f"client_{uuid.uuid4().hex}"

            cursor.execute("""
                INSERT INTO client_profiles
                (entity_id, username, password_hash, name, profile_json, tags)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                entity_id,
                username,
                password_hash,
                profile_data['data']['name'],
                psycopg2.extras.Json(profile_data),
                psycopg2.extras.Json(profile_data['data'].get('tags', []))
            ))

            user_id = cursor.fetchone()['id']

            # Initialize game state
            cursor.execute("""
                INSERT INTO game_state (client_id, gold_coins, farm_level)
                VALUES (%s, %s, %s)
            """, (user_id, 0, 1))

            return user_id

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username (for login)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, password_hash, entity_id, name, profile_json,
                       tags, created_at, updated_at, is_active
                FROM client_profiles
                WHERE username = %s AND is_active = TRUE
            """, (username,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'username': row['username'],
                'password_hash': row['password_hash'],
                'entity_id': row['entity_id'],
                'name': row['name'],
                'profile': row['profile_json'],
                'tags': row['tags'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'is_active': row['is_active']
            }

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID (for JWT verification)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, entity_id, name, profile_json,
                       tags, created_at, updated_at, is_active
                FROM client_profiles
                WHERE id = %s AND is_active = TRUE
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'username': row['username'],
                'entity_id': row['entity_id'],
                'name': row['name'],
                'profile': row['profile_json'],
                'tags': row['tags'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'is_active': row['is_active']
            }

    def create_client_profile(self, profile_data: Dict[str, Any]) -> Tuple[int, str]:
        """
        Create a new client profile with a recovery code.

        Returns:
            Tuple of (client_id, recovery_code)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            entity_id = f"client_{uuid.uuid4().hex}"

            # Generate recovery code
            recovery_code = self._generate_recovery_code()
            recovery_code_hash = self._hash_recovery_code(recovery_code)

            cursor.execute("""
                INSERT INTO client_profiles (entity_id, name, profile_json, tags, recovery_code_hash, recovery_code_expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                entity_id,
                profile_data['data']['name'],
                psycopg2.extras.Json(profile_data),
                psycopg2.extras.Json(profile_data['data'].get('tags', [])),
                recovery_code_hash,
                None  # No expiration for alpha stage
            ))

            profile_id = cursor.fetchone()['id']
            if profile_id is None:
                raise Exception("Failed to create client profile")

            # Initialize game state for new client
            cursor.execute("""
                INSERT INTO game_state (client_id, gold_coins, farm_level)
                VALUES (%s, %s, %s)
            """, (profile_id, 0, 1))

            # Log creation
            self._log_change(conn, 'client_profile', profile_id, 'created', None, profile_data)

            return profile_id, recovery_code

    def get_client_profile(self, profile_id: int) -> Optional[Dict]:
        """Get client profile by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, entity_id, name, profile_json, tags, created_at, updated_at
                FROM client_profiles
                WHERE id = %s AND is_active = TRUE AND deleted_at IS NULL
            """, (profile_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'entity_id': row['entity_id'],
                'name': row['name'],
                'profile': row['profile_json'],
                'tags': row['tags'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                entity_id,
                profile_data['data']['name'],
                profile_data['data'].get('who_you_are', ''),  # specialization column
                profile_data['data'].get('your_vibe', ''),  # therapeutic_style column
                profile_data['data'].get('your_worldview', ''),  # credentials column now stores worldview
                psycopg2.extras.Json(profile_data),
                psycopg2.extras.Json(profile_data['data'].get('tags', [])),
                profile_data['data'].get('is_hidden', False)  # is_hidden field (optional, default False)
            ))

            profile_id = cursor.fetchone()['id']
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
                SELECT id, entity_id, name, specialization, therapeutic_style, credentials, profile_json, tags, created_at, updated_at, client_id, is_custom
                FROM counselor_profiles
                WHERE id = %s AND is_active = TRUE AND deleted_at IS NULL
            """, (profile_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'entity_id': row['entity_id'],
                'name': row['name'],
                'specialization': row['specialization'],
                'therapeutic_style': row['therapeutic_style'],
                'credentials': row['credentials'],
                'profile': row['profile_json'],
                'tags': row['tags'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'client_id': row['client_id'],
                'is_custom': row['is_custom']
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
                    'id': row['id'],
                    'entity_id': row['entity_id'],
                    'name': row['name'],
                    'specialization': row['specialization'],
                    'therapeutic_style': row['therapeutic_style'],
                    'credentials': row['credentials'],
                    'profile': row['profile_json'],
                    'tags': row['tags'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
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
                WHERE LOWER(name) = LOWER(%s) AND is_active = TRUE AND deleted_at IS NULL
            """, (name,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'entity_id': row['entity_id'],
                'name': row['name'],
                'specialization': row['specialization'],
                'therapeutic_style': row['therapeutic_style'],
                'credentials': row['credentials'],
                'profile': row['profile_json'],
                'tags': row['tags'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }

    # ============================================================
    # CUSTOM ADVISOR METHODS (Migration 007)
    # ============================================================

    def create_custom_counselor(
        self,
        client_id: int,
        persona_data: Dict[str, Any]
    ) -> int:
        """
        Create a custom counselor for a specific client.

        This creates a user-defined advisor that appears alongside system personas
        in counselor selection screen.

        Args:
            client_id: The client creating advisor (must exist in client_profiles)
            persona_data: Full persona JSON following persona_profile_v1 spec
                Required structure:
                {
                    "spec": "persona_profile_v1",
                    "spec_version": "1.0",
                    "data": {
                        "name": str,
                        "who_you_are": str,
                        "your_vibe": str,
                        "your_worldview": str,
                        "session_template": str,
                        "session_examples": list,
                        "tags": list,
                        "visuals": dict,
                        "crisis_protocol": str,
                        "hotlines": list
                    }
                }

        Returns:
            counselor_id: The ID of newly created counselor

        Raises:
            ValueError: If persona_data is missing required fields
            Exception: If database insertion fails

        Example:
            >>> persona = {
            ...     "spec": "persona_profile_v1",
            ...     "data": {
            ...         "name": "Captain Wisdom",
            ...         "who_you_are": "A grizzled sea captain...",
            ...         "your_vibe": "Gruff but caring...",
            ...         "your_worldview": "Life is like ocean...",
            ...         "session_template": "Ahoy there!",
            ...         "session_examples": [...],
            ...         "tags": ["maritime", "wisdom"],
            ...         "visuals": {...},
            ...         "crisis_protocol": "...",
            ...         "hotlines": [...]
            ...     }
            ... }
            >>> counselor_id = db.create_custom_counselor(1, persona)
            >>> print(counselor_id)  # 123
        """
        if not isinstance(persona_data, dict):
            raise ValueError("persona_data must be a dictionary")

        if 'data' not in persona_data:
            raise ValueError("persona_data must contain 'data' key")

        data = persona_data['data']
        required_fields = ['name', 'who_you_are', 'your_vibe', 'your_worldview']
        missing_fields = [f for f in required_fields if f not in data or not data[f]]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            entity_id = f"counselor_{uuid.uuid4().hex}"

            cursor.execute("""
                INSERT INTO counselor_profiles (
                    entity_id, name, specialization, therapeutic_style, credentials,
                    profile_json, tags, is_hidden, is_custom, client_id, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                entity_id,
                data['name'],
                data.get('who_you_are', ''),
                data.get('your_vibe', ''),
                data.get('your_worldview', ''),
                psycopg2.extras.Json(persona_data),
                psycopg2.extras.Json(data.get('tags', [])),
                False,
                True,
                client_id,
                True
            ))

            counselor_id = cursor.fetchone()['id']
            if counselor_id is None:
                raise Exception("Failed to create custom counselor - no ID returned")

            self._log_change(
                conn,
                'counselor_profile',
                counselor_id,
                'created',
                None,
                persona_data,
                changed_by=f'client_{client_id}'
            )

            return counselor_id

    def get_custom_counselors(self, client_id: int) -> List[Dict]:
        """
        Get all custom counselors for a specific client.

        Returns only advisors created by this client that haven't been deleted.

        Args:
            client_id: The client whose custom advisors to retrieve

        Returns:
            List of counselor dictionaries with full profile data
            Each dict contains: id, entity_id, name, specialization, therapeutic_style,
            credentials, profile (parsed JSON), tags (parsed JSON), created_at, updated_at

        Example:
            >>> advisors = db.get_custom_counselors(1)
            >>> print(len(advisors))  # 3
            >>> print(advisors[0]['name'])  # "Captain Wisdom"
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    id, entity_id, name, specialization, therapeutic_style,
                    credentials, profile_json, tags, created_at, updated_at
                FROM counselor_profiles
                WHERE client_id = %s
                AND is_custom = TRUE
                AND is_active = TRUE
                AND deleted_at IS NULL
                ORDER BY created_at DESC
            """, (client_id,))

            counselors = []
            for row in cursor.fetchall():
                counselors.append({
                    'id': row['id'],
                    'entity_id': row['entity_id'],
                    'name': row['name'],
                    'specialization': row['specialization'],
                    'therapeutic_style': row['therapeutic_style'],
                    'credentials': row['credentials'],
                    'profile': row['profile_json'],
                    'tags': row['tags'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })

            return counselors

    def count_custom_counselors(self, client_id: int) -> int:
        """
        Count custom counselors for a client.

        Used to enforce 5-advisor limit before creating a new one.

        Args:
            client_id: The client to count advisors for

        Returns:
            Number of active custom counselors (0-5 typically)

        Example:
            >>> count = db.count_custom_counselors(1)
            >>> if count >= 5:
            ...     raise Exception("Maximum advisors reached")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*)
                FROM counselor_profiles
                WHERE client_id = %s
                AND is_custom = TRUE
                AND is_active = TRUE
                AND deleted_at IS NULL
            """, (client_id,))

            result = cursor.fetchone()
            return result['count'] if result else 0

    def update_custom_counselor(
        self,
        counselor_id: int,
        persona_data: Dict[str, Any]
    ) -> bool:
        """
        Update a custom counselor's persona data.

        Only updates profile_json and derived columns. Cannot change
        ownership (client_id) or convert to/from system persona.

        Args:
            counselor_id: The advisor to update
            persona_data: New full persona JSON

        Returns:
            True if update succeeded, False if counselor not found or not custom

        Raises:
            ValueError: If persona_data is invalid

        Example:
            >>> success = db.update_custom_counselor(123, new_persona)
            >>> if not success:
            ...     print("Advisor not found or is a system persona")
        """
        if not isinstance(persona_data, dict) or 'data' not in persona_data:
            raise ValueError("Invalid persona_data structure")

        data = persona_data['data']

        with self._get_connection() as conn:
            verify_cursor = conn.cursor()

            verify_cursor.execute(
                "SELECT is_custom FROM counselor_profiles WHERE id = %s",
                (counselor_id,)
            )
            row = verify_cursor.fetchone()
            if not row or not row['is_custom']:
                return False

            cursor = conn.cursor()


            cursor.execute("""
                UPDATE counselor_profiles
                SET name = %s,
                    specialization = %s,
                    therapeutic_style = %s,
                    credentials = %s,
                    profile_json = %s,
                    tags = %s,
                    updated_at = NOW()
                WHERE id = %s
                AND is_custom = TRUE
            """, (
                data.get('name', ''),
                data.get('who_you_are', ''),
                data.get('your_vibe', ''),
                data.get('your_worldview', ''),
                psycopg2.extras.Json(persona_data),
                psycopg2.extras.Json(data.get('tags', [])),
                counselor_id
            ))

            if cursor.rowcount > 0:
                self._log_change(
                    conn,
                    'counselor_profile',
                    counselor_id,
                    'updated',
                    None,
                    persona_data,
                    changed_by='user'
                )
                return True

            return False

    def delete_custom_counselor(
        self,
        counselor_id: int,
        client_id: int
    ) -> bool:
        """
        Soft-delete a custom counselor.

        Sets is_active = FALSE and deleted_at = NOW().
        This allows for potential undelete in the future and maintains
        referential integrity with sessions table.

        Security: Verifies client_id matches to prevent users from deleting
        other users' advisors.

        Args:
            counselor_id: The advisor to delete
            client_id: The client who owns advisor (security check)

        Returns:
            True if deletion succeeded, False if not found or not owned

        Example:
            >>> success = db.delete_custom_counselor(123, 1)
            >>> if success:
            ...     print("Advisor deleted successfully")
            >>> else:
            ...     print("Advisor not found or access denied")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE counselor_profiles
                SET is_active = FALSE,
                    deleted_at = NOW()
                WHERE id = %s
                AND client_id = %s
                AND is_custom = TRUE
            """, (counselor_id, client_id))

            if cursor.rowcount > 0:
                self._log_change(
                    conn,
                    'counselor_profile',
                    counselor_id,
                    'deleted',
                    None,
                    {'deleted_by': client_id},
                    changed_by=f'client_{client_id}'
                )
                return True

            return False

    def get_all_counselors_including_custom(
        self,
        client_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get all active counselors including user's custom advisors.

        Returns system personas (is_custom = FALSE, is_hidden = FALSE) plus
        any custom advisors created by the specified client.

        Args:
            client_id: Optional client ID. If provided, includes their custom advisors.
                      If None or 0, returns only system personas.

        Returns:
            List of counselor dicts sorted by is_custom (system first), then name
            Each dict includes 'is_custom' boolean flag

        Example:
            >>> counselors = db.get_all_counselors_including_custom(1)
            >>> print(len(counselors))  # 7 (4 system + 3 custom)
            >>>
            >>> counselors = db.get_all_counselors_including_custom()
            >>> print(len(counselors))  # 4 (system only)
        """
        with self._get_connection() as conn:
            params = []

            if client_id:
                query = """
                    SELECT
                        id, entity_id, name, specialization, therapeutic_style,
                        credentials, profile_json, tags, created_at, updated_at,
                        FALSE as is_custom
                    FROM counselor_profiles
                    WHERE is_active = TRUE
                    AND deleted_at IS NULL
                    AND is_custom = FALSE
                    AND is_hidden = FALSE

                    UNION ALL

                    SELECT
                        id, entity_id, name, specialization, therapeutic_style,
                        credentials, profile_json, tags, created_at, updated_at,
                        TRUE as is_custom
                    FROM counselor_profiles
                    WHERE client_id = %s
                    AND is_custom = TRUE
                    AND is_active = TRUE
                    AND deleted_at IS NULL

                    ORDER BY is_custom ASC, name ASC
                """
                params = [client_id]
            else:
                query = """
                    SELECT
                        id, entity_id, name, specialization, therapeutic_style,
                        credentials, profile_json, tags, created_at, updated_at,
                        FALSE as is_custom
                    FROM counselor_profiles
                    WHERE is_active = TRUE
                    AND deleted_at IS NULL
                    AND is_custom = FALSE
                    AND is_hidden = FALSE
                    ORDER BY name ASC
                """

            cursor = conn.cursor()


            cursor.execute(query, params)

            counselors = []
            for row in cursor.fetchall():
                counselors.append({
                    'id': row['id'],
                    'entity_id': row['entity_id'],
                    'name': row['name'],
                    'specialization': row['specialization'],
                    'therapeutic_style': row['therapeutic_style'],
                    'credentials': row['credentials'],
                    'profile': row['profile_json'],
                    'tags': row['tags'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'is_custom': row['is_custom']
                })

            return counselors

    # Session Operations
    def create_session(self, client_id: int, counselor_id: int) -> int:
        """Create a new counseling session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get session number for this client-counselor pair
            cursor.execute("""
                SELECT COALESCE(MAX(session_number), 0) + 1 AS session_number
                FROM sessions
                WHERE client_id = %s AND counselor_id = %s
            """, (client_id, counselor_id))
            session_number = cursor.fetchone()['session_number']

            # Create session
            cursor.execute("""
                INSERT INTO sessions (client_id, counselor_id, session_number)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (client_id, counselor_id, session_number))

            session_id = cursor.fetchone()['id']
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
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (session_id, role, content, speaker))
            message_id = cursor.fetchone()['id']
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
                WHERE session_id = %s
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
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                client_id,
                card_name,
                relationship_type,
                relationship_label,
                psycopg2.extras.Json(card_data)
            ))

            card_id = cursor.fetchone()['id']
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
                WHERE client_id = %s
                ORDER BY card_name
            """, (client_id,))

            return [
                {
                    'id': row['id'],
                    'card_name': row['card_name'],
                    'relationship_type': row['relationship_type'],
                    'relationship_label': row['relationship_label'],
                    'card': row['card_json'],
                    'auto_update_enabled': row['auto_update_enabled'],
                    'last_updated': row['last_updated'],
                    'created_at': row['created_at'],
                    'is_pinned': row['is_pinned']
                }
                for row in cursor.fetchall()
            ]

    def get_character_card_by_id(self, card_id: int) -> Optional[Dict]:
        """Get a character card by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, client_id, card_name, relationship_type, relationship_label, card_json, auto_update_enabled, last_updated, created_at, is_pinned
                FROM character_cards
                WHERE id = %s
            """, (card_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'client_id': row['client_id'],
                    'card_name': row['card_name'],
                    'relationship_type': row['relationship_type'],
                    'relationship_label': row['relationship_label'],
                    'card_json': row['card_json'],
                    'card': row['card_json'],
                    'auto_update_enabled': row['auto_update_enabled'],
                    'last_updated': row['last_updated'],
                    'created_at': row['created_at'],
                    'is_pinned': row['is_pinned']
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

        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [card_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE character_cards
                SET {set_clause}, last_updated = NOW()
                WHERE id = %s
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
                WHERE client_id = %s
            """, (client_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'client_id': row['client_id'],
                'gold_coins': row['gold_coins'],
                'farm_level': row['farm_level'],
                'last_coin_award': row['last_coin_award'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }

    def update_gold_coins(self, client_id: int, coins_earned: int, reason: str = "session_completion") -> bool:
        """Update gold coins for a client."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE game_state
                SET gold_coins = gold_coins + %s,
                    last_coin_award = NOW(),
                    updated_at = NOW()
                WHERE client_id = %s
            """, (coins_earned, client_id))

            # Get current state
            cursor.execute("SELECT gold_coins FROM game_state WHERE client_id = %s", (client_id,))
            new_total = cursor.fetchone()['gold_coins']

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
                WHERE client_id = %s
                ORDER BY created_at DESC
            """, (client_id,))

            return [
                {
                    'id': row['id'],
                    'item_type': row['item_type'],
                    'item_name': row['item_name'],
                    'metadata': row['item_metadata'] if row['item_metadata'] else {},
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
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
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                client_id,
                item_type,
                item_name,
                psycopg2.extras.Json(item_metadata) if item_metadata else None
            ))

            item_id = cursor.fetchone()['id']
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

    # ============================================================
    # Farm Minigame Methods (Message-based growth)
    # ============================================================

    def initialize_farm(self, client_id: int) -> None:
        """Initialize farm for a new client with starting gold."""
        import datetime
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Check if game_state exists
            cursor.execute("SELECT id FROM game_state WHERE client_id = %s", (client_id,))
            if not cursor.fetchone():
                cursor.execute(
                    """INSERT INTO game_state (client_id, gold_coins, farm_level, message_counter, last_login_date)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (client_id, 15, 1, 0, datetime.date.today())
                )

    def increment_message_counter(self, client_id: int) -> int:
        """Increment message counter and return new value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE game_state SET message_counter = message_counter + 1 
                   WHERE client_id = %s RETURNING message_counter""",
                (client_id,)
            )
            result = cursor.fetchone()
            return result['message_counter'] if result else 0

    def get_message_counter(self, client_id: int) -> int:
        """Get current message counter."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT message_counter FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            result = cursor.fetchone()
            return result['message_counter'] if result else 0

    def claim_daily_login(self, client_id: int) -> Tuple[bool, str]:
        """Claim daily login bonus. Returns (success, message)."""
        import datetime
        today = datetime.date.today()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT last_login_date, gold_coins FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return False, "Game state not found"
            
            last_login = row['last_login_date']
            
            if last_login == today:
                return False, "Already claimed today"
            
            # Award 5 gold
            new_gold = row['gold_coins'] + 5
            cursor.execute(
                "UPDATE game_state SET gold_coins = %s, last_login_date = %s WHERE client_id = %s",
                (new_gold, today, client_id)
            )
            
            return True, "Claimed 5 gold"

    def get_farm_status(self, client_id: int) -> Dict:
        """Get complete farm status."""
        from app.config.game_constants import FARM_LEVELS, CROPS, ANIMALS
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get game state
            cursor.execute(
                "SELECT gold_coins, farm_level, message_counter FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            game_state = cursor.fetchone()
            
            if not game_state:
                return {"error": "Game state not found"}
            
            farm_level = game_state['farm_level']
            level_data = FARM_LEVELS.get(farm_level, FARM_LEVELS[1])
            
            # Get planted crops
            cursor.execute(
                """SELECT plot_index, crop_type, planted_at_message, growth_duration, is_harvested, 
                          COALESCE(watered_stages, '[]'::jsonb) as watered_stages, 
                          COALESCE(growth_stage, 0) as growth_stage
                   FROM planted_crops WHERE client_id = %s AND is_harvested = FALSE""",
                (client_id,)
            )
            crops = []
            for row in cursor.fetchall():
                # Parse watered_stages
                try:
                    watered_stages = row['watered_stages']
                    if isinstance(watered_stages, str):
                        watered_stages = json.loads(watered_stages)
                    elif hasattr(watered_stages, 'tolist'):
                        watered_stages = watered_stages.tolist()
                except (json.JSONDecodeError, AttributeError):
                    watered_stages = []
                
                crops.append({
                    'plotIndex': row['plot_index'],
                    'cropType': row['crop_type'],
                    'plantedAtMessage': row['planted_at_message'],
                    'growthDuration': row['growth_duration'],
                    'isHarvested': row['is_harvested'],
                    'wateredStages': watered_stages,
                    'growthStage': row['growth_stage'],
                })
            
            # Get tilled plots (not planted)
            cursor.execute(
                """SELECT fp.plot_index 
                   FROM farm_plots fp
                   LEFT JOIN planted_crops pc ON fp.client_id = pc.client_id 
                       AND fp.plot_index = pc.plot_index 
                       AND pc.is_harvested = FALSE
                   WHERE fp.client_id = %s AND pc.id IS NULL""",
                (client_id,)
            )
            tilledPlots = [row['plot_index'] for row in cursor.fetchall()]
            
            # Get animals
            cursor.execute(
                """SELECT slot_index, animal_type, acquired_at_message, maturity_duration, is_mature 
                   FROM farm_animals WHERE client_id = %s""",
                (client_id,)
            )
            animals = []
            for row in cursor.fetchall():
                animals.append({
                    'slotIndex': row['slot_index'],
                    'animalType': row['animal_type'],
                    'acquiredAtMessage': row['acquired_at_message'],
                    'maturityDuration': row['maturity_duration'],
                    'isMature': row['is_mature'],
                })
            
            # Get decorations
            cursor.execute(
                """SELECT decoration_type, x_position, y_position, variant 
                   FROM farm_decorations WHERE client_id = %s""",
                (client_id,)
            )
            decorations = []
            for row in cursor.fetchall():
                decorations.append({
                    'type': row['decoration_type'],
                    'x': row['x_position'],
                    'y': row['y_position'],
                    'variant': row['variant'],
                })
            
            return {
                "gold": game_state['gold_coins'],
                "farmLevel": farm_level,
                "messageCounter": game_state['message_counter'],
                "crops": crops,
                "tilledPlots": tilledPlots,
                "animals": animals,
                "decorations": decorations,
                "maxPlots": level_data['plots'],
                "maxBarnSlots": level_data['barn_slots'],
                "unlocks": level_data['unlocks'],
            }

    def plant_crop(self, client_id: int, crop_type: str, plot_index: int, message_counter: int) -> Dict:
        """Plant a crop in a plot."""
        from app.config.game_constants import CROPS, FARM_LEVELS
        
        # Validate crop type
        if crop_type not in CROPS:
            return {"success": False, "error": "Invalid crop type"}
        
        crop_info = CROPS[crop_type]
        
        # Get farm level and max plots
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT farm_level, gold_coins FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "Game state not found"}
            
            farm_level = row['farm_level']
            level_data = FARM_LEVELS.get(farm_level, FARM_LEVELS[1])
            
            # Check plot is within unlocked range
            if plot_index >= level_data['plots']:
                return {"success": False, "error": "Plot not unlocked"}
            
            # Check if plot is already occupied
            cursor.execute(
                "SELECT id FROM planted_crops WHERE client_id = %s AND plot_index = %s AND is_harvested = FALSE",
                (client_id, plot_index)
            )
            if cursor.fetchone():
                return {"success": False, "error": "Plot already has a crop"}
            
            # Check gold
            if row['gold_coins'] < crop_info['seed_cost']:
                return {"success": False, "error": "Not enough gold"}
            
            # Deduct gold and plant
            new_gold = row['gold_coins'] - crop_info['seed_cost']
            cursor.execute(
                "UPDATE game_state SET gold_coins = %s WHERE client_id = %s",
                (new_gold, client_id)
            )
            
            cursor.execute(
                """INSERT INTO planted_crops (client_id, crop_type, plot_index, planted_at_message, growth_duration, watered_stages)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (client_id, crop_type, plot_index, message_counter, crop_info['growth_messages'], json.dumps([]))
            )
            
            return {
                "success": True,
                "goldSpent": crop_info['seed_cost'],
                "newGold": new_gold
            }

    def harvest_crop(self, client_id: int, plot_index: int, current_message: int) -> Dict:
        """Harvest a mature crop."""
        from app.config.game_constants import CROPS
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, crop_type, planted_at_message, growth_duration 
                   FROM planted_crops 
                   WHERE client_id = %s AND plot_index = %s AND is_harvested = FALSE""",
                (client_id, plot_index)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "No crop in this plot"}
            
            crop_type = row['crop_type']
            planted_at = row['planted_at_message']
            growth_needed = row['growth_duration']
            
            # Check if mature
            if current_message - planted_at < growth_needed:
                return {"success": False, "error": "Crop not yet mature"}
            
            crop_info = CROPS.get(crop_type, {})
            
            # Mark as harvested
            cursor.execute(
                "UPDATE planted_crops SET is_harvested = TRUE WHERE id = %s",
                (row['id'],)
            )
            
            # Add gold
            cursor.execute(
                "SELECT gold_coins FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            current_gold = cursor.fetchone()['gold_coins']
            sell_price = crop_info.get('sell_price', 10)
            new_gold = current_gold + sell_price
            
            cursor.execute(
                "UPDATE game_state SET gold_coins = %s WHERE client_id = %s",
                (new_gold, client_id)
            )
            
            return {
                "success": True,
                "cropType": crop_type,
                "goldEarned": sell_price,
                "newGold": new_gold
            }

    def buy_animal(self, client_id: int, animal_type: str, slot_index: int, message_counter: int) -> Dict:
        """Buy and place an animal in barn."""
        from app.config.game_constants import ANIMALS, FARM_LEVELS
        
        if animal_type not in ANIMALS:
            return {"success": False, "error": "Invalid animal type"}
        
        animal_info = ANIMALS[animal_type]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check farm level
            cursor.execute(
                "SELECT farm_level, gold_coins FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "Game state not found"}
            
            farm_level = row['farm_level']
            level_data = FARM_LEVELS.get(farm_level, FARM_LEVELS[1])
            
            # Check slot is within unlocked range
            if slot_index >= level_data['barn_slots']:
                return {"success": False, "error": "Barn slot not unlocked"}
            
            # Check gold
            if row['gold_coins'] < animal_info['cost']:
                return {"success": False, "error": "Not enough gold"}
            
            # Check slot available
            cursor.execute(
                "SELECT id FROM farm_animals WHERE client_id = %s AND slot_index = %s",
                (client_id, slot_index)
            )
            if cursor.fetchone():
                return {"success": False, "error": "Slot already occupied"}
            
            new_gold = row['gold_coins'] - animal_info['cost']
            cursor.execute(
                "UPDATE game_state SET gold_coins = %s WHERE client_id = %s",
                (new_gold, client_id)
            )
            
            cursor.execute(
                """INSERT INTO farm_animals (client_id, animal_type, slot_index, acquired_at_message, maturity_duration)
                   VALUES (%s, %s, %s, %s, %s)""",
                (client_id, animal_type, slot_index, message_counter, animal_info['maturity_messages'])
            )
            
            return {
                "success": True,
                "goldSpent": animal_info['cost'],
                "newGold": new_gold
            }

    def harvest_animal(self, client_id: int, slot_index: int, current_message: int) -> Dict:
        """Harvest (sell) a mature animal."""
        from app.config.game_constants import ANIMALS
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, animal_type, acquired_at_message, maturity_duration, is_mature
                   FROM farm_animals 
                   WHERE client_id = %s AND slot_index = %s""",
                (client_id, slot_index)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "No animal in this slot"}
            
            if row['is_mature']:
                return {"success": False, "error": "Animal already harvested"}
            
            animal_type = row['animal_type']
            acquired_at = row['acquired_at_message']
            maturity_needed = row['maturity_duration']
            
            if current_message - acquired_at < maturity_needed:
                return {"success": False, "error": "Animal not yet mature"}
            
            animal_info = ANIMALS.get(animal_type, {})
            
            # Mark as mature
            cursor.execute(
                "UPDATE farm_animals SET is_mature = TRUE WHERE id = %s",
                (row['id'],)
            )
            
            # Add gold
            cursor.execute(
                "SELECT gold_coins FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            current_gold = cursor.fetchone()['gold_coins']
            sell_price = animal_info.get('sell_price', 50)
            new_gold = current_gold + sell_price
            
            cursor.execute(
                "UPDATE game_state SET gold_coins = %s WHERE client_id = %s",
                (new_gold, client_id)
            )
            
            return {
                "success": True,
                "animalType": animal_type,
                "goldEarned": sell_price,
                "newGold": new_gold
            }

    def add_decoration(self, client_id: int, decoration_type: str, x: int, y: int, variant: int = 0) -> Dict:
        """Add a decoration to the farm."""
        from app.config.game_constants import DECORATIONS
        
        if decoration_type not in DECORATIONS:
            return {"success": False, "error": "Invalid decoration type"}
        
        decor_info = DECORATIONS[decoration_type]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check gold
            cursor.execute(
                "SELECT gold_coins FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "Game state not found"}
            
            if row['gold_coins'] < decor_info['cost']:
                return {"success": False, "error": "Not enough gold"}
            
            new_gold = row['gold_coins'] - decor_info['cost']
            cursor.execute(
                "UPDATE game_state SET gold_coins = %s WHERE client_id = %s",
                (new_gold, client_id)
            )
            
            cursor.execute(
                """INSERT INTO farm_decorations (client_id, decoration_type, x_position, y_position, variant)
                   VALUES (%s, %s, %s, %s, %s)""",
                (client_id, decoration_type, x, y, variant)
            )
            
            return {
                "success": True,
                "goldSpent": decor_info['cost'],
                "newGold": new_gold
            }

    def upgrade_farm_level(self, client_id: int) -> Dict:
        """Upgrade farm level."""
        from app.config.game_constants import UPGRADE_COSTS, FARM_LEVELS, MAX_PLOTS
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT farm_level, gold_coins FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "Game state not found"}
            
            current_level = row['farm_level']
            
            if current_level >= 7:
                return {"success": False, "error": "Maximum farm level reached"}
            
            cost = UPGRADE_COSTS.get(current_level, 100)
            
            if row['gold_coins'] < cost:
                return {"success": False, "error": f"Not enough gold. Need {cost} gold."}
            
            new_gold = row['gold_coins'] - cost
            new_level = current_level + 1
            
            cursor.execute(
                "UPDATE game_state SET farm_level = %s, gold_coins = %s WHERE client_id = %s",
                (new_level, new_gold, client_id)
            )
            
            level_data = FARM_LEVELS.get(new_level, {})
            
            return {
                "success": True,
                "newLevel": new_level,
                "cost": cost,
                "newGold": new_gold,
                "newPlots": level_data.get('plots', 0),
                "newBarnSlots": level_data.get('barn_slots', 0),
                "unlocks": level_data.get('unlocks', [])
            }

    def get_farm_shop(self, client_id: int) -> Dict:
        """Get available items to buy from shop."""
        from app.config.game_constants import CROPS, ANIMALS, DECORATIONS, FARM_LEVELS, UPGRADE_COSTS
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT gold_coins, farm_level FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"seeds": [], "animals": [], "decorations": [], "playerGold": 0, "farmLevel": 1}
            
            farm_level = row['farm_level']
            
            # Seeds always available
            seeds = [
                {"id": crop_type, "name": crop_type.capitalize(), "cost": info["seed_cost"], "growthMessages": info["growth_messages"]}
                for crop_type, info in CROPS.items()
            ]
            
            # Animals depend on farm level
            available_animals = []
            if farm_level >= 1:
                available_animals.append({"id": "chicken", "name": "Chicken", "cost": ANIMALS["chicken"]["cost"], "maturityMessages": ANIMALS["chicken"]["maturity_messages"]})
            if farm_level >= 3:
                available_animals.append({"id": "cow", "name": "Cow", "cost": ANIMALS["cow"]["cost"], "maturityMessages": ANIMALS["cow"]["maturity_messages"]})
            if farm_level >= 4:
                available_animals.append({"id": "horse", "name": "Horse", "cost": ANIMALS["horse"]["cost"], "maturityMessages": ANIMALS["horse"]["maturity_messages"]})
            
            # Decorations
            decorations = [
                {"id": dec_type, "name": info["name"], "cost": info["cost"]}
                for dec_type, info in DECORATIONS.items()
            ]
            
            # Upgrade info
            level_data = FARM_LEVELS.get(farm_level, FARM_LEVELS[1])
            upgrade_cost = None
            if farm_level < 7:
                upgrade_cost = UPGRADE_COSTS.get(farm_level, 100)
            
            return {
                "seeds": seeds,
                "animals": available_animals,
                "decorations": decorations,
                "playerGold": row['gold_coins'],
                "farmLevel": farm_level,
                "currentPlots": level_data['plots'],
                "currentBarnSlots": level_data['barn_slots'],
                "upgradeCost": upgrade_cost,
                "nextLevelUnlocks": level_data.get('unlocks', []),
            }

    def get_marina_message_count(self, client_id: int, counselor_id: int) -> int:
        """Get number of messages exchanged with Marina."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM messages m
                JOIN sessions s ON m.session_id = s.id
                WHERE s.client_id = %s AND s.counselor_id = %s
            """, (client_id, counselor_id))
            result = cursor.fetchone()
            return result['count'] if result else 0

    def unlock_mermaid(self, client_id: int) -> Dict:
        """Unlock mermaid for farm (called after 100 messages with Marina)."""
        from app.config.game_constants import MARINA_MERMAID_UNLOCK_MESSAGES
        
        # First check if already unlocked
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM farm_animals WHERE client_id = %s AND animal_type = 'mermaid'",
                (client_id,)
            )
            if cursor.fetchone():
                return {"success": True, "message": "Mermaid already unlocked", "alreadyUnlocked": True}
            
            # Check if we have a pond (need to check decorations)
            cursor.execute(
                "SELECT id FROM farm_decorations WHERE client_id = %s AND decoration_type = 'pond'",
                (client_id,)
            )
            has_pond = cursor.fetchone() is not None
            
            # Add mermaid (free - it's a decoration essentially)
            cursor.execute(
                """INSERT INTO farm_animals (client_id, animal_type, slot_index, acquired_at_message, maturity_duration, is_mature)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (client_id, 'mermaid', 0, 0, 0, True)  # Mermaid is instant, decorative
            )
            
            return {
                "success": True,
                "message": "Mermaid unlocked!",
                "requiresPond": not has_pond,
            }

    def till_plot(self, client_id: int, plot_index: int) -> Dict:
        """Till a plot (prepare soil for planting)."""
        from app.config.game_constants import FARM_LEVELS
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check farm level and max plots
            cursor.execute(
                "SELECT farm_level FROM game_state WHERE client_id = %s",
                (client_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "Game state not found"}
            
            farm_level = row['farm_level']
            level_data = FARM_LEVELS.get(farm_level, FARM_LEVELS[1])
            
            if plot_index >= level_data['plots']:
                return {"success": False, "error": "Plot not unlocked"}
            
            # Check if already tilled
            cursor.execute(
                "SELECT id FROM farm_plots WHERE client_id = %s AND plot_index = %s",
                (client_id, plot_index)
            )
            if cursor.fetchone():
                return {"success": False, "error": "Plot already tilled"}
            
            # Check if already has a crop
            cursor.execute(
                "SELECT id FROM planted_crops WHERE client_id = %s AND plot_index = %s AND is_harvested = FALSE",
                (client_id, plot_index)
            )
            if cursor.fetchone():
                return {"success": False, "error": "Plot already has a crop"}
            
            # Till the plot
            cursor.execute(
                """INSERT INTO farm_plots (client_id, plot_index, state)
                   VALUES (%s, %s, 'tilled')""",
                (client_id, plot_index)
            )
            
            return {
                "success": True,
                "plotIndex": plot_index,
                "state": "tilled"
            }

    def water_crop(self, client_id: int, plot_index: int, stage: int) -> Dict:
        """Water a planted crop at a specific growth stage.
        
        Args:
            client_id: The client ID
            plot_index: The plot index
            stage: The current growth stage (0-indexed)
        
        Returns:
            Dict with success status and watered_stages array
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if crop exists and get current watered_stages
            cursor.execute(
                """SELECT id, COALESCE(watered_stages, '[]'::jsonb) as watered_stages 
                   FROM planted_crops 
                   WHERE client_id = %s AND plot_index = %s AND is_harvested = FALSE""",
                (client_id, plot_index)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "No crop in this plot"}
            
            # Parse the watered_stages array
            try:
                watered_stages = row['watered_stages']
                if isinstance(watered_stages, str):
                    watered_stages = json.loads(watered_stages)
                elif hasattr(watered_stages, 'tolist'):
                    watered_stages = watered_stages.tolist()
            except (json.JSONDecodeError, AttributeError):
                watered_stages = []
            
            # Check if this stage is already watered
            if stage in watered_stages:
                return {"success": False, "error": "This stage already watered", "wateredStages": watered_stages}
            
            # Add the stage to watered_stages
            watered_stages.append(stage)
            
            # Water the crop at this stage
            cursor.execute(
                "UPDATE planted_crops SET watered_stages = %s WHERE id = %s",
                (json.dumps(watered_stages), row['id'])
            )
            
            return {
                "success": True,
                "plotIndex": plot_index,
                "stage": stage,
                "wateredStages": watered_stages
            }

    def get_tilled_plots(self, client_id: int) -> List[int]:
        """Get list of tilled plot indices (not planted)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get tilled plots that don't have crops
            cursor.execute(
                """SELECT fp.plot_index 
                   FROM farm_plots fp
                   LEFT JOIN planted_crops pc ON fp.client_id = pc.client_id 
                       AND fp.plot_index = pc.plot_index 
                       AND pc.is_harvested = FALSE
                   WHERE fp.client_id = %s AND pc.id IS NULL""",
                (client_id,)
            )
            
            return [row['plot_index'] for row in cursor.fetchall()]

    # Change Log Operations
    def _log_change(
        self,
        conn,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: Optional[Any],
        new_value: Optional[Any],
        changed_by: str = 'system'
    ):
        """Log a change to change log table."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO change_log (entity_type, entity_id, action, old_value, new_value, changed_by, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (
            entity_type, entity_id, action,
            psycopg2.extras.Json(_prepare_for_json(old_value)) if old_value else None,
            psycopg2.extras.Json(_prepare_for_json(new_value)) if new_value else None,
            changed_by
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
                WHERE entity_type = %s AND entity_id = %s
                ORDER BY changed_at DESC
                LIMIT %s
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
                WHERE entity_type = %s AND entity_id = %s AND changed_by = 'user'
            """
            params = [entity_type, entity_id]

            if since_timestamp:
                query += " AND changed_at > %s"
                params.append(since_timestamp)

            query += " ORDER BY changed_at DESC LIMIT 1"

            cursor = conn.cursor()


            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_last_ai_update(
        self,
        card_type: str,
        card_id: int
    ) -> Optional[datetime]:
        """Get timestamp of last AI update for a card."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT changed_at FROM change_log
                WHERE entity_type = %s AND entity_id = %s AND changed_by = 'system'
                ORDER BY changed_at DESC LIMIT 1
            """, (f"{card_type}_card", card_id))
            row = cursor.fetchone()
            if row:
                return row['changed_at']
            return None

    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get session by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, client_id, counselor_id, session_number,
                       started_at, ended_at, metadata
                FROM sessions WHERE id = %s
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_session_counselor(self, session_id: int, new_counselor_id: int) -> bool:
        """Update the counselor for a session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE sessions
                SET counselor_id = %s
                WHERE id = %s
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
            cursor = conn.cursor()

            cursor.execute(
                f"UPDATE {table} SET is_pinned = TRUE WHERE id = %s",
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
            cursor = conn.cursor()

            cursor.execute(
                f"UPDATE {table} SET is_pinned = FALSE WHERE id = %s",
                (card_id,)
            )
            return cursor.rowcount > 0

    def get_pinned_cards(self, client_id: int) -> List[Dict]:
        """Get all pinned cards for a client (unified format)."""
        pinned = []

        with self._get_connection() as conn:
            # Self cards
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, card_json, auto_update_enabled, created_at, last_updated
                FROM self_cards
                WHERE client_id = %s AND is_pinned = TRUE
            """, (client_id,))
            for row in cursor.fetchall():
                pinned.append({
                    'id': row['id'],
                    'card_type': 'self',
                    'payload': row['card_json'],
                    'auto_update_enabled': row['auto_update_enabled'],
                    'is_pinned': True,
                    'created_at': row['created_at'],
                    'updated_at': row['last_updated']
                })

            # Character cards
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, card_name, relationship_label, card_json, auto_update_enabled, created_at, last_updated
                FROM character_cards
                WHERE client_id = %s AND is_pinned = TRUE
            """, (client_id,))
            for row in cursor.fetchall():
                card_json = row['card_json']
                payload = {**card_json, 'name': row['card_name']}
                if row['relationship_label']:
                    payload['relationship_label'] = row['relationship_label']
                pinned.append({
                    'id': row['id'],
                    'card_type': 'character',
                    'payload': payload,
                    'auto_update_enabled': row['auto_update_enabled'],
                    'is_pinned': True,
                    'created_at': row['created_at'],
                    'updated_at': row['last_updated']
                })

            # World events (Life Events)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, title, description, key_array, event_type,
                       auto_update_enabled, resolved, created_at, updated_at
                FROM world_events
                WHERE client_id = %s AND is_pinned = TRUE
            """, (client_id,))
            for row in cursor.fetchall():
                pinned.append({
                    'id': row['id'],
                    'card_type': 'world',
                    'payload': {
                        'title': row['title'],
                        'description': row['description'],
                        'key_array': row['key_array'],
                        'event_type': row['event_type'],
                        'resolved': row['resolved']
                    },
                    'auto_update_enabled': row['auto_update_enabled'],
                    'is_pinned': True,
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })

        return pinned

    def get_all_sessions_for_client(self, client_id: int) -> List[Dict]:
        """Get all sessions for a client (for session counting)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, client_id, counselor_id, session_number,
                       started_at, ended_at, metadata
                FROM sessions
                WHERE client_id = %s
                ORDER BY started_at DESC
            """, (client_id,))
            return [dict(row) for row in cursor.fetchall()]

    # ============================================================
    # Phase 1: Self Card Methods
    # ============================================================

    def create_self_card(self, client_id: int, card_json: Any, auto_update_enabled: bool = True) -> int:
        """Create a self card for a client."""
        normalized_payload = self.normalize_self_card_payload(card_json)
        normalized_json = psycopg2.extras.Json(normalized_payload)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # DEBUG: Check if client exists
            cursor.execute("SELECT id FROM client_profiles WHERE id = %s", (client_id,))
            client_exists = cursor.fetchone()
            if not client_exists:
                logger.error(f"[DEBUG] Client {client_id} does not exist in client_profiles!")
                # Try to list all clients
                cursor.execute("SELECT id FROM client_profiles LIMIT 5")
                clients = cursor.fetchall()
                logger.error(f"[DEBUG] Clients in DB: {clients}")
                raise Exception(f"Client {client_id} not found in client_profiles")

            cursor.execute("""
                INSERT INTO self_cards (client_id, card_json, auto_update_enabled, last_updated)
                VALUES (%s, %s, %s, NOW())
                RETURNING id
            """, (client_id, normalized_json, auto_update_enabled))
            card_id = cursor.fetchone()['id']
            if card_id is not None:
                self._log_change(conn, 'self_card', card_id, 'created', None, {'card_json': normalized_payload})
            return card_id or 0

    def get_self_card(self, client_id: int) -> Optional[Dict]:
        """Get self card for a client."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM self_cards WHERE client_id = %s
            """, (client_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_self_card_by_id(self, card_id: int) -> Optional[Dict]:
        """Get self card by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM self_cards WHERE id = %s
            """, (card_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_self_card(self, client_id: int, card_json: Any, changed_by: str = 'system') -> bool:
        """Update self card for a client."""
        normalized_payload = self.normalize_self_card_payload(card_json)
        normalized_json = psycopg2.extras.Json(normalized_payload)

        with self._get_connection() as conn:
            old_card = self.get_self_card(client_id)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE self_cards
                SET card_json = %s, last_updated = NOW()
                WHERE client_id = %s
            """, (normalized_json, client_id))
            if cursor.rowcount > 0:
                self._log_change(
                    conn,
                    'self_card',
                    client_id,
                    'updated',
                    old_card,
                    normalized_payload,
                    changed_by
                )
            return cursor.rowcount > 0

    def upsert_self_card(self, client_id: int, card_json: Any, changed_by: str = 'system') -> int:
        existing = self.get_self_card(client_id)
        if existing:
            self.update_self_card(client_id, card_json, changed_by=changed_by)
            return existing['id']

        return self.create_self_card(client_id, card_json)

    # ============================================================
    # PHASE 1: World Event Methods
    # ============================================================

    def create_world_event(self, client_id: int, entity_id: str, title: str,
                          key_array: str, description: str, event_type: str,
                          is_canon_law: bool = False, auto_update_enabled: bool = True,
                          resolved: bool = False) -> int:
        """Create a world event."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO world_events
                (client_id, entity_id, title, key_array, description, event_type,
                 is_canon_law, auto_update_enabled, resolved)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (client_id, entity_id, title, psycopg2.extras.Json(key_array), description, event_type,
                  is_canon_law, auto_update_enabled, resolved))
            event_id = cursor.fetchone()['id']
            if event_id is not None:
                self._log_change(conn, 'world_event', event_id, 'created', None, {'title': title})
            return event_id or 0

    def get_world_events(self, client_id: int, canon_law_only: bool = False) -> List[Dict]:
        """Get world events for a client."""
        with self._get_connection() as conn:
            if canon_law_only:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM world_events
                    WHERE client_id = %s AND is_canon_law = TRUE
                    ORDER BY created_at DESC
                """, (client_id,))
            else:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM world_events
                    WHERE client_id = %s
                    ORDER BY created_at DESC
                """, (client_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_world_event_by_id(self, event_id: int) -> Optional[Dict]:
        """Get a world event by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM world_events WHERE id = %s
            """, (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_world_event(self, event_id: int, **kwargs) -> bool:
        """Update a world event."""
        allowed_fields = ['title', 'key_array', 'description', 'event_type',
                         'is_canon_law', 'auto_update_enabled', 'resolved', 'changed_by']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields and k != 'changed_by'}
        changed_by = kwargs.get('changed_by', 'system')

        if not updates:
            return False

        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        set_clause += ", updated_at = NOW()"
        values = list(updates.values()) + [event_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE world_events SET {set_clause}
                WHERE id = %s
            """, values)
            if cursor.rowcount > 0:
                self._log_change(conn, 'world_event', event_id, 'updated', None, updates, changed_by)
            return cursor.rowcount > 0

    # ============================================================
    # PHASE1: Entity Mention Methods
    # ============================================================

    def add_entity_mention(self, client_id: int, session_id: int, entity_type: str,
                          entity_ref: str, mention_context: str) -> int:
        """Add an entity mention."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO entity_mentions
                (client_id, session_id, entity_type, entity_ref, mention_context)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (client_id, session_id, entity_type, entity_ref, mention_context))
            return cursor.fetchone()['id'] or 0

    def get_entity_mentions(self, client_id: int, entity_ref: Optional[str] = None,
                          entity_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get entity mentions with optional filtering."""
        with self._get_connection() as conn:
            query = "SELECT * FROM entity_mentions WHERE client_id = %s"
            params: List[object] = [client_id]

            if entity_ref:
                query += " AND entity_ref = %s"
                params.append(str(entity_ref))

            if entity_type:
                query += " AND entity_type = %s"
                params.append(str(entity_type))

            query += " ORDER BY mentioned_at DESC LIMIT %s"
            params.append(limit)

            cursor = conn.cursor()


            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_entity_mentions_by_session(self, session_id: int) -> List[Dict]:
        """Get entity mentions for a specific session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM entity_mentions WHERE session_id = %s ORDER BY mentioned_at DESC",
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
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE {table}
                SET auto_update_enabled = %s
                WHERE id = %s
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
            cursor = conn.cursor()

            cursor.execute(f"""
                DELETE FROM {table}
                WHERE id = %s
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
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT auto_update_enabled FROM {table} WHERE id = %s
            """, (card_id,))
            row = cursor.fetchone()
            return row['auto_update_enabled'] if row else None

    def search_cards(self, query: str, card_types: Optional[List[str]] = None,
                    client_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """
        Search cards across all types using SQL ILIKE.

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
                    sql += " WHERE client_id = %s"
                    params.append(client_id)
                    sql += " AND card_json::text ILIKE %s"
                    params.append(search_term)
                else:
                    sql += " WHERE card_json::text ILIKE %s"
                    params.append(search_term)

                sql += " ORDER BY last_updated DESC"

                cursor = conn.cursor()


                cursor.execute(sql, params)
                for row in cursor.fetchall():
                    card_json = row['card_json']
                    if any(query.lower() in str(v).lower() for v in card_json.values()):
                        results.append({
                            'id': row['id'],
                            'card_type': row['card_type'],
                            'payload': card_json,
                            'relevance': 1.0
                        })

            if 'character' in search_types:
                sql = "SELECT id, 'character' as card_type, card_name, relationship_label, card_json, auto_update_enabled, created_at, last_updated FROM character_cards"
                params = []
                if client_id:
                    sql += " WHERE client_id = %s"
                    params.append(client_id)
                    sql += " AND (card_name ILIKE %s OR card_json::text ILIKE %s)"
                    params.extend([search_term, search_term])
                else:
                    sql += " WHERE card_name ILIKE %s OR card_json::text ILIKE %s"
                    params.extend([search_term, search_term])

                sql += " ORDER BY last_updated DESC"

                cursor = conn.cursor()


                cursor.execute(sql, params)
                for row in cursor.fetchall():
                    card_json = row['card_json']
                    payload = {**card_json, 'name': row['card_name']}
                    if row['relationship_label']:
                        payload['relationship_label'] = row['relationship_label']
                    results.append({
                        'id': row['id'],
                        'card_type': row['card_type'],
                        'payload': payload,
                        'relevance': 1.0
                    })

            if 'world' in search_types:
                sql = "SELECT id, 'world' as card_type, title, description, key_array, is_canon_law, resolved, auto_update_enabled, created_at, updated_at FROM world_events"
                params = []
                if client_id:
                    sql += " WHERE client_id = %s"
                    params.append(client_id)
                    sql += " AND (title ILIKE %s OR description ILIKE %s)"
                    params.extend([search_term, search_term])
                else:
                    sql += " WHERE title ILIKE %s OR description ILIKE %s"
                    params.extend([search_term, search_term])

                sql += " ORDER BY updated_at DESC"

                cursor = conn.cursor()


                cursor.execute(sql, params)
                for row in cursor.fetchall():
                    key_array = row['key_array']
                    results.append({
                        'id': row['id'],
                        'card_type': row['card_type'],
                        'payload': {
                            'title': row['title'],
                            'description': row['description'],
                            'key_array': key_array,
                            'is_canon_law': row['is_canon_law'],
                            'resolved': row['resolved']
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
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO performance_metrics (operation_type, duration_ms, status, error_message, metadata)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                operation,
                duration_ms,
                status,
                error_message,
                psycopg2.extras.Json(metadata) if metadata else None
            ))

    # Recovery Code Operations
    def _generate_recovery_code(self) -> str:
        """Generate a 16-character, user-friendly recovery code."""
        # Generate random bytes and encode as base32 for readability
        code_bytes = secrets.token_bytes(10)
        code = base64.b32encode(code_bytes).decode('ascii').upper()
        # Format as XXXX-XXXX-XXXX-XXXX for readability
        return '-'.join([code[i:i+4] for i in range(0, 16, 4)])

    def _hash_recovery_code(self, code: str) -> str:
        """Hash recovery code using SHA-256 for security."""
        return hashlib.sha256(code.encode()).hexdigest()

    def generate_new_recovery_code(self, client_id: int) -> Optional[str]:
        """
        Generate new recovery code for existing client.

        Args:
            client_id: The client ID to generate code for

        Returns:
            The new recovery code, or None if client not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if client exists
            cursor.execute("""
                SELECT id FROM client_profiles
                WHERE id = %s AND is_active = TRUE
            """, (client_id,))

            if not cursor.fetchone():
                return None

            # Generate new recovery code
            recovery_code = self._generate_recovery_code()
            recovery_code_hash = self._hash_recovery_code(recovery_code)

            cursor.execute("""
                UPDATE client_profiles
                SET recovery_code_hash = %s,
                    recovery_code_expires_at = NULL,
                    last_recovery_at = NULL
                WHERE id = %s
            """, (recovery_code_hash, client_id))

            return recovery_code

    def validate_recovery_code(self, recovery_code: str) -> Optional[int]:
        """
        Validate recovery code and return client_id if valid.

        Args:
            recovery_code: The recovery code to validate

        Returns:
            The client_id if valid, None otherwise
        """
        recovery_code_hash = self._hash_recovery_code(recovery_code)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM client_profiles
                WHERE recovery_code_hash = %s
                AND (recovery_code_expires_at IS NULL OR recovery_code_expires_at > NOW())
                AND is_active = TRUE
                AND deleted_at IS NULL
            """, (recovery_code_hash,))

            row = cursor.fetchone()
            if row:
                client_id = row['id']
                # Update last_recovery_at
                cursor.execute("""
                    UPDATE client_profiles
                    SET last_recovery_at = NOW()
                    WHERE id = %s
                """, (client_id,))
                return client_id
            return None

    def get_recovery_code_status(self, client_id: int) -> Optional[Dict[str, Any]]:
        """
        Get recovery code status for a client.

        Args:
            client_id: The client ID to check

        Returns:
            Dict with recovery status info, or None if client not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT recovery_code_hash, recovery_code_expires_at, last_recovery_at
                FROM client_profiles
                WHERE id = %s AND is_active = TRUE
            """, (client_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'has_recovery_code': row['recovery_code_hash'] is not None,
                'expires_at': row['recovery_code_expires_at'],
                'last_recovered_at': row['last_recovery_at']
            }


# Global database instance - initialized at module load time
db = Database()
