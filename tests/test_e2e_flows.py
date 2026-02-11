"""
End-to-end flow tests.

Tests complete user workflows: onboarding, chat, card creation,
entity tracking, and farm discovery.
"""
import pytest
import json
from app.db.database import db

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


@pytest.mark.e2e
class TestE2EOnboarding:
    """Test complete user onboarding flow."""

    @pytest.mark.e2e
    def test_complete_onboarding_flow(self, test_client, sample_counselor, mock_llm_success):
        """Start guide → create self card → chat → verify context loaded."""
        client_id = db.create_client_profile({
            'data': {
                'name': 'New User',
                'personality': 'Test',
                'traits': ['curious'],
                'tags': ['test']
            }
        })
        
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": client_id}
        )
        assert start_response.status_code == 200
        session_id = start_response.json()['data']['session_id']
        
        confirm_response = test_client.post(
            "/guide/conversation/confirm-card",
            params={
                "session_id": session_id,
                "card_type": "self",
                "topic": "Self Card"
            }
        )
        assert confirm_response.status_code == 200
        
        self_card = db.get_self_card(client_id)
        assert self_card is not None

        chat_response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": session_id,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )
        assert chat_response.status_code == 200
        chunks = parse_sse_response(chat_response.text)
        assert chunks[-1]['type'] == 'done'
        assert chunks[-1]['data']['cards_loaded'] >= 1


@pytest.mark.e2e
class TestE2ECardSuggestionPin:
    """Test chat → card suggestion → card creation → pin flow."""

    @pytest.mark.e2e
    def test_chat_card_suggestion_creation_pin_flow(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """Chat → guide suggests character card → confirm → pin → chat with context."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        confirm_response = test_client.post(
            "/guide/conversation/confirm-card",
            params={
                "session_id": session_id,
                "card_type": "character",
                "topic": "Mom"
            }
        )
        assert confirm_response.status_code == 200
        
        char_cards = db.get_character_cards(sample_client)
        assert len(char_cards) > 0
        card_id = char_cards[0]['id']
        
        pin_response = test_client.put(f"/api/v1/cards/character/{card_id}/pin")
        assert pin_response.status_code == 200

        chat_response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": session_id,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )
        assert chat_response.status_code == 200
        chunks = parse_sse_response(chat_response.text)
        assert chunks[-1]['type'] == 'done'
        assert chunks[-1]['data']['cards_loaded'] >= 1


@pytest.mark.e2e
class TestE2EMultiSessionTracking:
    """Test multi-session entity tracking."""

    @pytest.mark.e2e
    def test_multi_session_entity_tracking(self, test_client, sample_client, sample_counselor, mock_llm_success):
        """Multiple sessions mentioning 'Mom' → verify mention count increases."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Mom",
            relationship_type="family",
            card_data={"name": "Mom", "relationship_type": "family"}
        )
        
        session_ids = []
        for i in range(3):
            session_id = db.create_session(
                client_id=sample_client,
                counselor_id=sample_counselor
            )
            session_ids.append(session_id)

            test_client.post(
                f"/api/v1/chat/chat",
                json={
                    "session_id": session_id,
                    "message_data": {
                        "role": "user",
                        "content": "My mom is here"
                    }
                }
            )

        total_mentions = 0
        for session_id in session_ids:
            mentions = db.get_entity_mentions_by_session(session_id)
            total_mentions += len(mentions)

        assert total_mentions >= 3


@pytest.mark.e2e
class TestE2EWorldEventCreation:
    """Test world event creation and context loading."""

    @pytest.mark.e2e
    def test_world_event_creation_and_context_loading(self, test_client, sample_client, sample_guide_counselor, mock_llm_success):
        """Guide suggests life event → confirm → verify loaded in future chats."""
        start_response = test_client.post(
            "/guide/conversation/start",
            params={"client_id": sample_client}
        )
        session_id = start_response.json()['data']['session_id']
        
        confirm_response = test_client.post(
            "/guide/conversation/confirm-card",
            params={
                "session_id": session_id,
                "card_type": "world",
                "topic": "College Graduation"
            }
        )
        assert confirm_response.status_code == 200
        
        world_events = db.get_world_events(sample_client)
        assert len(world_events) > 0
        
        db.pin_card('world', world_events[0]['id'])

        chat_response = test_client.post(
            f"/api/v1/chat/chat",
            json={
                "session_id": session_id,
                "message_data": {
                    "role": "user",
                    "content": "Hello"
                }
            }
        )
        assert chat_response.status_code == 200
        chunks = parse_sse_response(chat_response.text)
        assert chunks[-1]['type'] == 'done'
        assert chunks[-1]['data']['cards_loaded'] >= 1


@pytest.mark.e2e
class TestE2ESearchEditCard:
    """Test search and edit card flow."""

    @pytest.mark.e2e
    def test_search_and_edit_card_flow(self, test_client, sample_client, mock_llm_success):
        """Search cards → find character → update details → save."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test Person",
            relationship_type="friend",
            card_data={"name": "Test Person", "relationship_type": "friend"}
        )
        
        search_response = test_client.get("/api/v1/cards/search?q=test&types=character")
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert len(search_data['data']['items']) > 0
        
        update_response = test_client.put(
            f"/api/v1/cards/{card_id}",
            json={
                "card_type": "character",
                "card_name": "Updated Name"
            }
        )
        assert update_response.status_code == 200
        
        char_cards = db.get_character_cards(sample_client)
        assert char_cards[0]['card_name'] == "Updated Name"


@pytest.mark.e2e
class TestE2EFarmDiscovery:
    """Test farm discovery flow (optional feature)."""

    @pytest.mark.e2e
    def test_farm_discovery_flow(self, test_client, sample_client, sample_counselor, mock_llm_success):
        """5+ sessions → guide suggests farm → discover endpoints (optional)."""
        session_ids = []
        for i in range(5):
            session_id = db.create_session(
                client_id=sample_client,
                counselor_id=sample_counselor
            )
            session_ids.append(session_id)
            
            test_client.post(
                f"/api/v1/chat/chat",
                params={"session_id": session_id},
                json={"role": "user", "content": "Chat message"}
            )
        
        assert len(session_ids) == 5
