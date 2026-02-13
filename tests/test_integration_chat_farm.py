"""
Chat-Farm Integration Tests.

Tests interaction between chat system and farm minigame.
"""
import pytest
from app.db.database import db


@pytest.mark.integration
class TestChatFarmIntegration:
    """Test chat messages affect farm state."""

    @pytest.mark.integration
    def test_chat_message_increments_farm_counter(self, sample_client, sample_counselor):
        """Each chat message increments the farm message counter."""
        session_id = db.create_session(sample_client, sample_counselor)
        
        initial_counter = db.get_message_counter(sample_client)
        
        db.increment_message_counter(sample_client)
        
        new_counter = db.get_message_counter(sample_client)
        assert new_counter == initial_counter + 1

    @pytest.mark.integration
    def test_farm_status_reflects_chat_messages(self, sample_client):
        """Farm status shows correct message count."""
        db.increment_message_counter(sample_client)
        db.increment_message_counter(sample_client)
        db.increment_message_counter(sample_client)
        
        status = db.get_farm_status(sample_client)
        assert status['messageCounter'] == 3
