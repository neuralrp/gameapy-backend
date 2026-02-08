"""
Phase 3 Test Suite: Unified Card Management API

Tests for:
- GET /clients/{id}/cards (paginated, page_size=all)
- PUT /cards/{id} (partial updates)
- PUT /cards/{id}/toggle-auto-update
- GET /cards/search (cross-type, type filter)
- DELETE /cards/{id}
"""

import pytest
import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from app.db.database import db
import json

client = TestClient(app)


@pytest.fixture
def setup_test_data():
    """Setup test data for Phase 3 tests."""
    # Use existing test client ID (assume client 1 exists)
    test_client_id = 1

    # Get existing self card for client 1
    existing_self = db.get_self_card(test_client_id)
    if existing_self:
        self_card_id = existing_self['id']
    else:
        # Create self card
        self_card_data = {
            "name": "Test User",
            "summary": "A test user for Phase 3",
            "personality": "Curious, analytical"
        }
        self_card_id = db.create_self_card(
            client_id=test_client_id,
            card_json=json.dumps(self_card_data)
        )

    # Create character card
    import random
    char_uuid = ''.join([random.choice('0123456789abcdef') for _ in range(8)])
    character_card_data = {
        "name": "Test Friend Phase3",
        "relationship_type": "friend",
        "personality": "Friendly, supportive",
        "patterns": [{"pattern": "always there", "weight": 0.9, "mentions": 1}],
        "user_feelings": [{"feeling": "trust", "weight": 0.85}],
        "emotional_state": {
            "user_to_other": {
                "trust": 80,
                "emotional_bond": 70,
                "conflict": 10,
                "power_dynamic": 0,
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

    # Create world event
    import random
    world_uuid = ''.join([random.choice('0123456789abcdef') for _ in range(8)])
    world_event_data = {
        "title": "Test Achievement Phase3",
        "description": "A major achievement in life",
        "event_type": "achievement",
        "key_array": ["achievement", "success", "milestone"],
        "is_canon_law": False,
        "resolved": True
    }
    test_entity_id = ''.join([random.choice('0123456789abcdef') for _ in range(16)])
    world_card_id = db.create_world_event(
        client_id=test_client_id,
        entity_id=f"test_{test_entity_id}",
        title=world_event_data["title"],
        key_array=json.dumps(world_event_data["key_array"]),
        description=world_event_data["description"],
        event_type=world_event_data["event_type"]
    )

    yield {
        "client_id": test_client_id,
        "self_card_id": self_card_id,
        "char_card_id": char_card_id,
        "world_card_id": world_card_id
    }

    # Cleanup - only delete character and world cards (keep self card for future tests)
    try:
        db.delete_card("character", char_card_id)
        db.delete_card("world", world_card_id)
    except:
        pass


# ============================================================
# Test GET /clients/{id}/cards (Unified Card List)
# ============================================================

def test_get_all_cards_paginated(setup_test_data):
    """Test retrieving all cards with pagination."""
    data = setup_test_data

    response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True
    assert 'data' in result
    assert 'items' in result['data']
    assert 'pagination' in result['data']
    assert len(result['data']['items']) >= 3

    pagination = result['data']['pagination']
    assert pagination['page'] == 1
    assert pagination['page_size'] == 20


def test_get_all_cards_page_size_all(setup_test_data):
    """Test retrieving all cards with page_size=all."""
    data = setup_test_data

    response = client.get(f"/api/v1/clients/{data['client_id']}/cards?page_size=all")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True
    assert result['data']['pagination']['total_items'] >= 3


def test_get_all_cards_pagination(setup_test_data):
    """Test pagination with smaller page size."""
    data = setup_test_data

    response = client.get(f"/api/v1/clients/{data['client_id']}/cards?page_size=1&page=1")
    assert response.status_code == 200
    result = response.json()
    assert len(result['data']['items']) == 1
    assert result['data']['pagination']['page'] == 1
    assert result['data']['pagination']['page_size'] == 1


def test_get_cards_unified_format(setup_test_data):
    """Test that all cards have unified format."""
    data = setup_test_data

    response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    result = response.json()
    items = result['data']['items']

    for item in items:
        assert 'id' in item
        assert 'card_type' in item
        assert 'payload' in item
        assert 'auto_update_enabled' in item
        assert 'created_at' in item
        assert 'updated_at' in item


# ============================================================
# Test PUT /cards/{id} (Partial Updates)
# ============================================================

def test_update_self_card_partial(setup_test_data):
    """Test partial update of self card."""
    data = setup_test_data

    updated_card = {
        "name": "Updated Test User",
        "summary": "Updated summary"
    }

    response = client.put(
        f"/api/v1/cards/{data['self_card_id']}",
        json={
            "card_type": "self",
            "card_json": json.dumps(updated_card)
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True
    assert result['data']['card_id'] == data['self_card_id']

    # Verify update
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    self_cards = [item for item in items if item['card_type'] == 'self']
    assert self_cards[0]['payload']['name'] == "Updated Test User"


def test_update_character_card_partial(setup_test_data):
    """Test partial update of character card."""
    data = setup_test_data

    response = client.put(
        f"/api/v1/cards/{data['char_card_id']}",
        json={
            "card_type": "character",
            "card_name": "Updated Friend"
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True

    # Verify update
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    char_cards = [item for item in items if item['card_type'] == 'character']
    assert char_cards[0]['payload']['name'] == "Updated Friend"


def test_update_world_event_partial(setup_test_data):
    """Test partial update of world event."""
    data = setup_test_data

    response = client.put(
        f"/api/v1/cards/{data['world_card_id']}",
        json={
            "card_type": "world",
            "title": "Updated Test Achievement",
            "resolved": False
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True

    # Verify update
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    world_cards = [item for item in items if item['card_type'] == 'world']
    assert world_cards[0]['payload']['title'] == "Updated Test Achievement"
    assert world_cards[0]['payload']['resolved'] is False


def test_update_invalid_card_type(setup_test_data):
    """Test update with invalid card type."""
    data = setup_test_data

    response = client.put(
        f"/api/v1/cards/{data['self_card_id']}",
        json={
            "card_type": "invalid",
            "card_json": json.dumps({"name": "test"})
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is False
    assert "Invalid card type" in result['message']


# ============================================================
# Test PUT /clients/{id}/cards/{id}/toggle-auto-update
# ============================================================

def test_toggle_auto_update(setup_test_data):
    """Test toggling auto-update on/off."""
    data = setup_test_data

    # Get initial state
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    self_cards = [item for item in items if item['card_type'] == 'self']
    initial_state = self_cards[0]['auto_update_enabled']

    # Toggle
    response = client.put(
        f"/api/v1/cards/{data['self_card_id']}/toggle-auto-update?card_type=self"
    )
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True

    # Verify toggle
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    self_cards = [item for item in items if item['card_type'] == 'self']
    assert self_cards[0]['auto_update_enabled'] != initial_state


def test_toggle_auto_update_invalid_type(setup_test_data):
    """Test toggle with invalid card type."""
    data = setup_test_data

    response = client.put(
        f"/api/v1/cards/{data['self_card_id']}/toggle-auto-update?card_type=invalid"
    )
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is False


# ============================================================
# Test GET /clients/{id}/cards/search (Search)
# ============================================================

def test_search_all_types(setup_test_data):
    """Test searching across all card types."""
    data = setup_test_data

    response = client.get(f"/api/v1/cards/search?q=test&client_id={data['client_id']}")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True
    assert 'items' in result['data']
    assert 'pagination' in result['data']


def test_search_filter_by_type(setup_test_data):
    """Test filtering search by card type."""
    data = setup_test_data

    response = client.get(f"/api/v1/cards/search?q=test&types=character&client_id={data['client_id']}")
    assert response.status_code == 200
    result = response.json()
    items = result['data']['items']

    for item in items:
        assert item['card_type'] == 'character'


def test_search_with_client_filter(setup_test_data):
    """Test searching with client_id filter."""
    data = setup_test_data

    response = client.get(f"/api/v1/cards/search?q=test&client_id={data['client_id']}")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True


def test_search_empty_results(setup_test_data):
    """Test search that returns no results."""
    data = setup_test_data

    response = client.get(f"/api/v1/cards/search?q=nonexistent&client_id={data['client_id']}")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True
    assert len(result['data']['items']) == 0


# ============================================================
# Test DELETE /clients/{id}/cards/{id}
# ============================================================

def test_delete_self_card(setup_test_data):
    """Test deleting a self card."""
    data = setup_test_data

    response = client.delete(f"/api/v1/cards/{data['self_card_id']}?card_type=self")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True

    # Verify deletion - just check count decreased
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    self_cards = [item for item in items if item['card_type'] == 'self']
    assert len(self_cards) == 0


def test_delete_character_card(setup_test_data):
    """Test deleting a character card."""
    data = setup_test_data

    response = client.delete(f"/api/v1/cards/{data['char_card_id']}?card_type=character")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True

    # Verify deletion - check that specific card is gone
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    char_cards = [item for item in items if item['card_type'] == 'character']
    assert all(card['id'] != data['char_card_id'] for card in char_cards)


def test_delete_world_event(setup_test_data):
    """Test deleting a world event."""
    data = setup_test_data

    response = client.delete(f"/api/v1/cards/{data['world_card_id']}?card_type=world")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is True

    # Verify deletion
    get_response = client.get(f"/api/v1/clients/{data['client_id']}/cards")
    items = get_response.json()['data']['items']
    world_cards = [item for item in items if item['card_type'] == 'world']
    assert len(world_cards) == 0


def test_delete_invalid_card_type(setup_test_data):
    """Test delete with invalid card type."""
    data = setup_test_data

    response = client.delete(f"/api/v1/cards/{data['self_card_id']}?card_type=invalid")
    assert response.status_code == 200
    result = response.json()
    assert result['success'] is False


# ============================================================
# Run Tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
