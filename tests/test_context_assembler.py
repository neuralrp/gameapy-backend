import pytest
from app.services.context_assembler import context_assembler
from app.db.database import db
import json


@pytest.mark.integration
class TestContextAssembler:
    """Test context assembly and loading priorities."""
    
    @pytest.mark.integration
    def test_always_loads_self_card(self, sample_client, sample_session, sample_self_card):
        """Test self card is always loaded."""
        client_id = sample_client
        session_id = sample_session
        
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=session_id,
            user_message="test"
        )
        
        assert context['self_card'] is not None
        assert context['self_card']['card_type'] == 'self'
        assert context['total_cards_loaded'] >= 1
    
    @pytest.mark.integration
    def test_pinned_cards_loaded(self, sample_client, sample_session, sample_character_card):
        """Test pinned cards are always loaded."""
        client_id = sample_client
        
        # Pin the character card
        mom_id = sample_character_card
        db.pin_card('character', mom_id)
        
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=sample_session,
            user_message="test"
        )
        
        pinned_ids = [c['id'] for c in context['pinned_cards']]
        assert len(pinned_ids) > 0
        assert context['total_cards_loaded'] >= 1
    
    @pytest.mark.integration
    def test_pinned_cards_not_in_recent(self, sample_client, sample_session, sample_self_card, sample_character_card):
        """Test pinned cards excluded from recent list."""
        client_id = sample_client
        
        # Pin the character card
        mom_id = sample_character_card
        db.pin_card('character', mom_id)
        
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=sample_session,
            user_message="test"
        )
        
        pinned_ids = {c['id'] for c in context['pinned_cards']}
        recent_ids = {c['id'] for c in context['recent_cards']}
        
        # No overlap between pinned and recent
        assert len(pinned_ids.intersection(recent_ids)) == 0
    
    @pytest.mark.integration
    def test_current_session_mentions_loaded(self, sample_client, sample_session, sample_self_card):
        """Test cards mentioned in current session are loaded."""
        client_id = sample_client
        
        # Create Dad card
        dad_id = db.create_character_card(
            client_id=client_id,
            card_name="Dad",
            relationship_type="family",
            card_data={"name": "Dad", "relationship_type": "family"}
        )
        
        # Log mention in current session
        db.add_entity_mention(
            client_id=client_id,
            session_id=sample_session,
            entity_type="character_card",
            entity_ref=str(dad_id),
            mention_context="Dad was here"
        )
        
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=sample_session,
            user_message="test"
        )
        
        mention_ids = [c['id'] for c in context['current_mentions']]
        assert dad_id in mention_ids
        assert context['total_cards_loaded'] >= 1
    
    @pytest.mark.integration
    def test_recent_cards_limit_respected(self, sample_client, sample_session, sample_counselor, sample_self_card, monkeypatch):
        """Test that recent_card_session_limit is respected."""
        client_id = sample_client
        
        # Mock config to look back 2 sessions
        from app.core.config import settings
        monkeypatch.setattr(settings, 'recent_card_session_limit', 2)
        
        # Create 3 cards mentioned in 3 different sessions
        for i in range(3):
            card_id = db.create_character_card(
                client_id=client_id,
                card_name=f"Person{i}",
                relationship_type="friend",
                card_data={"name": f"Person{i}", "relationship_type": "friend"}
            )
            # Create actual session for each mention
            session_id = db.create_session(client_id=client_id, counselor_id=sample_counselor)
            # Mention in different session
            db.add_entity_mention(
                client_id=client_id,
                session_id=session_id,
                entity_type="character_card",
                entity_ref=str(card_id),
                mention_context=f"Person{i}"
            )
        
        # Assemble context from a new session
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=sample_session,
            user_message="test"
        )
        
        # Should only load cards from last 2 sessions
        assert len(context['recent_cards']) <= 2
    
    @pytest.mark.integration
    def test_total_cards_counted_correctly(self, sample_client, sample_session, sample_self_card, sample_character_card):
        """Test total cards loaded is accurate."""
        client_id = sample_client
        
        # Pin the character card
        mom_id = sample_character_card
        db.pin_card('character', mom_id)
        
        # Create unpinned card
        friend_id = db.create_character_card(
            client_id=client_id,
            card_name="Friend",
            relationship_type="friend",
            card_data={"name": "Friend", "relationship_type": "friend"}
        )
        
        # Log mention in current session
        db.add_entity_mention(
            client_id=client_id,
            session_id=sample_session,
            entity_type="character_card",
            entity_ref=str(friend_id),
            mention_context="Friend was here"
        )
        
        context = context_assembler.assemble_context(
            client_id=client_id,
            session_id=sample_session,
            user_message="test"
        )
        
        # Total = 1 (self) + 1 (pinned) + 1 (current) + X (recent)
        expected_min = 1 + 1 + 1  # self + pinned + current
        assert context['total_cards_loaded'] >= expected_min
