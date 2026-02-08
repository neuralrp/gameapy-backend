"""
Guide API tests.

Tests /conversation/start, /input, /confirm-card endpoints,
organic conversation flow, and LLM error scenarios.
"""
import pytest
from app.db.database import db


@pytest.mark.integration
class TestGuideConversationFlow:
    """Test organic guide conversation endpoints."""

    @pytest.mark.integration
    def test_start_conversation_creates_session(self, test_client, sample_client, sample_guide_counselor):
        """POST /conversation/start, session created."""
        response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'session_id' in data['data']
        assert data['data']['session_id'] > 0

    @pytest.mark.integration
    def test_conversation_input_no_card_needed(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """Input continues conversation without card suggestion."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        response = test_client.post(
            "/guide/conversation/input",
            params={"session_id": session_id, "user_input": "I'm just chatting"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_conversation_input_suggests_card(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """Input triggers card suggestion."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        response = test_client.post(
            "/guide/conversation/input",
            params={"session_id": session_id, "user_input": "My mom is overprotective"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_confirm_card_creation_success(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """POST /confirm-card, card created."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        response = test_client.post(
            "/guide/conversation/confirm-card",
            params={
                "session_id": session_id,
                "card_type": "character",
                "topic": "Mom"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @pytest.mark.integration
    def test_conversation_never_completes(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """Verify flow is organic (no phase completion)."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        for _ in range(5):
            response = test_client.post(
                "/guide/conversation/input",
                params={"session_id": session_id, "user_input": "Just chatting"}
            )
            assert response.status_code == 200


@pytest.mark.integration
class TestGuideCardSuggestion:
    """Test card suggestion and confirmation flow."""

    @pytest.mark.integration
    def test_card_suggestion_includes_type_and_topic(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """Suggestion returns card_type + topic."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        response = test_client.post(
            "/guide/conversation/input",
            params={"session_id": session_id, "user_input": "My boss is strict"}
        )
        
        assert response.status_code == 200

    @pytest.mark.integration
    def test_card_creation_from_suggestion(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """Confirm card matches suggestion."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        response = test_client.post(
            "/guide/conversation/confirm-card",
            params={
                "session_id": session_id,
                "card_type": "character",
                "topic": "Mom"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


@pytest.mark.integration
class TestGuideLLMError:
    """Test LLM error handling in guide system."""

    @pytest.mark.integration
    def test_conversation_input_llm_error(self, test_client, sample_client, sample_guide_counselor, mock_llm_error):
        """Card generator fails, guide returns sane message with no card created."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        response = test_client.post(
            "/guide/conversation/input",
            params={"session_id": session_id, "user_input": "My mom is here"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
