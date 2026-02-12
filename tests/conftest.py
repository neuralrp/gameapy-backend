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
import sqlite3
import json
from typing import Dict, Any, Optional
from contextlib import contextmanager


# =============================================================================
# DATABASE ISOLATION FIXTURES
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def test_database_setup():
    print(f"[CONFTEST] test_database_setup() called")
    """
    Wire up test_database_url for all tests.
    
    This runs once at the start of test session to ensure all tests
    use the test database instead of the main database.
    """
    from app.core.config import settings
    import time
    
    original_url = settings.database_url
    
    # Update settings to point to test DB
    settings.database_url = settings.test_database_url
    settings.database_path = settings.database_url.replace("sqlite:///", "")
    
    # Debug: Log settings values
    print(f"[CONFTEST] settings.database_url: {settings.database_url}")
    print(f"[CONFTEST] settings.database_path: {settings.database_path}")
    
    # Remove existing test DB if present with retry logic
    test_db_path = settings.database_path
    if os.path.exists(test_db_path):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                os.remove(test_db_path)
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    print(f"[Warning] Could not remove test DB before setup: {test_db_path}")
    
    # Reinitialize Database with test DB and run migration
    import app.db.database as db_module
    import importlib
    import sys
    
    original_db = db_module.db
    from app.db.database import Database
    db_module.db = Database(test_db_path)
    
    # Force reload of modules that import db to ensure they get the new instance
    for mod_name in list(sys.modules.keys()):
        if 'database' in mod_name or 'db' in mod_name:
            if mod_name.startswith('app.') or mod_name.startswith('tests.'):
                importlib.reload(sys.modules[mod_name])
    
    # Re-set db after reload (reload re-executes db = Database() with default path)
    db_module.db = Database(test_db_path)
    
    # Run all migrations on test DB (after schema is created)
    from migrations.run_migrations import run_all_migrations
    run_all_migrations()
    
    # Run pivot migration on test DB (ensure is_pinned columns exist)
    _run_test_db_migration(db_module.db)
    
    yield
    
    # Close test database connections before restoring original DB
    try:
        # Explicitly close any connections by forcing a connection and closing it
        with db_module.db._get_connection() as conn:
            pass
    except Exception:
        pass
    
    # Restore original DB instance and settings
    db_module.db = original_db
    settings.database_url = original_url
    
    # Cleanup test database file after all tests complete with retry logic
    if os.path.exists(test_db_path):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                os.remove(test_db_path)
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    print(f"[Warning] Could not remove test DB after {max_retries} attempts: {test_db_path}")


def _run_test_db_migration(db_instance):
    """
    Run pivot migration on test database.
    
    This ensures test DB has is_pinned columns and indexes.
    
    Args:
        db_instance: The Database instance to run migration on
    """
    test_db_path = db_instance.db_path
    
    # Use the Database's connection to add is_pinned columns
    with db_instance._get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if is_pinned and relationship_label exist for each table
        for table in ['self_cards', 'character_cards', 'world_events']:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if 'is_pinned' not in columns:
                    # Add is_pinned column
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE")
                    conn.commit()  # Explicit commit
                if table == 'character_cards' and 'relationship_label' not in columns:
                    # Add relationship_label column to character_cards
                    cursor.execute("ALTER TABLE character_cards ADD COLUMN relationship_label TEXT")
                    conn.commit()  # Explicit commit
            except sqlite3.OperationalError as e:
                if 'no such table' in str(e):
                    # Table doesn't exist yet
                    pass
                else:
                    raise
        
        # Create indexes for pinned cards
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_self_cards_pinned ON self_cards(client_id, is_pinned)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_character_cards_pinned ON character_cards(client_id, is_pinned)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_world_events_pinned ON world_events(client_id, is_pinned)")
            conn.commit()  # Explicit commit
        except sqlite3.OperationalError as e:
            # Tables might not exist yet
            if 'no such table' not in str(e):
                raise


@pytest.fixture(scope="function", autouse=True)
def clean_test_database():
    """
    Clean database tables before each test.
    
    Instead of deleting the file (which can be brittle with concurrent connections),
    we truncate tables while preserving schema.
    """
    from app.core.config import settings
    
    # Get test DB path
    test_db_path = settings.test_database_url.replace("sqlite:///", "")
    
    # Initialize fresh test DB if it doesn't exist
    if not os.path.exists(test_db_path):
        yield
        return
    
    # Clean tables before test
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.cursor()
        
        # Disable foreign keys temporarily for truncation
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Get all table names
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # Delete all data from each table
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        
        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
    
    yield
    
    # Clean tables after test
    if os.path.exists(test_db_path):
        with sqlite3.connect(test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
            
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()


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
            
            if "character card" in prompt.lower() or "relationship_type" in prompt.lower():
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
    import app.api.guide as guide_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module
    import app.services.guide_system as guide_system_module
    
    mock_instance = MockSuccessClient()
    
    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)
    
    # Monkeypatch also in the API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)
    
    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_system_module, 'simple_llm_client', mock_instance, raising=False)
    
    yield
    
    # Monkeypatch will automatically restore original when fixture exits


@pytest.fixture
def mock_llm_fallback(monkeypatch):
    """
    Mock SimpleLLMClient to trigger fallback path after decode failures.
    
    Simulates 3 JSON decode failures to test the card generator's
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
    import app.api.guide as guide_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module
    import app.services.guide_system as guide_system_module
    
    mock_instance = MockFallbackClient()
    
    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)
    
    # Monkeypatch also in API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)
    
    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_system_module, 'simple_llm_client', mock_instance, raising=False)
    
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
    import app.api.guide as guide_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module
    import app.services.guide_system as guide_system_module
    
    mock_instance = MockErrorClient()
    
    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)
    
    # Monkeypatch also in the API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)
    
    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_system_module, 'simple_llm_client', mock_instance, raising=False)
    
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
    import app.api.guide as guide_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module
    import app.services.guide_system as guide_system_module
    
    mock_instance = MockNoCardClient()
    
    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)
    
    # Monkeypatch also in the API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)
    
    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_system_module, 'simple_llm_client', mock_instance, raising=False)
    
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
    import app.api.guide as guide_module
    import app.api.session_analyzer as session_analyzer_module
    import app.services.card_generator as card_gen_module
    import app.services.card_updater as card_updater_module
    import app.services.guide_system as guide_system_module
    
    mock_instance = MockStreamingClient()
    
    # Use monkeypatch to replace global instance
    monkeypatch.setattr(llm_module, 'simple_llm_client', mock_instance)
    
    # Monkeypatch also in API modules that import it directly
    monkeypatch.setattr(chat_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(session_analyzer_module, 'simple_llm_client', mock_instance, raising=False)
    
    # Monkeypatch in services that import at module load time
    monkeypatch.setattr(card_gen_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(card_updater_module, 'simple_llm_client', mock_instance, raising=False)
    monkeypatch.setattr(guide_system_module, 'simple_llm_client', mock_instance, raising=False)
    
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
    for line in response_text.split('\n\n'):
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

@pytest.fixture
def sample_client():
    """Create a test client profile."""
    from app.db.database import db
    client_id, recovery_code = db.create_client_profile({
        'data': {
            'name': 'Test User',
            'personality': 'Test',
            'tags': ['test']
        }
    })
    return client_id


@pytest.fixture
def sample_counselor():
    """Create a test counselor profile (non-guide)."""
    from app.db.database import db
    counselor_data = {
        'data': {
            "name": "Test Counselor",
            "specialization": "Test",
            "therapeutic_style": "Supportive",
            "credentials": "Test credentials"
        }
    }
    return db.create_counselor_profile(counselor_data)


@pytest.fixture
def sample_guide_counselor():
    """Create a guide counselor profile for guide system tests."""
    from app.db.database import db
    counselor_data = {
        'data': {
            "name": "Guide",
            "specialization": "Onboarding & Getting to Know You",
            "therapeutic_style": (
                "Warm, curious, and conversational. "
                "Helps users share what matters at their own pace."
            ),
            "credentials": "AI Guide"
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
    return db.create_world_event(
        client_id=sample_client,
        entity_id=f"world_{uuid.uuid4().hex}",
        title="College Graduation",
        key_array='["graduation", "college"]',
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
    When tests finish, the event loop closes but the httpx client may still try to
    schedule cleanup callbacks, causing 'Event loop is closed' errors.
    
    This fixture ensures the client is properly closed after the test.
    Use this fixture in tests that use the real LLM client (not mocks).
    """
    yield
    
    # Close the LLM client's HTTP connection after test
    try:
        from app.services.simple_llm_fixed import simple_llm_client
        await simple_llm_client.close()
    except Exception:
        # Ignore errors during cleanup (client might already be closed)
        pass
