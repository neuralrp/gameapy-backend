"""
Pytest configuration and shared fixtures for Gameapy test suite.

This file provides:
- Database isolation with test database
- LLM mocking for deterministic tests
- Sample data fixtures
- API test client fixture
"""

import os
import sys
import pytest
import psycopg2
import json
from typing import Dict, Any, Optional
from contextlib import contextmanager


# =============================================================================
# EARLY DATABASE INITIALIZATION (runs at module import time)
# =============================================================================
# This MUST run before any test modules are imported to ensure they get
# the correct database instance with the test database URL.

print("[CONFTEST] Initializing test database configuration...")

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import and configure settings BEFORE importing database
from app.core.config import settings

# Store original database URL
_original_database_url = settings.database_url

# Update settings to point to test DB
settings.database_url = settings.test_database_url
print(f"[CONFTEST] Database URL configured: {settings.database_url}")

# Now import database module - it will use the test database URL
import app.db.database as db_module
from app.db.database import Database

# Ensure test database exists
def _ensure_test_database(database_url: str):
    """Ensure test database exists."""
    try:
        db_name = database_url.split('/')[-1]
        if '?' in db_name:
            db_name = db_name.split('?')[0]
        
        base_url = '/'.join(database_url.split('/')[:-1]) + '/postgres'
        conn = psycopg2.connect(base_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
        if not cursor.fetchone():
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"[CONFTEST] Created test database: {db_name}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Warning] Could not ensure test database: {e}")

# Apply base schema if needed
def _apply_base_schema(database_url: str):
    """Apply base schema.sql if tables don't exist."""
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        LIMIT 1
    """)
    
    if not cursor.fetchone():
        print("[CONFTEST] No tables found, applying base schema...")
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        cursor.execute(schema_sql)
        print("[CONFTEST] Base schema applied successfully")
    else:
        print("[CONFTEST] Tables already exist, skipping schema application")
    
    cursor.close()
    conn.close()

# Initialize test database
_ensure_test_database(settings.test_database_url)
_apply_base_schema(settings.test_database_url)

# Clean any existing data
conn = psycopg2.connect(settings.test_database_url)
conn.autocommit = True
cursor = conn.cursor()
cursor.execute("""
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename NOT LIKE 'pg_%'
    AND tablename NOT LIKE 'sql_%'
""")
tables = [row[0] for row in cursor.fetchall()]
for table in tables:
    if table != '_migrations':
        cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE')
print(f"[CONFTEST] Cleaned {len(tables)} tables in test database")
cursor.close()
conn.close()

# Reset Database singleton to force new pool with test database URL
print(f"[CONFTEST] Resetting Database singleton...")
if Database._instance and Database._instance._pool:
    Database._instance._pool.closeall()
    print("[CONFTEST] Closed existing connection pool")
Database._instance = None
Database._pool = None

# Force recreation with test database URL
db_module.db = Database()
print(f"[CONFTEST] Database singleton recreated with test database")

# Run migrations
print("[CONFTEST] Running migrations...")
from migrations.run_migrations import run_all_migrations
run_all_migrations()

print("[CONFTEST] Test database initialization complete!")


# =============================================================================
# DATABASE ISOLATION FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def db():
    """
    Provide the database instance for tests.
    
    This fixture returns the singleton Database instance that has been
    configured to use the test database.
    """
    from app.db.database import Database
    return Database()


@pytest.fixture(scope="session", autouse=True)
def test_database_setup():
    """
    Verify database is properly configured (initialization done at import time).
    """
    print("[CONFTEST] test_database_setup() verifying configuration...")
    # Database is already initialized at import time above
    yield
    print("[CONFTEST] Test session complete")


@pytest.fixture(scope="function")
def clean_test_database():
    """
    Clean database tables after each test.

    For PostgreSQL, we use TRUNCATE to clear all tables while preserving schema.
    """
    from app.core.config import settings
    from app.db.database import db

    test_db_url = settings.test_database_url

    print(f"[FIXTURE clean_test_database] Before yield")

    # Check client count before test
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM client_profiles')
        count = cursor.fetchone()['count']
        print(f"[FIXTURE clean_test_database] Client count before test: {count}")

    yield

    print(f"[FIXTURE clean_test_database] After yield, cleaning...")

    # Clean tables after test
    with psycopg2.connect(test_db_url) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename NOT LIKE 'pg_%'
            AND tablename NOT LIKE 'sql_%'
        """)

        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            if table != '_migrations':
                cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE')

        conn.commit()

        print(f"[FIXTURE clean_test_database] Cleaned {len(tables)} tables")


# =============================================================================
# LLM MOCKING FIXTURES
# =============================================================================

@pytest.fixture(scope="function", autouse=True)
def reset_llm_client_state():
    """
    Reset LLM client state before each test.

    This ensures no cached clients or connections persist between tests.
    """
    yield
    # Reset happens automatically via monkeypatch restoration


@pytest.fixture
def mock_llm_success(monkeypatch):
    """
    Mock SimpleLLMClient to return successful JSON responses.

    Use this for tests that expect normal LLM behavior without fallbacks.
    """
    from app.services.simple_llm_fixed import SimpleLLMClient

    class MockSuccessClient:
        def __init__(self):
            self.api_key = "mock_key"

        async def chat_completion(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ) -> Dict[str, Any]:
            # Detect card type from prompt and return appropriate response
            prompt = messages[0].get("content", "") if messages else ""

            if "advisor" in prompt.lower() or "persona" in prompt.lower():
                # Advisor/Persona generation response - extract name from prompt
                import re
                name_match = re.search(r'\*\*Name:\*\*\s*([^\n]+)', prompt)
                name = name_match.group(1).strip() if name_match else "Test Advisor"

                persona_json = f'''{{
                    "spec": "persona_profile_v1",
                    "spec_version": "1.0",
                    "data": {{
                        "name": "{name}",
                        "who_you_are": "Test description",
                        "your_vibe": "Test vibe",
                        "your_worldview": "Test worldview",
                        "session_template": "Hello",
                        "session_examples": [
                            {{"user_situation": "Test", "your_response": "Test response", "approach": "Test approach"}}
                        ],
                        "tags": ["test"],
                        "visuals": {{"primaryColor": "#E8D0A0"}},
                        "crisis_protocol": "Test crisis protocol",
                        "hotlines": []
                    }}
                }}'''
                return {
                    "choices": [{
                        "message": {
                            "content": persona_json
                        }
                    }]
                }
            elif "character card" in prompt.lower() or "relationship_type" in prompt.lower():
                # Character card response
                return {
                    "choices": [{
                        "message": {
                            "content": '{"spec": "gameapy_character_card_v1", "data": {"name": "Test Person", "relationship_type": "friend", "personality": "Test personality"}}'
                        }
                    }]
                }
            elif "world event" in prompt.lower() or "event_type" in prompt.lower():
                # World event response
                return {
                    "choices": [{
                        "message": {
                            "content": '{"title": "Test Event", "event_type": "achievement", "key_array": ["test"], "description": "Test description"}'
                        }
                    }]
                }
            else:
                # Self card response (default)
                return {
                    "choices": [{
                        "message": {
                            "content": '{"spec": "gameapy_self_card_v1", "data": {"name": "Test", "personality": "Test personality", "traits": ["test"]}}'
                        }
                    }]
                }

        async def chat_completion_stream(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ):
            """Yield a single content chunk for streaming."""
            yield {
                "choices": [{
                    "delta": {"content": "Mock streaming response"}
                }]
            }

        async def close(self):
            pass

    import app.services.simple_llm_fixed as llm_module
    import app.api.chat as chat_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module

    mock_instance = MockSuccessClient()

    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)

    # Monkeypatch also in API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)

    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)

    yield

    # Monkeypatch will automatically restore original when fixture exits


@pytest.fixture
def mock_llm_fallback(monkeypatch):
    """
    Mock SimpleLLMClient to trigger fallback path after decode failures.

    Simulates 3 JSON decode failures to test card generator's
    fallback logic.
    """
    from app.services.simple_llm_fixed import SimpleLLMClient

    class MockFallbackClient:
        def __init__(self):
            self.api_key = "mock_key"
            self.call_count = 0

        async def chat_completion(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ) -> Dict[str, Any]:
            self.call_count += 1
            # Return invalid JSON to trigger decode error
            return {
                "choices": [{
                    "message": {
                        "content": "This is not valid JSON"
                    }
                }]
            }

        async def close(self):
            pass

    import app.services.simple_llm_fixed as llm_module
    import app.api.chat as chat_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module

    mock_instance = MockFallbackClient()

    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)

    # Monkeypatch also in API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)

    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)

    yield

    # Monkeypatch will automatically restore original when fixture exits


@pytest.fixture
def mock_llm_error(monkeypatch):
    """
    Mock SimpleLLMClient to raise exceptions.

    Use this to test error handling and logging in card generation.
    """
    from app.services.simple_llm_fixed import SimpleLLMClient

    class MockErrorClient:
        def __init__(self):
            self.api_key = "mock_key"

        async def chat_completion(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ) -> Dict[str, Any]:
            raise Exception("Mock LLM API error")

        async def chat_completion_stream(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ):
            """Yield an error chunk for error handling test."""
            # In a real scenario, this would fail during streaming
            # For testing, we yield content then raise to simulate mid-stream failure
            yield {
                "choices": [{
                    "delta": {"content": "Partial response before error"}
                }]
            }
            raise Exception("Mock LLM API error")

        async def close(self):
            pass

    import app.services.simple_llm_fixed as llm_module
    import app.api.chat as chat_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module

    mock_instance = MockErrorClient()

    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)

    # Monkeypatch also in API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)

    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)

    yield

    # Monkeypatch will automatically restore original when fixture exits


@pytest.fixture
def mock_llm_no_card(monkeypatch):
    """
    Mock SimpleLLMClient to return "no card" responses.

    Use this for tests that expect no card to be suggested.
    """
    from app.services.simple_llm_fixed import SimpleLLMClient

    class MockNoCardClient:
        def __init__(self):
            self.api_key = "mock_key"

        async def chat_completion(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ) -> Dict[str, Any]:
            # Return "no card" response for topic detection
            return {
                "choices": [{
                    "message": {
                        "content": '{"card_type": null, "topic": null, "confidence": 0.0}'
                    }
                }]
            }

        async def chat_completion_stream(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ):
            """Yield empty content for no card response."""
            yield {
                "choices": [{
                    "delta": {"content": ""}
                }]
            }

        async def close(self):
            pass

    import app.services.simple_llm_fixed as llm_module
    import app.api.chat as chat_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module

    mock_instance = MockNoCardClient()

    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)

    # Monkeypatch also in API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)

    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)

    yield

    # Monkeypatch will automatically restore original when fixture exits


@pytest.fixture
def mock_card_generator_success(monkeypatch):
    """
    Mock card generator to return successful card data.

    Provides deterministic responses for each card type.
    """
    from app.services.card_generator import CardGenerator

    class MockCardGenerator:
        async def generate_card(
            self,
            card_type: str,
            plain_text: str,
            context: Optional[str] = None,
            name: Optional[str] = None
        ) -> Dict[str, Any]:
            if card_type == "self":
                return {
                    "card_type": "self",
                    "generated_card": {
                        "spec": "gameapy_self_card_v1",
                        "data": {
                            "name": "Test User",
                            "personality": "Test personality",
                            "traits": ["curious"]
                        }
                    },
                    "preview": True,
                    "fallback": False
                }
            elif card_type == "character":
                return {
                    "card_type": "character",
                    "generated_card": {
                        "spec": "gameapy_character_card_v1",
                        "data": {
                            "name": name or "Test Person",
                            "relationship_type": "friend",
                            "personality": "Test personality"
                        }
                    },
                    "preview": True,
                    "fallback": False
                }
            elif card_type == "world":
                return {
                    "card_type": "world",
                    "generated_card": {
                        "title": "Test Event",
                        "event_type": "achievement",
                        "key_array": ["test", "event"],
                        "description": "Test description"
                    },
                    "preview": True,
                    "fallback": False
                }
            else:
                raise ValueError(f"Invalid card_type: {card_type}")

    import app.services.card_generator as card_gen_module
    original_gen = card_gen_module.card_generator
    card_gen_module.card_generator = MockCardGenerator()

    yield

    card_gen_module.card_generator = original_gen


@pytest.fixture
def mock_llm_streaming_success(monkeypatch):
    """
    Mock SimpleLLMClient to return successful streaming responses.

    Yields multiple content chunks to simulate real streaming behavior.
    """
    from app.services.simple_llm_fixed import SimpleLLMClient

    class MockStreamingClient:
        def __init__(self):
            self.api_key = "mock_key"

        async def chat_completion(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ) -> Dict[str, Any]:
            return {
                "choices": [{
                    "message": {
                        "content": "Mock response"
                    }
                }]
            }

        async def chat_completion_stream(
            self,
            messages: list,
            model: str = "mock-model",
            temperature: float = 0.7,
            max_tokens: int = 1000,
            **kwargs
        ):
            """Yield multiple content chunks to simulate streaming."""
            content_parts = ["Hello ", "there! ", "How ", "are ", "you?"]
            for part in content_parts:
                yield {
                    "choices": [{
                        "delta": {"content": part}
                    }]
                }

        async def close(self):
            pass

    import app.services.simple_llm_fixed as llm_module
    import app.api.chat as chat_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module

    mock_instance = MockStreamingClient()

    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)

    # Monkeypatch also in API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)

    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)

    yield

    # Monkeypatch will automatically restore original when fixture exits


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_sse_response(response_text: str) -> list:
    """
    Parse SSE (Server-Sent Events) streaming response into list of chunks.

    Args:
        response_text: Raw response text from streaming endpoint

    Returns:
        List of parsed chunk dictionaries
    """
    chunks = []
    for line in response_text.split('\n'):
        line = line.strip()
        if line.startswith('data: '):
            try:
                chunk = json.loads(line[6:])
                chunks.append(chunk)
            except (json.JSONDecodeError, ValueError):
                pass
    return chunks


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================

@pytest.fixture(scope="function", autouse=True)
def patch_db_instance():
    """
    Patch db import in test modules to use the test database instance.

    This fixture runs before each test and patches the db import in all
    test modules that have already been loaded, ensuring they use the
    test database instance instead of the production database instance.
    """
    from app.db.database import db as test_db

    # Patch db in all test modules
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith('tests.'):
            mod = sys.modules[mod_name]
            # Store the old db
            old_db = getattr(mod, 'db', None)
            if old_db is not None:
                # Patch with the test db instance
                mod.__dict__['db'] = test_db

    yield

    # No need to restore since the test is over


@pytest.fixture
def sample_client(db):
    """Create a test client profile."""
    from app.core.config import settings

    print(f"[FIXTURE sample_client] db instance: {id(db)}")
    print(f"[FIXTURE sample_client] settings.database_url: {settings.database_url}")

    # Use db.create_client_profile which uses the connection pool
    # This ensures the same pool is used throughout the test
    client_id, recovery_code = db.create_client_profile({
        'data': {
            'name': 'Test User',
            'personality': 'Test',
            'tags': ['test']
        }
    })

    print(f"[FIXTURE sample_client] Created client: {client_id}")

    # Verify client exists using a fresh connection from the pool
    # This commits the transaction from create_client_profile
    # DISABLED FOR DEBUGGING
    # with db._get_connection() as conn:
    #     cursor = conn.cursor()
    #     cursor.execute('SELECT id FROM client_profiles WHERE id = %s', (client_id,))
    #     result = cursor.fetchone()
    #     print(f"[FIXTURE sample_client] Client exists in DB: {result is not None}")

    # Return client_id
    return client_id


@pytest.fixture
def sample_counselor():
    """Create a test counselor profile (non-guide)."""
    from app.db.database import db
    counselor_data = {
        'data': {
            "name": "Test Counselor",
            "who_you_are": "Test",
            "your_vibe": "Supportive",
            "your_worldview": "Test credentials"
        }
    }
    return db.create_counselor_profile(counselor_data)


@pytest.fixture
def sample_self_card(sample_client):
    """Create a sample self card."""
    from app.db.database import db
    import json
    card_data = {
        "spec": "gameapy_self_card_v1",
        "data": {
            "name": "Test User",
            "personality": "Curious and open-minded"
        }
    }
    return db.create_self_card(
        client_id=sample_client,
        card_json=json.dumps(card_data),
        auto_update_enabled=True
    )


@pytest.fixture
def sample_character_card(sample_client):
    """Create a sample character card."""
    from app.db.database import db
    card_data = {
        "name": "Mom",
        "relationship_type": "family",
        "personality": "Caring but overprotective"
    }
    return db.create_character_card(
        client_id=sample_client,
        card_name="Mom",
        relationship_type="family",
        card_data=card_data
    )


@pytest.fixture
def sample_world_event(sample_client):
    """Create a sample world event."""
    from app.db.database import db
    import uuid
    import json
    return db.create_world_event(
        client_id=sample_client,
        entity_id=f"world_{uuid.uuid4().hex}",
        title="College Graduation",
        key_array=json.dumps(['graduation', 'college']),
        description="Graduated with honors in 2020",
        event_type="achievement"
    )


@pytest.fixture
def sample_session(sample_client, sample_counselor):
    """Create a sample session."""
    from app.db.database import db
    return db.create_session(
        client_id=sample_client,
        counselor_id=sample_counselor
    )


@pytest.fixture
def sample_persona_data():
    """Valid persona data following persona_profile_v1 spec."""
    return {
        "spec": "persona_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Advisor",
            "who_you_are": "A test advisor for unit testing",
            "your_vibe": "Helpful and concise",
            "your_worldview": "Testing makes perfect",
            "session_template": "Hello, I'm here to help",
            "session_examples": [{
                "user_situation": "I need help",
                "your_response": "I can help with that",
                "approach": "Direct assistance"
            }],
            "tags": ["test", "helpful"],
            "visuals": {
                "primaryColor": "#E8D0A0",
                "chatBubble": {"backgroundColor": "#F8F0D8"}
            },
            "crisis_protocol": "Test crisis protocol",
            "hotlines": [{"name": "Test", "contact": "123"}]
        }
    }


# =============================================================================
# API TEST CLIENT FIXTURE
# =============================================================================

@pytest.fixture
def test_client():
    """Create FastAPI TestClient for API testing."""
    from fastapi.testclient import TestClient
    # Import main AFTER possible mocks are applied to ensure route handlers use mocked client
    from main import app
    # Create TestClient without context manager to avoid early closure
    client = TestClient(app)
    yield client
    # Cleanup happens automatically when fixture is torn down


@pytest.fixture
async def cleanup_llm_client():
    """
    Close LLM HTTP client after test to avoid event loop issues.

    The global simple_llm_client creates an httpx.AsyncClient at module import time.
    When tests finish, event loop closes but httpx client may still try to
    schedule cleanup callbacks, causing 'Event loop is closed' errors.

    This fixture ensures client is properly closed after test.

    Use this fixture in tests that use real LLM client (not mocks).
    """
    yield

    # Close LLM client's HTTP connection after test
    try:
        from app.services.simple_llm_fixed import simple_llm_client
        await simple_llm_client.close()
    except Exception:
        # Ignore errors during cleanup (client might already be closed)
        pass


# =============================================================================
# AUTH FIXTURES
# =============================================================================

@pytest.fixture
def sample_user(db):
    """Create a test user with username/password."""
    from app.auth.security import get_password_hash
    import uuid
    
    unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
    
    user_id = db.create_user(
        username=unique_username,
        password_hash=get_password_hash("testpass123"),
        profile_data={
            'data': {
                'name': 'Test User',
                'personality': 'Test',
                'tags': ['test']
            }
        }
    )
    
    return user_id


@pytest.fixture
def auth_headers(sample_user):
    """Generate auth headers for authenticated requests."""
    from app.auth.security import create_access_token
    
    token = create_access_token(data={"sub": str(sample_user)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_client_with_auth(auth_headers):
    """Create FastAPI TestClient with auth headers pre-configured."""
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    
    class AuthTestClient:
        def __init__(self, client, headers):
            self._client = client
            self._auth_headers = headers
        
        def get(self, url, **kwargs):
            headers = {**self._auth_headers, **kwargs.pop('headers', {})}
            return self._client.get(url, headers=headers, **kwargs)
        
        def post(self, url, **kwargs):
            headers = {**self._auth_headers, **kwargs.pop('headers', {})}
            return self._client.post(url, headers=headers, **kwargs)
        
        def put(self, url, **kwargs):
            headers = {**self._auth_headers, **kwargs.pop('headers', {})}
            return self._client.put(url, headers=headers, **kwargs)
        
        def delete(self, url, **kwargs):
            headers = {**self._auth_headers, **kwargs.pop('headers', {})}
            return self._client.delete(url, headers=headers, **kwargs)
        
        def __getattr__(self, name):
            return getattr(self._client, name)
    
    return AuthTestClient(client, auth_headers)


# =============================================================================
# AUTH-AWARE SAMPLE DATA FIXTURES (for API tests)
# =============================================================================

@pytest.fixture
def auth_self_card(sample_user):
    """Create a sample self card for the authenticated user."""
    from app.db.database import db
    import json
    card_data = {
        "spec": "gameapy_self_card_v1",
        "data": {
            "name": "Test User",
            "personality": "Curious and open-minded"
        }
    }
    return db.create_self_card(
        client_id=sample_user,
        card_json=json.dumps(card_data),
        auto_update_enabled=True
    )


@pytest.fixture
def auth_character_card(sample_user):
    """Create a sample character card for the authenticated user."""
    from app.db.database import db
    card_data = {
        "name": "Mom",
        "relationship_type": "family",
        "personality": "Caring but overprotective"
    }
    return db.create_character_card(
        client_id=sample_user,
        card_name="Mom",
        relationship_type="family",
        card_data=card_data
    )


@pytest.fixture
def auth_world_event(sample_user):
    """Create a sample world event for the authenticated user."""
    from app.db.database import db
    import uuid
    import json
    return db.create_world_event(
        client_id=sample_user,
        entity_id=f"world_{uuid.uuid4().hex}",
        title="College Graduation",
        key_array=json.dumps(['graduation', 'college']),
        description="Graduated with honors in 2020",
        event_type="achievement"
    )


@pytest.fixture
def auth_session(sample_user, sample_counselor):
    """Create a sample session for the authenticated user."""
    from app.db.database import db
    return db.create_session(
        client_id=sample_user,
        counselor_id=sample_counselor
    )
