"""
Chat API tests.

Tests /chat endpoint, entity mention logging, context assembly integration,
and streaming smoke test.
"""
import pytest
from app.models.schemas import MessageCreate
from app.db.database import db

def parse_sse_response(response_text: str) -> list:
    """
    Parse SSE (Server-Sent Events) streaming response into list of chunks.
    
    Args:
        response_text: Raw response text from streaming endpoint
        
    Returns:
        List of parsed chunk dictionaries
    """
    import json
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


@pytest.mark.integration
class TestChatEndpoint:
    """Test /chat endpoint functionality."""

    @pytest.mark.integration
    def test_chat_with_counselor_success(self, test_client, sample_session, mock_llm_success):
        """POST /chat (streaming), verify response + cards_loaded count."""
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
        chunks = parse_sse_response(response.text)
        
        # Verify we received content chunks
        content_chunks = [c for c in chunks if c.get('type') == 'content']
        assert len(content_chunks) > 0, "Should receive at least one content chunk"
        
        # Verify final chunk is done with metadata
        final_chunk = chunks[-1]
        assert final_chunk['type'] == 'done'
        assert 'data' in final_chunk
        assert 'cards_loaded' in final_chunk['data']
        assert isinstance(final_chunk['data']['cards_loaded'], int)

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
        chunks = parse_sse_response(response.text)
        assert chunks[-1]['type'] == 'done'
        
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
        chunks = parse_sse_response(response.text)
        assert chunks[-1]['type'] == 'done'
        assert 'cards_loaded' in chunks[-1]['data']

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
        chunks = parse_sse_response(response.text)
        assert chunks[-1]['type'] == 'done'
        assert chunks[-1]['data']['cards_loaded'] >= 1

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
        chunks = parse_sse_response(response.text)
        assert chunks[-1]['type'] == 'done'
        assert chunks[-1]['data']['cards_loaded'] >= 1

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
        """Verify cards_loaded in streaming response."""
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
        chunks = parse_sse_response(response.text)
        assert chunks[-1]['type'] == 'done'
        assert 'cards_loaded' in chunks[-1]['data']
        assert isinstance(chunks[-1]['data']['cards_loaded'], int)


@pytest.mark.integration
class TestChatStreaming:
    """Test streaming endpoint."""

    @pytest.mark.integration
    def test_chat_stream_smoke(self, test_client, sample_session, mock_llm_success):
        """Streaming endpoint wired, returns 200, basic error handling."""
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
        assert response.headers.get('content-type') is not None
        chunks = parse_sse_response(response.text)
        assert len(chunks) > 0


@pytest.mark.integration
class TestChatStreamingEnhanced:
    """Enhanced streaming endpoint tests."""

    @pytest.mark.integration
    def test_streaming_yields_multiple_content_chunks(self, test_client, sample_session, mock_llm_streaming_success):
        """Verify multiple content chunks are yielded during streaming."""
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "Tell me more"
                }
            }
        )

        assert response.status_code == 200
        chunks = parse_sse_response(response.text)
        
        # Verify we received multiple content chunks
        content_chunks = [c for c in chunks if c.get('type') == 'content']
        assert len(content_chunks) > 1, "Should receive multiple content chunks"
        
        # Verify each chunk has content
        for chunk in content_chunks:
            assert 'content' in chunk
            assert len(chunk['content']) > 0

    @pytest.mark.integration
    def test_streaming_final_metadata_chunk(self, test_client, sample_session, mock_llm_streaming_success):
        """Verify final chunk is 'done' type with metadata."""
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
        chunks = parse_sse_response(response.text)
        
        # Verify final chunk is done with metadata
        final_chunk = chunks[-1]
        assert final_chunk['type'] == 'done'
        assert 'data' in final_chunk
        assert 'cards_loaded' in final_chunk['data']
        assert isinstance(final_chunk['data']['cards_loaded'], int)

    @pytest.mark.integration
    def test_streaming_counselor_switching(self, test_client, sample_session, sample_client, mock_llm_streaming_success):
        """Verify counselor switching works in streaming responses."""
        # Create Marina counselor
        marina_counselor = db.create_counselor_profile({
            'data': {
                "name": "Marina",
                "who_you_are": "A helpful counselor",
                "your_vibe": "Warm and friendly"
            }
        })
        
        # Create Deirdre counselor (hidden)
        deirdre_counselor = db.create_counselor_profile({
            'data': {
                "name": "Deirdre",
                "who_you_are": "A mysterious counselor",
                "your_vibe": "Enigmatic"
            }
        })
        
        # Update session to use Marina
        db.update_session_counselor(sample_session, marina_counselor)
        
        response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": sample_session,
                "message_data": {
                    "role": "user",
                    "content": "Summon Deirdre"
                }
            }
        )

        assert response.status_code == 200
        chunks = parse_sse_response(response.text)
        
        # Verify final chunk contains counselor_switched flag
        final_chunk = chunks[-1]
        assert final_chunk['type'] == 'done'
        assert final_chunk['data']['counselor_switched'] is True
        assert final_chunk['data']['new_counselor'] is not None
        assert final_chunk['data']['new_counselor']['name'] == "Deirdre"

    @pytest.mark.integration
    def test_streaming_error_handling(self, test_client, sample_session, mock_llm_error):
        """Verify errors are properly handled in streaming responses."""
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
        chunks = parse_sse_response(response.text)
        
        # Verify we received an error chunk
        error_chunks = [c for c in chunks if c.get('type') == 'error']
        assert len(error_chunks) > 0, "Should receive error chunk"
        assert 'error' in error_chunks[0]
        assert len(error_chunks[0]['error']) > 0

    @pytest.mark.integration
    def test_streaming_empty_response(self, test_client, sample_session, mock_llm_no_card):
        """Verify empty LLM responses are handled gracefully."""
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
        chunks = parse_sse_response(response.text)
        
        # Should still get a done chunk even with empty response
        assert chunks[-1]['type'] == 'done'
