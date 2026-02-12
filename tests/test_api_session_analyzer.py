"""
Session Analyzer API tests.

Tests /sessions/{id}/analyze endpoint for auto-update system,
respect for toggles, error handling, and LLM error scenarios.
"""
import pytest
import json
from app.db.database import db


@pytest.mark.integration
class TestSessionAnalyzer:
    """Test session analysis endpoint."""

    @pytest.mark.integration
    def test_analyze_session_success(self, test_client_with_auth, auth_session, auth_self_card, auth_character_card, mock_llm_success):
        """Valid session with messages returns cards_updated."""
        db.add_message(
            session_id=auth_session,
            role="user",
            content="I'm feeling stressed",
            speaker="client"
        )
        db.add_message(
            session_id=auth_session,
            role="assistant",
            content="Tell me more",
            speaker="counselor"
        )
        
        response = test_client_with_auth.post(f"/api/v1/sessions/{auth_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'cards_updated' in data['data']

    @pytest.mark.integration
    def test_analyze_session_respects_auto_update_toggle(self, test_client_with_auth, auth_session, auth_character_card, mock_llm_success):
        """Cards with auto_update_enabled=False are not modified."""
        db.update_auto_update_enabled(
            card_type='character',
            card_id=auth_character_card,
            enabled=False
        )
        
        db.add_message(
            session_id=auth_session,
            role="user",
            content="My mom is here",
            speaker="client"
        )
        
        response = test_client_with_auth.post(f"/api/v1/sessions/{auth_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_analyze_session_invalid_session(self, test_client_with_auth):
        """Invalid session_id returns clean error, no DB mutations."""
        response = test_client_with_auth.post("/api/v1/sessions/99999/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'not found' in data['message'].lower()

    @pytest.mark.integration
    def test_analyze_session_empty_session(self, test_client_with_auth, auth_session):
        """Handles empty message history gracefully."""
        response = test_client_with_auth.post(f"/api/v1/sessions/{auth_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'cards_updated' in data['data']

    @pytest.mark.integration
    def test_analyze_session_creates_self_card_when_missing(self, test_client_with_auth, auth_session, sample_user, mock_llm_success):
        """Auto-create self card if missing before updates."""
        db.add_message(
            session_id=auth_session,
            role="user",
            content="I'm learning how to handle stress lately.",
            speaker="client"
        )

        response = test_client_with_auth.post(f"/api/v1/sessions/{auth_session}/analyze")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        self_card = db.get_self_card(sample_user)
        assert self_card is not None

    @pytest.mark.integration
    def test_analyze_session_creates_character_card_from_updates(self, test_client_with_auth, auth_session, sample_user, auth_self_card, monkeypatch):
        """Auto-create character card when LLM proposes a new person."""
        class MockUpdateClient:
            async def chat_completion(self, messages, model="mock-model", temperature=0.7, max_tokens=1000, **kwargs):
                return {
                    "choices": [{
                        "message": {
                            "content": json.dumps({
                                "confidence": 0.9,
                                "updates": [],
                                "new_cards": [
                                    {
                                        "card_type": "character",
                                        "name": "Avery",
                                        "relationship_type": "friend",
                                        "relationship_label": "Close friend",
                                        "personality": "Supportive"
                                    }
                                ]
                            })
                        }
                    }]
                }

        import app.services.card_updater as card_updater_module
        monkeypatch.setattr(card_updater_module, 'simple_llm_client', MockUpdateClient(), raising=False)

        db.add_message(
            session_id=auth_session,
            role="user",
            content="I was talking with my friend Avery today.",
            speaker="client"
        )

        response = test_client_with_auth.post(f"/api/v1/sessions/{auth_session}/analyze")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        character_cards = db.get_character_cards(sample_user)
        names = [card['card_name'] for card in character_cards]
        assert "Avery" in names

    @pytest.mark.integration
    def test_analyze_session_llm_error(self, test_client_with_auth, auth_session, mock_llm_error):
        """Uses mock_llm_error, returns error without partial DB mutations."""
        db.add_message(
            session_id=auth_session,
            role="user",
            content="Test message",
            speaker="client"
        )
        
        response = test_client_with_auth.post(f"/api/v1/sessions/{auth_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
