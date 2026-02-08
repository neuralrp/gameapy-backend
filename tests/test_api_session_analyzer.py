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
    def test_analyze_session_success(self, test_client, sample_session, sample_self_card, sample_character_card, mock_llm_success):
        """Valid session with messages returns cards_updated."""
        db.add_message(
            session_id=sample_session,
            role="user",
            content="I'm feeling stressed",
            speaker="client"
        )
        db.add_message(
            session_id=sample_session,
            role="assistant",
            content="Tell me more",
            speaker="counselor"
        )
        
        response = test_client.post(f"/api/v1/sessions/{sample_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'cards_updated' in data['data']

    @pytest.mark.integration
    def test_analyze_session_respects_auto_update_toggle(self, test_client, sample_session, sample_character_card, mock_llm_success):
        """Cards with auto_update_enabled=False are not modified."""
        db.update_auto_update_enabled(
            card_type='character',
            card_id=sample_character_card,
            enabled=False
        )
        
        db.add_message(
            session_id=sample_session,
            role="user",
            content="My mom is here",
            speaker="client"
        )
        
        response = test_client.post(f"/api/v1/sessions/{sample_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_analyze_session_invalid_session(self, test_client):
        """Invalid session_id returns clean error, no DB mutations."""
        response = test_client.post("/api/v1/sessions/99999/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'not found' in data['message'].lower()

    @pytest.mark.integration
    def test_analyze_session_empty_session(self, test_client, sample_session):
        """Handles empty message history gracefully."""
        response = test_client.post(f"/api/v1/sessions/{sample_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'cards_updated' in data['data']

    @pytest.mark.integration
    def test_analyze_session_llm_error(self, test_client, sample_session, mock_llm_error):
        """Uses mock_llm_error, returns error without partial DB mutations."""
        db.add_message(
            session_id=sample_session,
            role="user",
            content="Test message",
            speaker="client"
        )
        
        response = test_client.post(f"/api/v1/sessions/{sample_session}/analyze")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
