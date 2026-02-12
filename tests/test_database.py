"""
Database CRUD operations tests.

Tests core database functionality, pin/unpin, entity mentions,
sessions, and key constraint violations.
"""
import pytest
import json
import uuid
from app.db.database import db


@pytest.mark.integration
class TestDatabaseCardCRUD:
    """Test card CRUD operations."""

    @pytest.mark.integration
    def test_create_self_card_success(self, sample_client):
        """Create self card and verify ID returned."""
        from app.db.database import db
        card_data = {
            "spec": "gameapy_self_card_v1",
            "data": {
                "name": "Test User",
                "personality": "Curious and open-minded",
                "traits": ["curious"]
            }
        }
        card_id = db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps(card_data)
        )
        
        assert card_id is not None
        assert card_id > 0
        
        card = db.get_self_card_by_id(card_id)
        assert card is not None
        assert card['id'] == card_id
        assert card['client_id'] == sample_client

    @pytest.mark.integration
    def test_create_character_card_success(self, sample_client):
        """Create character card and verify all fields."""
        card_data = {
            "name": "Mom",
            "relationship_type": "family",
            "personality": "Caring but overprotective",
            "patterns": ["worries about grades"]
        }
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Mom",
            relationship_type="family",
            card_data=card_data
        )
        
        assert card_id is not None
        assert card_id > 0
        
        card = db.get_character_cards(sample_client)
        assert len(card) == 1
        assert card[0]['id'] == card_id
        assert card[0]['card_name'] == "Mom"

    @pytest.mark.integration
    def test_create_world_event_success(self, sample_client):
        """Create world event with key_array."""
        card_id = db.create_world_event(
            client_id=sample_client,
            entity_id=f"world_{uuid.uuid4().hex}",
            title="College Graduation",
            key_array='["graduation", "college"]',
            description="Graduated with honors in 2020",
            event_type="achievement"
        )
        
        assert card_id is not None
        assert card_id > 0
        
        event = db.get_world_events(sample_client)
        assert len(event) == 1
        assert event[0]['id'] == card_id
        assert event[0]['title'] == "College Graduation"

    @pytest.mark.integration
    def test_get_self_card_by_id(self, sample_client):
        """Retrieve existing self card."""
        card_id = db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {"name": "Test"}})
        )
        
        card = db.get_self_card_by_id(card_id)
        assert card is not None
        assert card['id'] == card_id

    @pytest.mark.integration
    def test_get_character_card_by_id(self, sample_client):
        """Retrieve existing character card."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Boss",
            relationship_type="coworker",
            card_data={"name": "Boss", "relationship_type": "coworker"}
        )
        
        cards = db.get_character_cards(sample_client)
        assert len(cards) == 1
        assert cards[0]['id'] == card_id

    @pytest.mark.integration
    def test_get_world_event_by_id(self, sample_client):
        """Retrieve existing world event."""
        card_id = db.create_world_event(
            client_id=sample_client,
            entity_id=f"world_{uuid.uuid4().hex}",
            title="Promotion",
            key_array='["work", "promotion"]',
            description="Got promoted to manager",
            event_type="achievement"
        )
        
        events = db.get_world_events(sample_client)
        assert len(events) == 1
        assert events[0]['id'] == card_id

    @pytest.mark.integration
    def test_update_self_card(self, sample_client):
        """Update self card JSON data."""
        card_id = db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {"personality": "Old"}})
        )
        
        success = db.update_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {"personality": "New"}}),
            changed_by='user'
        )
        
        assert success is True
        card = db.get_self_card_by_id(card_id)
        card_json = card['card_json'] if isinstance(card['card_json'], dict) else json.loads(card['card_json'])
        assert card_json['data']['personality'] == "New"

    @pytest.mark.integration
    def test_update_character_card(self, sample_client):
        """Update character card name/relationship."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Old Name",
            relationship_type="friend",
            card_data={"name": "Old Name", "relationship_type": "friend"}
        )
        
        success = db.update_character_card(
            card_id=card_id,
            card_name="New Name",
            relationship_type="family",
            changed_by='user'
        )
        
        assert success is True
        cards = db.get_character_cards(sample_client)
        assert cards[0]['card_name'] == "New Name"
        assert cards[0]['relationship_type'] == "family"

    @pytest.mark.integration
    def test_update_world_event(self, sample_client):
        """Update world event description."""
        card_id = db.create_world_event(
            client_id=sample_client,
            entity_id=f"world_{uuid.uuid4().hex}",
            title="Event",
            key_array='["event"]',
            description="Old description",
            event_type="other"
        )
        
        success = db.update_world_event(
            event_id=card_id,
            description="New description",
            changed_by='user'
        )
        
        assert success is True
        events = db.get_world_events(sample_client)
        assert events[0]['description'] == "New description"


@pytest.mark.integration
class TestDatabasePinUnpin:
    """Test pin/unpin operations."""

    @pytest.mark.integration
    def test_pin_card(self, sample_client):
        """Pin self card, verify is_pinned=True."""
        card_id = db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {}})
        )
        
        success = db.pin_card("self", card_id)
        assert success is True
        
        pinned = db.get_pinned_cards(sample_client)
        assert len(pinned) == 1
        assert pinned[0]['id'] == card_id
        assert pinned[0]['is_pinned'] is True

    @pytest.mark.integration
    def test_unpin_card(self, sample_client):
        """Unpin card, verify removed from pinned list."""
        card_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test",
            relationship_type="friend",
            card_data={"name": "Test"}
        )
        
        db.pin_card("character", card_id)
        pinned_before = db.get_pinned_cards(sample_client)
        assert len(pinned_before) == 1
        
        success = db.unpin_card("character", card_id)
        assert success is True
        
        pinned_after = db.get_pinned_cards(sample_client)
        assert len(pinned_after) == 0

    @pytest.mark.integration
    def test_get_pinned_cards(self, sample_client):
        """Retrieve only pinned cards for client."""
        self_id = db.create_self_card(
            client_id=sample_client,
            card_json=json.dumps({"spec": "gameapy_self_card_v1", "data": {}})
        )
        char_id = db.create_character_card(
            client_id=sample_client,
            card_name="Test",
            relationship_type="friend",
            card_data={"name": "Test"}
        )
        world_id = db.create_world_event(
            client_id=sample_client,
            entity_id=f"world_{uuid.uuid4().hex}",
            title="Event",
            key_array='["event"]',
            description="Test",
            event_type="other"
        )
        
        db.pin_card("character", char_id)
        db.pin_card("world", world_id)
        
        pinned = db.get_pinned_cards(sample_client)
        assert len(pinned) == 2
        pinned_ids = [p['id'] for p in pinned]
        assert char_id in pinned_ids
        assert world_id in pinned_ids
        assert self_id not in pinned_ids


@pytest.mark.integration
class TestDatabaseEntityMentions:
    """Test entity mention logging."""

    @pytest.mark.integration
    def test_add_entity_mention(self, sample_client, sample_session):
        """Log entity mention for session."""
        mention_id = db.add_entity_mention(
            client_id=sample_client,
            session_id=sample_session,
            entity_type="character_card",
            entity_ref="1",
            mention_context="My mom is nagging me"
        )
        
        assert mention_id is not None
        assert mention_id > 0

    @pytest.mark.integration
    def test_get_entity_mentions_by_session(self, sample_client, sample_session):
        """Retrieve mentions for session using direct SQL query."""
        db.add_entity_mention(
            client_id=sample_client,
            session_id=sample_session,
            entity_type="character_card",
            entity_ref="1",
            mention_context="My mom"
        )
        db.add_entity_mention(
            client_id=sample_client,
            session_id=sample_session,
            entity_type="world_card",
            entity_ref="2",
            mention_context="College graduation"
        )
        
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM entity_mentions WHERE session_id = %s",
                (sample_session,)
            )
            mentions = [dict(row) for row in cursor.fetchall()]
        
        assert len(mentions) == 2
        assert mentions[0]['entity_type'] == "character_card"
        assert mentions[1]['entity_type'] == "world_card"


@pytest.mark.integration
class TestDatabaseSessionManagement:
    """Test session management."""

    @pytest.mark.integration
    def test_create_session(self, sample_client, sample_counselor):
        """Create session with client/counselor."""
        session_id = db.create_session(
            client_id=sample_client,
            counselor_id=sample_counselor
        )
        
        assert session_id is not None
        assert session_id > 0
        
        session = db.get_session(session_id)
        assert session is not None
        assert session['client_id'] == sample_client
        assert session['counselor_id'] == sample_counselor

    @pytest.mark.integration
    def test_get_session_messages(self, sample_client, sample_counselor):
        """Retrieve paginated messages."""
        session_id = db.create_session(
            client_id=sample_client,
            counselor_id=sample_counselor
        )
        db.add_message(
            session_id=session_id,
            role="user",
            content="Hello",
            speaker="client"
        )
        db.add_message(
            session_id=session_id,
            role="assistant",
            content="Hi there",
            speaker="counselor"
        )
        
        messages = db.get_session_messages(session_id, limit=10)
        assert len(messages) == 2
        assert messages[0]['role'] == "user"
        assert messages[1]['role'] == "assistant"

    @pytest.mark.integration
    def test_add_message(self, sample_client, sample_counselor):
        """Add user and counselor messages."""
        session_id = db.create_session(
            client_id=sample_client,
            counselor_id=sample_counselor
        )
        
        user_msg_id = db.add_message(
            session_id=session_id,
            role="user",
            content="Hello",
            speaker="client"
        )
        counselor_msg_id = db.add_message(
            session_id=session_id,
            role="assistant",
            content="Hi",
            speaker="counselor"
        )
        
        assert user_msg_id is not None
        assert counselor_msg_id is not None
        assert user_msg_id < counselor_msg_id


@pytest.mark.integration
class TestDatabaseConstraints:
    """Test constraint violations and edge cases."""

    @pytest.mark.integration
    def test_duplicate_entity_id_constraint_world_events(self, sample_client):
        """Attempt to create world event with duplicate entity_id."""
        entity_id = f"world_{uuid.uuid4().hex}"
        
        db.create_world_event(
            client_id=sample_client,
            entity_id=entity_id,
            title="Event 1",
            key_array='["event"]',
            description="First",
            event_type="other"
        )
        
        with pytest.raises(Exception):
            db.create_world_event(
                client_id=sample_client,
                entity_id=entity_id,
                title="Event 2",
                key_array='["event"]',
                description="Second",
                event_type="other"
            )

    @pytest.mark.integration
    def test_foreign_key_violation_nonexistent_client(self, sample_counselor):
        """Session creation fails with invalid client_id (PostgreSQL enforces FKs)."""
        import psycopg2
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            db.create_session(
                client_id=99999,
                counselor_id=sample_counselor
            )

    @pytest.mark.integration
    def test_invalid_card_type_rejected(self):
        """Database method returns False for invalid card_type."""
        result = db.update_auto_update_enabled(
            card_type="invalid_type",
            card_id=1,
            enabled=True
        )
        assert result is False
