import pytest
from app.services.entity_detector import entity_detector
from app.db.database import db


@pytest.mark.unit
class TestEntityDetector:
    """Test entity detection with keyword matching."""
    
    @pytest.mark.unit
    def test_name_matching_exact(self, sample_client):
        """Test exact card name match."""
        client_id = sample_client
        
        # Create Mom card
        mom_id = db.create_character_card(
            client_id=client_id,
            card_name="Mom",
            relationship_type="family",
            card_data={"name": "Mom", "relationship_type": "family"}
        )
        
        # Test message
        mentions = entity_detector.detect_mentions("My mom is nagging me", client_id)
        
        assert len(mentions) >= 1
        mom_mention = next(m for m in mentions if m['card_id'] == mom_id)
        assert mom_mention['card_id'] == mom_id
        assert mom_mention['card_type'] == 'character'
        assert mom_mention['match_type'] == 'name'
    
    @pytest.mark.unit
    def test_name_matching_case_insensitive(self, sample_client):
        """Test case-insensitive name matching."""
        client_id = sample_client
        
        # Create Boss card
        boss_id = db.create_character_card(
            client_id=client_id,
            card_name="Boss",
            relationship_type="coworker",
            card_data={"name": "Boss", "relationship_type": "coworker"}
        )
        
        mentions = entity_detector.detect_mentions("I hate my BOSS", client_id)
        
        boss_mention = next(m for m in mentions if m['card_id'] == boss_id)
        assert boss_mention['card_id'] == boss_id
        assert boss_mention['match_type'] == 'name'
    
    @pytest.mark.unit
    def test_keyword_matching_family(self, sample_client):
        """Test family keyword matching."""
        client_id = sample_client
        
        # Create Dad card
        dad_id = db.create_character_card(
            client_id=client_id,
            card_name="Dad",
            relationship_type="family",
            card_data={"name": "Dad", "relationship_type": "family"}
        )
        
        mentions = entity_detector.detect_mentions(
            "My father is really distant",
            client_id
        )
        
        dad_mention = next(m for m in mentions if m['card_id'] == dad_id)
        assert dad_mention['card_id'] == dad_id
        assert dad_mention['match_type'] == 'keyword'
    
    @pytest.mark.unit
    def test_keyword_matching_work(self, sample_client):
        """Test work keyword matching."""
        client_id = sample_client
        
        # Create manager card
        manager_id = db.create_character_card(
            client_id=client_id,
            card_name="Sarah",
            relationship_type="coworker",
            card_data={"name": "Sarah", "relationship_type": "coworker"}
        )
        
        mentions = entity_detector.detect_mentions(
            "My manager keeps changing my schedule",
            client_id
        )
        
        manager_mention = next(m for m in mentions if m['card_id'] == manager_id)
        assert manager_mention['card_id'] == manager_id
        assert manager_mention['match_type'] == 'keyword'
    
    @pytest.mark.unit
    def test_world_event_title_match(self, sample_client, sample_world_event):
        """Test life event title matching."""
        client_id = sample_client
        
        mentions = entity_detector.detect_mentions(
            "My college graduation was a big moment",
            client_id
        )
        
        # Should find the graduation event
        event_mention = next(m for m in mentions if m['card_type'] == 'world')
        assert event_mention['card_type'] == 'world'
        assert event_mention['match_type'] == 'title'
    
    @pytest.mark.unit
    def test_no_match_returns_empty(self, sample_client):
        """Test that no matches returns empty list."""
        client_id = sample_client
        
        mentions = entity_detector.detect_mentions(
            "I went to the store today",
            client_id
        )
        
        assert len(mentions) == 0
    
    @pytest.mark.unit
    def test_duplicate_card_ids_deduplicated(self, sample_client):
        """Test that duplicate mentions are deduplicated."""
        client_id = sample_client
        
        # Create Mom card
        mom_id = db.create_character_card(
            client_id=client_id,
            card_name="Mom",
            relationship_type="family",
            card_data={"name": "Mom", "relationship_type": "family"}
        )
        
        mentions = entity_detector.detect_mentions(
            "My mom and my mother are the same person",
            client_id
        )
        
        # Should match once even though "mom" and "mother" both hit
        mom_mentions = [m for m in mentions if m['card_id'] == mom_id]
        assert len(mom_mentions) == 1
        assert mom_mentions[0]['match_type'] == 'name'
