"""
Phase 1 Test Script
Tests database methods and Pydantic models for Phase 1 features
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import Database
from app.models.schemas import SelfCard, WorldEvent, EntityMention, CharacterCard


def test_database_methods():
    """Test database methods for Phase 1."""
    print("="*60)
    print("Testing Database Methods")
    print("="*60)

    db = Database("gameapy.db")

    # First, create a test client and session
    print("\n--- Creating test client and session ---")
    try:
        client_id = db.create_client_profile({
            'data': {
                'name': 'Test User',
                'personality': 'Test personality',
                'traits': ['test'],
                'presenting_issues': [],
                'goals': [],
                'life_events': [],
                'preferences': {}
            }
        })
        print(f"[OK] Created client (id={client_id})")
    except Exception as e:
        print(f"[ERROR] Failed to create client: {e}")
        return False

    # Create test session
    try:
        session_id = db.create_session(client_id, 1)
        print(f"[OK] Created session (id={session_id})")
    except Exception as e:
        print(f"[ERROR] Failed to create session: {e}")
        return False

    # Test 1: Create self card
    print("\n--- Test 1: Create Self Card ---")
    try:
        self_card_json = json.dumps({
            "spec": "gameapy_self_card_v1",
            "spec_version": "1.0",
            "data": {
                "name": "Test User",
                "personality": "Perfectionist, people-pleaser",
                "interests": ["guitar", "golf"],
                "triggers": ["conflict"]
            }
        })
        card_id = db.create_self_card(client_id, self_card_json, auto_update_enabled=True)
        print(f"[OK] Created self card (id={card_id})")

        self_card = db.get_self_card(client_id)
        assert self_card is not None, "Self card not found"
        # SQLite returns booleans as integers (0 or 1)
        assert self_card['auto_update_enabled'] in [True, 1]
        print(f"[OK] Retrieved self card: {self_card['id']}")
    except Exception as e:
        print(f"[ERROR] Self card test failed: {e}")
        return False

    # Test 2: Create world event
    print("\n--- Test 2: Create World Event ---")
    try:
        import time
        event_id = db.create_world_event(
            client_id=client_id,
            entity_id=f"evt_test_{int(time.time())}",  # Use unique ID
            title="Test Event",
            key_array='["test", "event"]',
            description="Test description",
            event_type="achievement",
            is_canon_law=True,
            auto_update_enabled=True
        )
        print(f"[OK] Created world event (id={event_id})")

        events = db.get_world_events(client_id, canon_law_only=True)
        assert len(events) > 0, "No world events found"
        # SQLite returns booleans as integers (0 or 1)
        assert events[0]['is_canon_law'] in [True, 1]
        print(f"[OK] Retrieved {len(events)} canon law events")
    except Exception as e:
        print(f"[ERROR] World event test failed: {e}")
        return False

    # Test 3: Create character card (with new fields)
    print("\n--- Test 3: Create Character Card ---")
    try:
        char_card_json = json.dumps({
            "spec": "gameapy_character_card_v1",
            "data": {
                "name": "Mom",
                "relationship_type": "family",
                "personality": "Overprotective"
            }
        })
        char_id = db.create_character_card(
            client_id=client_id,
            card_name="Mom",
            relationship_type="family",
            card_data=json.loads(char_card_json)
        )
        print(f"[OK] Created character card (id={char_id})")
    except Exception as e:
        print(f"[ERROR] Character card test failed: {e}")
        return False

    # Test 4: Add entity mentions
    print("\n--- Test 4: Add Entity Mentions ---")
    try:
        mention_id = db.add_entity_mention(
            client_id=client_id,
            session_id=session_id,
            entity_type="person",
            entity_ref="mom",
            mention_context="My mom is great"
        )
        print(f"[OK] Created entity mention (id={mention_id})")

        mentions = db.get_entity_mentions(client_id, entity_ref="mom")
        assert len(mentions) > 0, "No entity mentions found"
        print(f"[OK] Retrieved {len(mentions)} mentions for 'mom'")
    except Exception as e:
        print(f"[ERROR] Entity mention test failed: {e}")
        return False

    # Test 5: Update world event
    print("\n--- Test 5: Update World Event ---")
    try:
        result = db.update_world_event(event_id, title="Updated Title")
        assert result is True, "Failed to update world event"
        print("[OK] Updated world event title")

        events = db.get_world_events(client_id)
        updated_event = [e for e in events if e['id'] == event_id][0]
        assert updated_event['title'] == "Updated Title"
        print(f"[OK] Verified update: {updated_event['title']}")
    except Exception as e:
        print(f"[ERROR] World event update test failed: {e}")
        return False

    # Test 6: Toggle auto-update
    print("\n--- Test 6: Toggle Auto-Update ---")
    try:
        result = db.update_auto_update_enabled('character', char_id, False)
        assert result is True, "Failed to toggle auto-update"
        print("[OK] Disabled auto-update for character card")

        result = db.update_auto_update_enabled('self', card_id, False)
        assert result is True, "Failed to toggle auto-update"
        print("[OK] Disabled auto-update for self card")

        result = db.update_auto_update_enabled('world', event_id, False)
        assert result is True, "Failed to toggle auto-update"
        print("[OK] Disabled auto-update for world event")
    except Exception as e:
        print(f"[ERROR] Auto-update toggle test failed: {e}")
        return False

    # Test 7: Delete card
    print("\n--- Test 7: Delete Card ---")
    try:
        result = db.delete_card('character', char_id)
        assert result is True, "Failed to delete character card"
        print("[OK] Deleted character card")
    except Exception as e:
        print(f"[ERROR] Delete card test failed: {e}")
        return False

    print("\n" + "="*60)
    print("[OK] All database method tests passed!")
    print("="*60)
    return True


def test_pydantic_models():
    """Test Pydantic models for Phase 1."""
    print("\n" + "="*60)
    print("Testing Pydantic Models")
    print("="*60)

    # Test 1: SelfCard model
    print("\n--- Test 1: SelfCard Model ---")
    try:
        self_card = SelfCard(
            id=1,
            client_id=1,
            card_json='{"name": "Test"}',
            auto_update_enabled=True,
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        assert self_card.auto_update_enabled is True
        assert self_card.card_json == '{"name": "Test"}'
        print("[OK] SelfCard model validation passed")
    except Exception as e:
        print(f"[ERROR] SelfCard model test failed: {e}")
        return False

    # Test 2: WorldEvent model
    print("\n--- Test 2: WorldEvent Model ---")
    try:
        world_event = WorldEvent(
            id=1,
            client_id=1,
            entity_id="evt_001",
            title="Test Event",
            key_array='["test", "event"]',
            description="Test description",
            event_type="achievement",
            is_canon_law=True,
            auto_update_enabled=True,
            resolved=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert world_event.is_canon_law is True
        assert world_event.event_type == "achievement"
        print("[OK] WorldEvent model validation passed")
    except Exception as e:
        print(f"[ERROR] WorldEvent model test failed: {e}")
        return False

    # Test 3: EntityMention model
    print("\n--- Test 3: EntityMention Model ---")
    try:
        entity_mention = EntityMention(
            id=1,
            client_id=1,
            session_id=1,
            entity_type="person",
            entity_ref="mom",
            mention_context="My mom is great",
            mentioned_at=datetime.now(),
            created_at=datetime.now()
        )
        assert entity_mention.entity_type == "person"
        assert entity_mention.entity_ref == "mom"
        print("[OK] EntityMention model validation passed")
    except Exception as e:
        print(f"[ERROR] EntityMention model test failed: {e}")
        return False

    # Test 4: CharacterCard with new fields
    print("\n--- Test 4: CharacterCard with New Fields ---")
    try:
        from app.models.schemas import RelationshipType
        char_card = CharacterCard(
            id=1,
            client_id=1,
            card_name="Mom",
            relationship_type=RelationshipType.FAMILY,
            card={"personality": "Overprotective"},
            auto_update_enabled=True,
            last_updated=datetime.now(),
            created_at=datetime.now(),
            entity_id="char_mom_001",
            mention_count=5,
            last_mentioned=datetime.now(),
            first_mentioned=datetime.now()
        )
        assert char_card.entity_id == "char_mom_001"
        assert char_card.mention_count == 5
        print("[OK] CharacterCard model validation passed")
    except Exception as e:
        print(f"[ERROR] CharacterCard model test failed: {e}")
        return False

    print("\n" + "="*60)
    print("[OK] All Pydantic model tests passed!")
    print("="*60)
    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Phase 1 Test Suite")
    print("="*60)

    db_passed = test_database_methods()
    models_passed = test_pydantic_models()

    print("\n" + "="*60)
    print("Final Results:")
    print("="*60)
    print(f"Database Methods: {'[OK] PASSED' if db_passed else '[ERROR] FAILED'}")
    print(f"Pydantic Models:   {'[OK] PASSED' if models_passed else '[ERROR] FAILED'}")
    print("="*60)

    if db_passed and models_passed:
        print("\n[OK] All tests passed! Phase 1 implementation is complete.")
        sys.exit(0)
    else:
        print("\n[ERROR] Some tests failed. Please review the errors above.")
        sys.exit(1)
