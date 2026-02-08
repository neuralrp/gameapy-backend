import pytest
import importlib
import sys
from app.services.guide_system import guide_system
from app.db.database import db


@pytest.mark.integration
class TestGuideSystem:
    """Test organic guide conversation system."""
    
    @pytest.mark.integration
    async def test_start_conversation_creates_session(self, sample_client, sample_guide_counselor, mock_card_generator_success):
        """Test starting conversation creates new session."""
        # Reload guide_system to ensure it picks up mocked card_generator
        import app.services.guide_system as gs_module
        importlib.reload(gs_module)
        client_id = sample_client
        
        result = await guide_system.start_conversation(client_id)
        
        assert 'session_id' in result
        assert result['client_id'] == client_id
        assert 'guide_message' in result
        
        # Verify session exists
        session = db.get_session(result['session_id'])
        assert session is not None
        assert session['client_id'] == client_id
    
    @pytest.mark.integration
    async def test_conversation_suggests_card_when_appropriate(
        self, 
        sample_client, 
        sample_guide_counselor,
        mock_card_generator_success
    ):
        """Test guide suggests card for new topics."""
        client_id = sample_client
        session_id = db.create_session(
            client_id=client_id,
            counselor_id=sample_guide_counselor
        )
        
        # User mentions new person
        result = await guide_system.process_conversation(
            session_id=session_id,
            user_input="My boss is being really difficult lately"
        )
        
        # Should suggest card
        assert result['suggested_card'] is not None
        if result['suggested_card']:
            assert result['suggested_card']['card_type'] in ['character', 'world', 'self']
        assert result['conversation_complete'] is False
    
    @pytest.mark.integration
    async def test_conversation_continues_naturally_when_no_card_needed(
        self,
        sample_client,
        sample_guide_counselor,
        mock_llm_no_card
    ):
        """Test guide continues naturally when no card-worthy topic."""
        client_id = sample_client
        session_id = db.create_session(
            client_id=client_id,
            counselor_id=sample_guide_counselor
        )
        
        # Generic message
        result = await guide_system.process_conversation(
            session_id=session_id,
            user_input="I'm just feeling a bit anxious today"
        )
        
        # Should NOT suggest card
        assert result['suggested_card'] is None
        assert 'guide_message' in result
        assert len(result['guide_message']) > 0
        assert result['conversation_complete'] is False
    
    @pytest.mark.integration
    async def test_confirm_card_creation_creates_card(
        self, 
        sample_client, 
        sample_guide_counselor,
        mock_card_generator_success
    ):
        """Test confirming suggestion creates actual card."""
        client_id = sample_client
        session_id = db.create_session(
            client_id=client_id,
            counselor_id=sample_guide_counselor
        )
        
        # Confirm card creation
        result = await guide_system.confirm_card_creation(
            session_id=session_id,
            card_type="character",
            topic="My boss, John, is demanding"
        )
        
        assert 'card_id' in result
        assert 'card_data' in result
        assert 'guide_message' in result
        
        # Verify card exists
        char_cards = db.get_character_cards(client_id)
        assert len(char_cards) > 0
    
    @pytest.mark.integration
    async def test_conversation_never_completes(
        self, 
        sample_client, 
        sample_guide_counselor,
        mock_card_generator_success
    ):
        """Test conversation_complete is always False (no phases)."""
        client_id = sample_client
        session_id = db.create_session(
            client_id=client_id,
            counselor_id=sample_guide_counselor
        )
        
        # Multiple messages
        for _ in range(5):
            await guide_system.process_conversation(
                session_id=session_id,
                user_input="Just chatting"
            )
        
        # conversation_complete should always be False
        result = await guide_system.process_conversation(
            session_id=session_id,
            user_input="Final message"
        )
        
        assert result['conversation_complete'] is False
    
    @pytest.mark.integration
    async def test_farm_suggested_after_sessions(
        self, 
        sample_client, 
        sample_guide_counselor,
        mock_card_generator_success
    ):
        """Test farm suggested after 5+ sessions."""
        client_id = sample_client
        
        # Create 5 sessions
        for _ in range(5):
            db.create_session(client_id=client_id, counselor_id=sample_guide_counselor)
        
        # Start new conversation
        session_id = db.create_session(client_id=client_id, counselor_id=sample_guide_counselor)
        
        # Process message
        result = await guide_system.process_conversation(
            session_id=session_id,
            user_input="How are you?"
        )
        
        # Check messages for farm suggestion
        messages = db.get_session_messages(session_id)
        has_farm_suggestion = any(
            'garden' in msg.get('content', '').lower()
            for msg in messages
        )
        
        assert has_farm_suggestion
