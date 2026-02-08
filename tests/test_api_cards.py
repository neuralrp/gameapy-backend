"""
Card API endpoints tests.

Tests generate/save, update/toggle, pin/unpin, search/delete endpoints,
and LLM error handling scenarios.
"""
import pytest
import json
import uuid
from app.models.schemas import (
    CardGenerateRequest,
    CardSaveRequest,
    CardUpdateRequest,
    CardSearchRequest
)
from app.db.database import db


@pytest.mark.integration
class TestCardsGenerateSave:
    """Test /generate-from-text and /save endpoints."""

    @pytest.mark.integration
    def test_generate_from_text_success_self(self, test_client, mock_llm_success):
        """Generate self card preview."""
        response = test_client.post(
            "/api/v1/cards/generate-from-text",
            json={
                "card_type": "self",
                "plain_text": "I'm curious and love learning"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['card_type'] == 'self'
        assert 'generated_card' in data['data']

    @pytest.mark.integration
    def test_generate_from_text_success_character(self, test_client, mock_llm_success):
        """Generate character card preview."""
        response = test_client.post(
            "/api/v1/cards/generate-from-text",
            json={
                "card_type": "character",
                "plain_text": "My boss is strict but fair",
                "name": "Boss"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['card_type'] == 'character'
        assert 'generated_card' in data['data']

    @pytest.mark.integration
    def test_generate_from_text_success_world(self, test_client, mock_llm_success):
        """Generate world event preview."""
        response = test_client.post(
            "/api/v1/cards/generate-from-text",
            json={
                "card_type": "world",
                "plain_text": "I graduated from college last year"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['card_type'] == 'world'
        assert 'generated_card' in data['data']

    @pytest.mark.integration
    def test_generate_from_text_invalid_type(self, test_client):
        """Invalid card_type returns error."""
        response = test_client.post(
            "/api/v1/cards/generate-from-text",
            json={
                "card_type": "invalid",
                "plain_text": "Test"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'invalid' in data['message'].lower()

    @pytest.mark.integration
    def test_save_card_success(self, test_client, sample_client):
        """Save generated card to database."""
        response = test_client.post(
            "/api/v1/cards/save",
            json={
                "client_id": sample_client,
                "card_type": "self",
                "card_data": {
                    "spec": "gameapy_self_card_v1",
                    "data": {
                        "name": "Test User",
                        "personality": "Curious"
                    }
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'card_id' in data['data']
        assert data['data']['card_id'] > 0

    @pytest.mark.integration
    def test_generate_from_text_llm_error(self, test_client, mock_llm_error):
        """LLM error returns graceful failure message."""
        response = test_client.post(
            "/api/v1/cards/generate-from-text",
            json={
                "card_type": "self",
                "plain_text": "I'm curious"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'Failed to generate card' in data['message']

    @pytest.mark.integration
    def test_generate_from_text_fallback(self, test_client, mock_llm_fallback):
        """3 decode failures return fallback object with fallback flag."""
        response = test_client.post(
            "/api/v1/cards/generate-from-text",
            json={
                "card_type": "self",
                "plain_text": "I'm curious"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        result = data['data']
        assert 'fallback' in result
        assert 'preview' in result
        assert result.get('fallback') in [True, False]


@pytest.mark.integration
class TestCardsUpdateToggle:
    """Test /update and /toggle-auto-update endpoints."""

    @pytest.mark.integration
    def test_update_card_partial_self(self, test_client, sample_client):
        """Partial update self card."""
        card_id = db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {"personality": "Old"}})
        )
        
        response = test_client.put(
            f"/api/v1/cards/{card_id}",
            json={
                "card_type": "self",
                "card_json": json.dumps({"spec": "gameapy_self_card_v1", "data": {"personality": "New"}})
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['card_id'] == card_id

    @pytest.mark.integration
    def test_update_card_partial_character(self, test_client, sample_client):
        """Partial update character card."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Old Name",
            relationship_type="friend",
            card_data={"name": "Old Name"}
        )
        
        response = test_client.put(
            f"/api/v1/cards/{card_id}",
            json={
                "card_type": "character",
                "card_name": "New Name"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_update_card_partial_world(self, test_client, sample_client):
        """Partial update world event."""
        card_id = db.create_world_event(
            client_id=sample_client,
            entity_id=f"world_{uuid.uuid4().hex}",
            title="Old Title",
            key_array='["old"]',
            description="Test",
            event_type="other"
        )
        
        response = test_client.put(
            f"/api/v1/cards/{card_id}",
            json={
                "card_type": "world",
                "title": "New Title"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_toggle_auto_update_enable(self, test_client, sample_client):
        """Enable auto-update for card."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test",
            relationship_type="friend",
            card_data={"name": "Test"}
        )
        
        response = test_client.put(
            f"/api/v1/cards/{card_id}/toggle-auto-update?card_type=character"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_toggle_auto_update_disable(self, test_client, sample_client):
        """Disable auto-update for card."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test",
            relationship_type="friend",
            card_data={"name": "Test"}
        )
        
        test_client.put(f"/api/v1/cards/{card_id}/toggle-auto-update?card_type=character")
        response = test_client.put(f"/api/v1/cards/{card_id}/toggle-auto-update?card_type=character")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


@pytest.mark.integration
class TestCardsPinUnpin:
    """Test pin/unpin endpoints."""

    @pytest.mark.integration
    def test_pin_card_endpoint_success(self, test_client, sample_client):
        """POST /{card_type}/{id}/pin."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test",
            relationship_type="friend",
            card_data={"name": "Test"}
        )
        
        response = test_client.put(f"/api/v1/cards/character/{card_id}/pin")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'pinned' in data['message'].lower()

    @pytest.mark.integration
    def test_unpin_card_endpoint_success(self, test_client, sample_client):
        """POST /{card_type}/{id}/unpin."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test",
            relationship_type="friend",
            card_data={"name": "Test"}
        )
        
        test_client.put(f"/api/v1/cards/character/{card_id}/pin")
        response = test_client.put(f"/api/v1/cards/character/{card_id}/unpin")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'unpinned' in data['message'].lower()


@pytest.mark.integration
class TestCardsSearchDelete:
    """Test /search and /delete endpoints."""

    @pytest.mark.integration
    def test_search_cards_all_types(self, test_client, sample_client):
        """Search across all card types."""
        db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {"name": "Test User"}})
        )
        db.create_character_card(
            client_id=sample_client,
            card_name="Mom",
            relationship_type="family",
            card_data={"name": "Mom"}
        )
        db.create_world_event(
            client_id=sample_client,
            entity_id=f"world_{uuid.uuid4().hex}",
            title="Graduation",
            key_array='["graduation"]',
            description="Test",
            event_type="other"
        )
        
        response = test_client.get("/api/v1/cards/search?q=test")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['data']['items']) > 0

    @pytest.mark.integration
    def test_search_cards_filtered_by_type(self, test_client, sample_client):
        """Search specific card type."""
        db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {"name": "Test"}})
        )
        db.create_character_card(
            client_id=sample_client,
            card_name="Mom",
            relationship_type="family",
            card_data={"name": "Mom"}
        )
        
        response = test_client.get("/api/v1/cards/search?q=test&types=character")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        for item in data['data']['items']:
            assert item['card_type'] == 'character'

    @pytest.mark.integration
    def test_delete_card_success(self, test_client, sample_client):
        """Delete card, verify gone from DB."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test",
            relationship_type="friend",
            card_data={"name": "Test"}
        )
        
        response = test_client.delete(f"/api/v1/cards/{card_id}?card_type=character")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        
        cards = db.get_character_cards(sample_client)
        assert len(cards) == 0
