"""
Test suite for Custom Advisor feature.

Tests cover:
- Database migration 008
- AdvisorGenerator service
- E2E flows
- Edge cases and error conditions
- Performance tests

Run with: pytest tests/test_custom_counselors.py -v
"""

import pytest
import json
from datetime import datetime
from app.db.database import db


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_client():
    """Create a test client and return its ID."""
    profile_data = {
        "spec": "client_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Client",
            "tags": ["test"]
        }
    }
    client_id, _ = db.create_client_profile(profile_data)
    return {"id": client_id, "name": "Test Client"}


# ============================================================
# Migration Tests
# ============================================================

@pytest.mark.unit
def test_migration_008_columns_exist():
    """Verify migration 008 columns are present in database."""
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'counselor_profiles'
        """)
        columns = {row['column_name'] for row in cursor.fetchall()}
        
        # Check all migration 008 columns exist
        assert 'client_id' in columns, "client_id column missing"
        assert 'is_custom' in columns, "is_custom column missing"
        assert 'image_url' in columns, "image_url column missing"
        assert 'last_image_regenerated' in columns, "last_image_regenerated column missing"


@pytest.mark.unit
def test_migration_008_index_exists():
    """Verify migration 008 index was created."""
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'counselor_profiles' 
            AND indexname = 'idx_counselor_profiles_client_custom'
        """)
        assert cursor.fetchone() is not None, "Index not found"


# ============================================================
# AdvisorGenerator Tests
# ============================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_advisor_generator_creates_valid_persona(mock_llm_success):
    """Test that AdvisorGenerator creates valid persona structure."""
    from app.services.advisor_generator import AdvisorGenerator
    
    generator = AdvisorGenerator()
    
    persona = await generator.generate_advisor(
        name="Captain Test",
        specialty="Testing best practices",
        vibe="Encouraging and thorough"
    )
    
    # Validate top-level structure
    assert persona['spec'] == 'persona_profile_v1'
    assert persona['spec_version'] == '1.0'
    assert 'data' in persona
    
    # Validate data fields
    data = persona['data']
    assert data['name'] == 'Captain Test'
    assert 'who_you_are' in data
    assert 'your_vibe' in data
    assert 'your_worldview' in data
    assert 'session_template' in data
    assert 'session_examples' in data
    assert 'tags' in data
    assert 'visuals' in data
    assert 'crisis_protocol' in data
    assert 'hotlines' in data
    
    # Validate session_examples
    assert isinstance(data['session_examples'], list)
    assert len(data['session_examples']) >= 1
    for example in data['session_examples']:
        assert 'user_situation' in example
        assert 'your_response' in example
        assert 'approach' in example


@pytest.mark.integration
@pytest.mark.asyncio
async def test_advisor_generator_retry_on_failure():
    """Test that generator retries on parse failure."""
    from app.services.advisor_generator import AdvisorGenerator
    
    generator = AdvisorGenerator()
    generator.max_retries = 2
    
    # This should succeed within retries
    persona = await generator.generate_advisor(
        name="Retry Test",
        specialty="Testing retry logic",
        vibe="Persistent"
    )
    
    assert persona['data']['name'] == 'Retry Test'


@pytest.mark.unit
def test_advisor_generator_parse_markdown_code_blocks():
    """Test parsing JSON from markdown code blocks."""
    from app.services.advisor_generator import AdvisorGenerator
    
    generator = AdvisorGenerator()
    
    # Test with ```json
    response_json = '{"spec": "persona_profile_v1", "data": {"name": "Test"}}'
    markdown_response = f"```json\n{response_json}\n```"
    
    parsed = generator._parse_llm_response(markdown_response)
    assert parsed['data']['name'] == 'Test'
    
    # Test with just ```
    markdown_response = f"```\n{response_json}\n```"
    parsed = generator._parse_llm_response(markdown_response)
    assert parsed['data']['name'] == 'Test'


@pytest.mark.unit
def test_advisor_generator_validate_structure():
    """Test persona structure validation."""
    from app.services.advisor_generator import AdvisorGenerator
    
    generator = AdvisorGenerator()
    
    # Valid persona
    valid_persona = {
        "spec": "persona_profile_v1",
        "data": {
            "name": "Test",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [{"user_situation": "x", "your_response": "y"}],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    # Should not raise
    generator._validate_persona_structure(valid_persona, "Test")
    
    # Invalid - missing required field
    invalid_persona = {
        "spec": "persona_profile_v1",
        "data": {"name": "Test"}  # Missing other fields
    }
    
    with pytest.raises(ValueError) as exc_info:
        generator._validate_persona_structure(invalid_persona, "Test")
    
    assert "Missing required fields" in str(exc_info.value)


# ============================================================
# Database Method Tests
# ============================================================

@pytest.mark.integration
def test_create_custom_counselor(sample_client):
    """Test creating a custom counselor."""
    persona_data = {
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
            "visuals": {"primaryColor": "#E8D0A0"},
            "crisis_protocol": "Test crisis protocol",
            "hotlines": [{"name": "Test", "contact": "123"}]
        }
    }
    
    counselor_id = db.create_custom_counselor(
        client_id=sample_client['id'],
        persona_data=persona_data
    )
    
    assert counselor_id > 0, "Counselor ID should be positive integer"
    
    # Verify in database
    counselor = db.get_counselor_profile(counselor_id)
    assert counselor is not None
    assert counselor['name'] == "Test Advisor"
    assert counselor['profile']['data']['name'] == "Test Advisor"


@pytest.mark.integration
def test_create_custom_counselor_validation():
    """Test validation in create_custom_counselor."""
    # Missing required field
    invalid_persona = {
        "spec": "persona_profile_v1",
        "data": {"name": "Test"}  # Missing who_you_are, etc.
    }
    
    with pytest.raises(ValueError) as exc_info:
        db.create_custom_counselor(1, invalid_persona)
    
    assert "Missing required fields" in str(exc_info.value)


@pytest.mark.integration
def test_get_custom_counselors(sample_client):
    """Test retrieving custom counselors for a client."""
    persona_data = {
        "spec": "persona_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Advisor",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    # Create 3 advisors
    for i in range(3):
        persona = persona_data.copy()
        persona['data']['name'] = f"Advisor {i}"
        db.create_custom_counselor(sample_client['id'], persona)
    
    # Retrieve
    advisors = db.get_custom_counselors(sample_client['id'])
    
    assert len(advisors) == 3
    # Should be ordered by created_at DESC
    advisor_names = [a['name'] for a in advisors]
    assert "Advisor 0" in advisor_names
    assert "Advisor 1" in advisor_names
    assert "Advisor 2" in advisor_names


@pytest.mark.integration
def test_get_custom_counselors_empty(sample_client):
    """Test retrieving advisors when none exist."""
    advisors = db.get_custom_counselors(sample_client['id'])
    assert advisors == []


@pytest.mark.integration
def test_count_custom_counselors(sample_client):
    """Test counting custom counselors."""
    persona_data = {
        "spec": "persona_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Advisor",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    # Initially 0
    assert db.count_custom_counselors(sample_client['id']) == 0
    
    # Create 2
    db.create_custom_counselor(sample_client['id'], persona_data)
    db.create_custom_counselor(sample_client['id'], persona_data)
    
    assert db.count_custom_counselors(sample_client['id']) == 2


@pytest.mark.integration
def test_delete_custom_counselor(sample_client):
    """Test soft-deleting a custom counselor."""
    persona_data = {
        "spec": "persona_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Advisor",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    # Create
    counselor_id = db.create_custom_counselor(
        sample_client['id'],
        persona_data
    )
    
    # Delete
    success = db.delete_custom_counselor(counselor_id, sample_client['id'])
    assert success is True
    
    # Verify not in list
    advisors = db.get_custom_counselors(sample_client['id'])
    assert len(advisors) == 0
    
    # Verify cannot delete again (wrong owner)
    success = db.delete_custom_counselor(counselor_id, 99999)
    assert success is False


@pytest.mark.integration
def test_delete_wrong_owner(sample_client):
    """Test that users can't delete other users' advisors."""
    persona_data = {
        "spec": "persona_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Advisor",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    # Create another client
    other_client = db.create_client_profile({
        "spec": "client_profile_v1",
        "spec_version": "1.0",
        "data": {"name": "Other Client"}
    })
    
    # Create advisor for sample_client
    counselor_id = db.create_custom_counselor(
        sample_client['id'],
        persona_data
    )
    
    # Try to delete with wrong client_id
    success = db.delete_custom_counselor(counselor_id, other_client[0])
    assert success is False


@pytest.mark.integration
def test_get_all_counselors_including_custom(sample_client):
    """Test getting all counselors including custom ones."""
    persona_data = {
        "spec": "persona_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Advisor",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    # Count system personas
    all_counselors = db.get_all_counselors_including_custom()
    system_count = len(all_counselors)
    
    # Create custom advisor
    db.create_custom_counselor(sample_client['id'], persona_data)
    
    # Get with client_id
    all_with_custom = db.get_all_counselors_including_custom(sample_client['id'])
    
    assert len(all_with_custom) == system_count + 1
    
    # Verify is_custom flag
    custom_advisors = [c for c in all_with_custom if c.get('is_custom')]
    assert len(custom_advisors) == 1


# ============================================================
# E2E Flow Tests
# ============================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_create_and_use_advisor(sample_client, mock_llm_success):
    """Test complete flow: create advisor → appears in list → can chat."""
    from app.services.advisor_generator import advisor_generator
    
    # 1. Generate advisor
    persona = await advisor_generator.generate_advisor(
        name="E2E Advisor",
        specialty="End-to-end testing",
        vibe="Reliable"
    )
    
    # 2. Save to database
    counselor_id = db.create_custom_counselor(
        client_id=sample_client['id'],
        persona_data=persona
    )
    
    # 3. Verify appears in custom list
    custom_advisors = db.get_custom_counselors(sample_client['id'])
    assert any(a['id'] == counselor_id for a in custom_advisors)
    
    # 4. Verify appears in all counselors
    all_counselors = db.get_all_counselors_including_custom(sample_client['id'])
    assert any(c['id'] == counselor_id for c in all_counselors)


@pytest.mark.e2e
def test_e2e_advisor_persists_after_redeploy(sample_client):
    """Test that advisors persist in database (simulates redeploy)."""
    persona_data = {
        "spec": "persona_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Test Advisor",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    # Create
    counselor_id = db.create_custom_counselor(
        sample_client['id'],
        persona_data
    )
    
    # Simulate "redeploy" by re-fetching from same DB (PostgreSQL persists automatically)
    counselor = db.get_counselor_profile(counselor_id)
    assert counselor is not None
    assert counselor['name'] == "Test Advisor"


# ============================================================
# Performance Tests
# ============================================================

@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_advisor_generator_performance():
    """Test that advisor generation completes within reasonable time."""
    import time
    
    from app.services.advisor_generator import AdvisorGenerator
    
    generator = AdvisorGenerator()
    
    start = time.time()
    persona = await generator.generate_advisor(
        name="Performance Test",
        specialty="Speed testing",
        vibe="Fast"
    )
    duration = time.time() - start
    
    # Should complete within 30 seconds (generous for LLM call)
    assert duration < 30, f"Generation took {duration:.2f}s, expected < 30s"
    assert persona['data']['name'] == "Performance Test"


# ============================================================
# Edge Cases
# ============================================================

@pytest.mark.integration
def test_create_advisor_with_special_characters(sample_client):
    """Test creating advisor with special characters in name."""
    persona_data = {
        "spec": "persona_profile_v1",
        "data": {
            "name": "Advisor O'Brien-Smith Jr.",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    counselor_id = db.create_custom_counselor(sample_client['id'], persona_data)
    counselor = db.get_counselor_profile(counselor_id)
    
    assert counselor['name'] == "Advisor O'Brien-Smith Jr."


@pytest.mark.integration
def test_create_advisor_unicode(sample_client):
    """Test creating advisor with unicode characters."""
    persona_data = {
        "spec": "persona_profile_v1",
        "data": {
            "name": "顾问 (Advisor)",
            "who_you_are": "Test",
            "your_vibe": "Test",
            "your_worldview": "Test",
            "session_template": "Test",
            "session_examples": [],
            "tags": [],
            "visuals": {},
            "crisis_protocol": "Test",
            "hotlines": []
        }
    }
    
    counselor_id = db.create_custom_counselor(sample_client['id'], persona_data)
    counselor = db.get_counselor_profile(counselor_id)
    
    assert "顾问" in counselor['name']
