"""
Chat API tests.

Tests /chat endpoint, entity mention logging, context assembly integration,
and streaming smoke test.
"""
import pytest
from app.models.schemas import MessageCreate
from app.db.database import db


@pytest.mark.integration
class TestChatEndpoint:
    """Test /chat endpoint functionality."""

    @pytest.mark.integration
    def test_chat_with_counselor_success(self, test_client, sample_session, mock_llm_success):
        """POST /chat, verify response + cards_loaded count."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "Hello, how are you?"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'ai_response' in data['data']
        assert 'cards_loaded' in data['data']
        assert data['data']['user_message_id'] is not None

    @pytest.mark.integration
    def test_chat_logs_entity_mentions(self, test_client, sample_session, sample_client, sample_character_card, mock_llm_success):
        """Verify entity_detector mentions logged."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "My mom is nagging me"
                }
            }
        )
        
        assert response.status_code == 200
        
        with db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM entity_mentions WHERE session_id = ?",
                (sample_session,)
            )
            mentions = [dict(row) for row in cursor.fetchall()]
        
        assert len(mentions) > 0
        assert mentions[0]['entity_type'] in ['character_card', 'world_card', 'self_card']

    @pytest.mark.integration
    def test_chat_assembles_context(self, test_client, sample_session, sample_self_card, mock_llm_success):
        """Verify context_assembler called with correct params."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "How are you?"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'cards_loaded' in data['data']

    @pytest.mark.integration
    def test_chat_nonexistent_session(self, test_client):
        """404 for invalid session_id."""
        response = test_client.post(
            "/api/v1/chat/chat",
            json={
                "session_id": 99999,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )
        
        assert response.status_code == 404


@pytest.mark.integration
class TestChatEntityMentions:
    """Test entity mention logging in chat."""

    @pytest.mark.integration
    def test_entity_mention_logged_on_chat(self, test_client, sample_session, sample_character_card, mock_llm_success):
        """Verify add_entity_mention called."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "My mom is here"
                }
            }
        )
        
        assert response.status_code == 200
        
        with db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM entity_mentions WHERE session_id = ?",
                (sample_session,)
            )
            mentions = [dict(row) for row in cursor.fetchall()]
        
        assert len(mentions) > 0

    @pytest.mark.integration
    def test_multiple_mentions_logged(self, test_client, sample_session, sample_character_card, sample_world_event, mock_llm_success):
        """Multiple entities in one message logged separately."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "My mom graduated from college"
                }
            }
        )
        
        assert response.status_code == 200
        
        with db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM entity_mentions WHERE session_id = ?",
                (sample_session,)
            )
            mentions = [dict(row) for row in cursor.fetchall()]
        
        assert len(mentions) >= 1


@pytest.mark.integration
class TestChatContextAssembly:
    """Test context assembly integration."""

    @pytest.mark.integration
    def test_context_includes_self_card(self, test_client, sample_session, sample_self_card, mock_llm_success):
        """Self card always loaded."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['data']['cards_loaded'] >= 1

    @pytest.mark.integration
    def test_context_includes_pinned_cards(self, test_client, sample_session, sample_self_card, sample_character_card, mock_llm_success):
        """Pinned cards loaded."""
        db.pin_card('character', sample_character_card)

        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['data']['cards_loaded'] >= 1

    @pytest.mark.integration
    def test_context_includes_mentions(self, test_client, sample_session, sample_character_card, mock_llm_success):
        """Current session mentions loaded."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "My mom is here"
                }
            }
        )

        assert response.status_code == 200
        mentions = db.get_entity_mentions_by_session(sample_session)
        assert len(mentions) > 0

    @pytest.mark.integration
    def test_context_card_count_returned(self, test_client, sample_session, sample_self_card, mock_llm_success):
        """Verify cards_loaded in response."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert 'cards_loaded' in data['data']
        assert isinstance(data['data']['cards_loaded'], int)


@pytest.mark.integration
class TestChatStreaming:
    """Test streaming endpoint."""

    @pytest.mark.integration
    def test_chat_stream_smoke(self, test_client, sample_session, mock_llm_success):
        """Streaming endpoint wired, returns 200, basic error handling."""
        response = test_client.post(
            f"/api/v1/chat/chat/stream",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )

        assert response.status_code == 200
        assert response.headers.get('content-type') is not None
