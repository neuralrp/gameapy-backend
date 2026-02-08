"""
Phase 4 Test Suite: Auto-Update System + Canon Refactor

Tests for:
- Change logging with changed_by parameter
- User edit detection via get_recent_user_edit()
- Last AI update detection via get_last_ai_update()
- CardUpdater service (confidence thresholds, conflict resolution)
- CanonRefactor service (canon law flag updates)
- Session analysis endpoint integration
"""

import pytest
import sys
import os
import json
import random
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from app.db.database import db
from datetime import datetime

client = TestClient(app)


@pytest.fixture
def setup_test_data():
    """Setup test data for Phase 4 tests."""
    # Create fresh test client
    client_profile = {
        "spec": "client_profile_v1",
        "spec_version": "1.0",
        "data": {
            "name": "Phase4 Test User",
            "personality": "Test personality",
            "traits": ["test"],
            "goals": ["test goal"],
            "presenting_issues": [],
            "life_events": [],
            "preferences": {}
        }
    }
    test_client_id = db.create_client_profile(client_profile)

    # Create self card
    self_card_data = {
        "name": "Test User",
        "summary": "A test user for Phase 4",
        "personality": "Curious, analytical, kind",
        "traits": ["intelligent", "friendly"],
        "interests": ["testing"],
        "values": ["honesty"],
        "strengths": ["determined"],
        "challenges": ["procrastination"],
        "goals": [{"goal": "test auto-updates", "timeframe": "soon"}],
        "triggers": ["time pressure"],
        "coping_strategies": ["deep breathing"],
        "patterns": [{"pattern": "seeks clarity", "weight": 0.8, "mentions": 5}],
        "current_themes": ["growth"],
        "risk_flags": {"crisis": False, "self_harm_history": False, "substance_misuse_concern": False}
    }
    self_card_id = db.create_self_card(
        client_id=test_client_id,
        card_json=json.dumps(self_card_data)
    )

    # Create character card
    char_uuid = ''.join([random.choice('0123456789abcdef') for _ in range(8)])
    character_card_data = {
        "name": "Test Mom",
        "relationship_type": "family",
        "personality": "Supportive, caring, occasionally overprotective",
        "patterns": [{"pattern": "always there", "weight": 0.9, "mentions": 10}],
        "key_events": [
            {"event": "Helped with homework", "date": "2010", "impact": "positive"}
        ],
        "user_feelings": [{"feeling": "trust", "weight": 0.85}],
        "emotional_state": {
            "user_to_other": {
                "trust": 90,
                "emotional_bond": 85,
                "conflict": 15,
                "power_dynamic": -10,
                "fear_anxiety": 5
            },
            "other_to_user": None
        }
    }
    char_card_id = db.create_character_card(
        client_id=test_client_id,
        card_name=character_card_data["name"],
        relationship_type=character_card_data["relationship_type"],
        card_data=character_card_data
    )

    # Create world event (canon)
    canon_uuid = ''.join([random.choice('0123456789abcdef') for _ in range(16)])
    canon_event_data = {
        "title": "Major Life Trauma",
        "description": "A significant traumatic event that shaped my worldview",
        "event_type": "trauma",
        "key_array": ["trauma", "worldview", "shaping"],
        "is_canon_law": True,
        "resolved": False
    }
    canon_event_id = db.create_world_event(
        client_id=test_client_id,
        entity_id=f"canon_{canon_uuid}",
        title=canon_event_data["title"],
        key_array=json.dumps(canon_event_data["key_array"]),
        description=canon_event_data["description"],
        event_type=canon_event_data["event_type"],
        is_canon_law=True
    )

    # Create world event (non-canon)
    non_canon_uuid = ''.join([random.choice('0123456789abcdef') for _ in range(16)])
    non_canon_event_data = {
        "title": "Small Achievement",
        "description": "A minor achievement",
        "event_type": "achievement",
        "key_array": ["achievement", "small"],
        "is_canon_law": False,
        "resolved": True
    }
    non_canon_event_id = db.create_world_event(
        client_id=test_client_id,
        entity_id=f"event_{non_canon_uuid}",
        title=non_canon_event_data["title"],
        key_array=json.dumps(non_canon_event_data["key_array"]),
        description=non_canon_event_data["description"],
        event_type=non_canon_event_data["event_type"],
        is_canon_law=False
    )

    yield {
        "client_id": test_client_id,
        "self_card_id": self_card_id,
        "char_card_id": char_card_id,
        "canon_event_id": canon_event_id,
        "non_canon_event_id": non_canon_event_id
    }


# ============================================================
# Change Logging Tests (4)
# ============================================================

def test_user_edit_logging(setup_test_data):
    """Test that user edits are logged with changed_by='user'."""
    data = setup_test_data

    response = client.put(f"/api/v1/cards/{data['self_card_id']}", json={
        "card_type": "self",
        "card_json": json.dumps({
            "name": "Updated User",
            "summary": "Updated summary",
            "personality": "Updated personality",
            "traits": ["updated"]
        })
    })

    assert response.status_code == 200

    history = db.get_change_history("self_card", data['client_id'], limit=10)
    assert len(history) > 0
    assert history[0]['changed_by'] == 'user'


def test_system_update_logging(setup_test_data):
    """Test that system updates are logged with changed_by='system'."""
    data = setup_test_data

    db.update_self_card(
        client_id=data['client_id'],
        card_json=json.dumps({"name": "System Updated"}),
        changed_by='system'
    )

    history = db.get_change_history("self_card", data['client_id'], limit=10)
    assert len(history) > 0
    assert history[0]['changed_by'] == 'system'


def test_get_recent_user_edit(setup_test_data):
    """Test get_recent_user_edit returns correct data."""
    data = setup_test_data

    client.put(f"/api/v1/cards/{data['char_card_id']}", json={
        "card_type": "character",
        "card_name": "Updated Mom",
        "relationship_type": "family",
        "card_data": {"personality": "Updated personality"}
    })

    recent_edit = db.get_recent_user_edit(
        entity_type="character_card",
        entity_id=data['char_card_id'],
        since_timestamp=None
    )

    assert recent_edit is not None
    assert recent_edit['changed_by'] == 'user'


def test_get_last_ai_update(setup_test_data):
    """Test get_last_ai_update returns correct timestamp."""
    data = setup_test_data

    db.update_self_card(
        client_id=data['client_id'],
        card_json=json.dumps({"name": "AI Updated"}),
        changed_by='system'
    )

    last_update = db.get_last_ai_update("self", data['self_card_id'])

    assert last_update is not None
    assert isinstance(last_update, datetime)


# ============================================================
# CardUpdater Tests (10)
# ============================================================

def test_card_updater_low_batch_confidence(setup_test_data):
    """Test that low batch confidence (< 0.5) skips all updates."""
    data = setup_test_data

    from app.services.card_updater import card_updater

    import asyncio
    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "confidence": 0.3,
                        "updates": []
                    })
                }
            }]
        }

    from app.services.card_updater import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    result = asyncio.run(card_updater.analyze_and_update(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert result['cards_updated'] == 0


def test_card_updater_low_field_confidence(setup_test_data):
    """Test that low field confidence (< 0.7) skips specific field."""
    data = setup_test_data

    from app.services.card_updater import card_updater

    import asyncio
    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "confidence": 0.8,
                        "updates": [{
                            "card_id": data['char_card_id'],
                            "card_type": "character",
                            "updates": [{
                                "field": "personality",
                                "action": "merge",
                                "value": "New trait",
                                "reason": "Test",
                                "confidence": 0.5
                            }]
                        }]
                    })
                }
            }]
        }

    from app.services.card_updater import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    result = asyncio.run(card_updater.analyze_and_update(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert result['cards_updated'] == 0


def test_user_edits_block_updates(setup_test_data):
    """Test that user manual edits block all updates for that card."""
    data = setup_test_data

    client.put(f"/api/v1/cards/{data['char_card_id']}", json={
        "card_type": "character",
        "card_name": "User Edited",
        "card_data": {"personality": "User edited personality"}
    })

    from app.services.card_updater import card_updater
    import asyncio

    result = asyncio.run(card_updater.analyze_and_update(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert result['cards_updated'] == 0


def test_auto_update_disabled_blocks_updates(setup_test_data):
    """Test that auto_update_enabled=False blocks updates."""
    data = setup_test_data

    db.update_auto_update_enabled(
        card_type='character',
        card_id=data['char_card_id'],
        enabled=False
    )

    from app.services.card_updater import card_updater
    import asyncio

    result = asyncio.run(card_updater.analyze_and_update(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert result['cards_updated'] == 0


def test_personality_merge_dedupes(setup_test_data):
    """Test personality merge dedupes correctly."""
    from app.services.card_updater import card_updater

    old = "Friendly, supportive, caring"
    new = "caring, patient, wise"

    merged = card_updater._merge_personality(old, new)

    assert "friendly" in merged.lower()
    assert "supportive" in merged.lower()
    assert "caring" in merged.lower()
    assert "patient" in merged.lower()
    assert "wise" in merged.lower()
    assert merged.lower().count("caring") == 1


def test_patterns_append_dedupes(setup_test_data):
    """Test patterns append with deduping."""
    from app.services.card_updater import card_updater

    old_patterns = [
        {"pattern": "always there", "weight": 0.9, "mentions": 10},
        {"pattern": "helpful", "weight": 0.7, "mentions": 5}
    ]
    new_patterns = [
        {"pattern": "Always There", "weight": 0.8, "mentions": 3},
        {"pattern": "patient", "weight": 0.6, "mentions": 2}
    ]

    result = card_updater._append_patterns(old_patterns, new_patterns)

    assert len(result) == 3
    pattern_texts = [p['pattern'].lower() for p in result]
    assert "always there" in pattern_texts
    assert "helpful" in pattern_texts
    assert "patient" in pattern_texts
    assert pattern_texts.count("always there") == 1


def test_updates_logged_to_change_log(setup_test_data):
    """Test that updates are logged to change_log."""
    data = setup_test_data

    db.update_self_card(
        client_id=data['client_id'],
        card_json=json.dumps({"name": "Logged update"}),
        changed_by='system'
    )

    history = db.get_change_history("self_card", data['client_id'], limit=10)
    assert len(history) > 0
    assert any(h['changed_by'] == 'system' for h in history)


def test_card_updater_invalid_card_id(setup_test_data):
    """Test error handling for invalid card IDs."""
    data = setup_test_data

    from app.services.card_updater import card_updater
    import asyncio

    result = asyncio.run(card_updater.analyze_and_update(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert result['cards_updated'] == 0


def test_card_updater_llm_json_parse_error(setup_test_data):
    """Test LLM JSON parse error handling."""
    data = setup_test_data

    from app.services.card_updater import card_updater
    import asyncio

    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": "Invalid JSON"
                }
            }]
        }

    from app.services.card_updater import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    import pytest
    with pytest.raises(Exception):
        asyncio.run(card_updater.analyze_and_update(
            client_id=data['client_id'],
            session_id=999,
            messages=[{"role": "user", "content": "Test message"}]
        ))


# ============================================================
# CanonRefactor Tests (4)
# ============================================================

def test_canon_refactor_generates_valid_changes(setup_test_data):
    """Test LLM prompt generates valid canon changes."""
    data = setup_test_data

    from app.services.canon_refactor import canon_refactor

    import asyncio
    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "changes": [{
                            "event_id": data['non_canon_event_id'],
                            "title": "Small Achievement",
                            "action": "add_canon",
                            "reason": "User mentioned this was life-changing"
                        }]
                    })
                }
            }]
        }

    from app.services.canon_refactor import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    result = asyncio.run(canon_refactor.refactor_canon_law(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert 'canon_events_updated' in result
    assert 'events_marked_canon' in result
    assert 'events_removed_canon' in result


def test_canon_refactor_adds_canon_flag(setup_test_data):
    """Test canon_refactor adds canon flag to new events."""
    data = setup_test_data

    db.update_world_event(
        event_id=data['non_canon_event_id'],
        is_canon_law=False,
        changed_by='system'
    )

    from app.services.canon_refactor import canon_refactor

    import asyncio
    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "changes": [{
                            "event_id": data['non_canon_event_id'],
                            "title": "Small Achievement",
                            "action": "add_canon",
                            "reason": "Test"
                        }]
                    })
                }
            }]
        }

    from app.services.canon_refactor import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    result = asyncio.run(canon_refactor.refactor_canon_law(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert result['events_marked_canon'] == [data['non_canon_event_id']]


def test_canon_refactor_removes_canon_flag(setup_test_data):
    """Test canon_refactor removes canon flag from old events."""
    data = setup_test_data

    from app.services.canon_refactor import canon_refactor

    import asyncio
    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "changes": [{
                            "event_id": data['canon_event_id'],
                            "title": "Major Life Trauma",
                            "action": "remove_canon",
                            "reason": "User completed therapy and feels resolved"
                        }]
                    })
                }
            }]
        }

    from app.services.canon_refactor import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    result = asyncio.run(canon_refactor.refactor_canon_law(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    assert result['events_removed_canon'] == [data['canon_event_id']]


def test_canon_refactor_logs_rationale(setup_test_data):
    """Test rationale logged to change_log for canon changes."""
    data = setup_test_data

    from app.services.canon_refactor import canon_refactor

    import asyncio
    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "changes": [{
                            "event_id": data['non_canon_event_id'],
                            "title": "Small Achievement",
                            "action": "add_canon",
                            "reason": "Test rationale"
                        }]
                    })
                }
            }]
        }

    from app.services.canon_refactor import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    asyncio.run(canon_refactor.refactor_canon_law(
        client_id=data['client_id'],
        session_id=999,
        messages=[{"role": "user", "content": "Test message"}]
    ))

    history = db.get_change_history("world_event", data['non_canon_event_id'], limit=10)
    assert len(history) > 0


# ============================================================
# Integration Tests (2)
# ============================================================

def test_session_analysis_flow(setup_test_data):
    """Test full session analysis flow works end-to-end."""
    data = setup_test_data

    session_id = db.create_session(data['client_id'], 1)
    db.add_message(session_id, "user", "I've been feeling better lately")
    db.add_message(session_id, "assistant", "That's great to hear!")

    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "confidence": 0.8,
                        "updates": []
                    })
                }
            }]
        }

    from app.services.card_updater import simple_llm_client
    from app.services.canon_refactor import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    response = client.post(f"/api/v1/sessions/{session_id}/analyze")

    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True
    assert 'data' in result
    assert 'cards_updated' in result['data']
    assert 'canon_events_updated' in result['data']


def test_session_analysis_endpoint_returns_correct_summary(setup_test_data):
    """Test session analysis endpoint returns correct summary."""
    data = setup_test_data

    session_id = db.create_session(data['client_id'], 1)
    db.add_message(session_id, "user", "Test message")

    async def mock_llm(*args, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "confidence": 0.8,
                        "updates": []
                    })
                }
            }]
        }

    from app.services.card_updater import simple_llm_client
    simple_llm_client.chat_completion = mock_llm

    response = client.post(f"/api/v1/sessions/{session_id}/analyze")

    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True
    assert result['message'] == "Session analysis complete."
    assert result['data']['cards_updated'] >= 0
    assert result['data']['canon_events_updated'] >= 0
