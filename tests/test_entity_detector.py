import pytest
import uuid
from app.services.entity_detector import entity_detector
from app.db.database import db


@pytest.mark.unit
class TestEntityDetector:
    """Test entity detection with improved keyword matching."""

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
    def test_relationship_label_specific_matching(self, sample_client):
        """Test specific matching using relationship_label."""
        client_id = sample_client

        # Create Paula card with custom label "Sister"
        paula_id = db.create_character_card(
            client_id=client_id,
            card_name="Paula",
            relationship_type="family",
            relationship_label="Sister",
            card_data={"name": "Paula", "relationship_type": "family"}
        )

        # Create Dad card (no label)
        dad_id = db.create_character_card(
            client_id=client_id,
            card_name="Dad",
            relationship_type="family",
            card_data={"name": "Dad", "relationship_type": "family"}
        )

        # "Sister" should only match Paula, not Dad
        mentions = entity_detector.detect_mentions("My sister is driving me crazy", client_id)

        # Should match Paula by label
        paula_mention = next((m for m in mentions if m['card_id'] == paula_id), None)
        assert paula_mention is not None
        assert paula_mention['match_type'] == 'label'

        # Should NOT match Dad
        dad_mention = next((m for m in mentions if m['card_id'] == dad_id), None)
        assert dad_mention is None

    @pytest.mark.unit
    def test_word_boundary_prevents_false_positives(self, sample_client):
        """Test that word boundaries prevent substring false matches."""
        client_id = sample_client

        # Create achievement event
        event_id = db.create_world_event(
            client_id=client_id,
            entity_id=f"event_{uuid.uuid4().hex}",
            title="My achievement",
            key_array='["success", "milestone"]',
            description="A big achievement",
            event_type="achievement",
            is_canon_law=False,
            resolved=False
        )

        # "achievement" should match the event
        mentions = entity_detector.detect_mentions("I'm proud of my achievement", client_id)
        event_mention = next((m for m in mentions if m['card_id'] == event_id), None)
        assert event_mention is not None

        # "overachievements" should NOT match "achievement" (word boundary)
        mentions2 = entity_detector.detect_mentions("My overachievements are stressing me out", client_id)
        event_mention2 = next((m for m in mentions2 if m['card_id'] == event_id), None)
        assert event_mention2 is None

    @pytest.mark.unit
    def test_possessive_stripping(self, sample_client):
        """Test that possessives are stripped for matching."""
        client_id = sample_client

        # Create Wife card
        wife_id = db.create_character_card(
            client_id=client_id,
            card_name="Wife",
            relationship_type="romantic",
            card_data={"name": "Wife", "relationship_type": "romantic"}
        )

        # "Wife's" should match "Wife"
        mentions = entity_detector.detect_mentions("My wife's car broke down", client_id)
        wife_mention = next((m for m in mentions if m['card_id'] == wife_id), None)
        assert wife_mention is not None
        assert wife_mention['match_type'] == 'name'

    @pytest.mark.unit
    def test_plural_normalization(self, sample_client):
        """Test that common plurals are normalized."""
        client_id = sample_client

        # Create College event
        event_id = db.create_world_event(
            client_id=client_id,
            entity_id=f"event_{uuid.uuid4().hex}",
            title="College",
            key_array='["graduation"]',
            description="College graduation",
            event_type="achievement",
            is_canon_law=False,
            resolved=False
        )

        # "colleges" should match "College"
        mentions = entity_detector.detect_mentions("I applied to 2 colleges", client_id)
        event_mention = next((m for m in mentions if m['card_id'] == event_id), None)
        assert event_mention is not None

    @pytest.mark.unit
    def test_event_type_matching(self, sample_client):
        """Test that event_type is matched for world events."""
        client_id = sample_client

        import uuid

        # Create achievement events
        grad_id = db.create_world_event(
            client_id=client_id,
            entity_id=f"event_{uuid.uuid4().hex}",
            title="College graduation",
            key_array='["graduation"]',
            description="Graduated from college",
            event_type="achievement",
            is_canon_law=False,
            resolved=False
        )

        promo_id = db.create_world_event(
            client_id=client_id,
            entity_id=f"event_{uuid.uuid4().hex}",
            title="Job promotion",
            key_array='["promotion", "work"]',
            description="Got promoted",
            event_type="achievement",
            is_canon_law=False,
            resolved=False
        )

        # "achievement" should match ALL achievement-type events
        mentions = entity_detector.detect_mentions("I'm proud of my achievements", client_id)
        achievement_mentions = [m for m in mentions if m['match_type'] == 'event_type']

        assert len(achievement_mentions) == 2
        matched_ids = {m['card_id'] for m in achievement_mentions}
        assert grad_id in matched_ids
        assert promo_id in matched_ids

    @pytest.mark.unit
    def test_keyword_matching_family(self, sample_client):
        """Test family keyword matching (broad category)."""
        client_id = sample_client

        # Create Dad card (no custom label)
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
