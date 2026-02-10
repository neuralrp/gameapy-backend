"""
Test that keyword-based card matching works correctly.

Tests:
1. Character cards match by name
2. World events match by title
3. Mentioned cards persist in session context
"""

import asyncio
from app.db.database import db
from app.services.entity_detector import entity_detector
from app.services.context_assembler import context_assembler

def test_keyword_matching():
    print("\n=== Testing Keyword-Based Card Matching ===\n")

    # Create test client
    client_id = db.create_client_profile({
        'data': {
            'name': 'Test User',
            'personality': 'Test',
            'traits': [],
            'goals': [],
            'presenting_issues': [],
            'tags': []
        }
    })

    # Create test counselor
    counselor_id = db.create_counselor_profile({
        'data': {
            'name': 'Test Counselor',
            'specialization': 'Testing',
            'therapeutic_style': 'Test style',
            'credentials': 'AI',
            'who_you_are': 'Test',
            'your_vibe': 'Test',
            'your_worldview': 'Test'
        }
    })

    # Create test session
    session_id = db.create_session(
        client_id=client_id,
        counselor_id=counselor_id
    )

    # Create character card
    char_card_id = db.create_character_card(
        client_id=client_id,
        card_name='Mom',
        relationship_type='family',
        card_data={
            'personality': 'Caring, supportive',
            'traits': ['kind', 'loving'],
            'patterns': []
        }
    )

    # Create world event card
    import json
    import uuid
    world_event_id = db.create_world_event(
        client_id=client_id,
        entity_id=f'world_{uuid.uuid4().hex}',
        title='Going to college',
        key_array=json.dumps(['college', 'university', 'education']),
        description='I started college in 2020',
        event_type='life_event',
        is_canon_law=False,
        auto_update_enabled=True,
        resolved=False
    )

    print(f"[OK] Created test client: {client_id}")
    print(f"[OK] Created test session: {session_id}")
    print(f"[OK] Created character card 'Mom' (id={char_card_id})")
    print(f"[OK] Created world event 'Going to college' (id={world_event_id})")

    # Test 1: Character card matches by name
    print("\n--- Test 1: Character Card Name Matching ---")
    message1 = "My mom has been really supportive lately."
    mentions1 = entity_detector.detect_mentions(message1, client_id)

    print(f"Message: '{message1}'")
    print(f"Detected mentions: {mentions1}")

    assert len(mentions1) > 0, "Should detect 'Mom' mention"
    assert mentions1[0]['card_id'] == char_card_id, "Should match 'Mom' card"
    assert mentions1[0]['card_type'] == 'character', "Should be character type"
    print("[PASS] Character card matched by name")

    # Test 2: World event matches by title
    print("\n--- Test 2: World Event Title Matching ---")
    message2 = "Going to college was a big change for me."
    mentions2 = entity_detector.detect_mentions(message2, client_id)

    print(f"Message: '{message2}'")
    print(f"Detected mentions: {mentions2}")

    assert len(mentions2) > 0, "Should detect 'Going to college' mention"
    assert mentions2[0]['card_id'] == world_event_id, "Should match 'Going to college' event"
    assert mentions2[0]['card_type'] == 'world', "Should be world type"
    print("[PASS] World event matched by title")

    # Test 3: Mentions persist in session context
    print("\n--- Test 3: Context Persistence ---")

    # Log the mentions to session
    db.add_entity_mention(
        client_id=client_id,
        session_id=session_id,
        entity_type='character_card',
        entity_ref=str(char_card_id),
        mention_context=message1
    )

    db.add_entity_mention(
        client_id=client_id,
        session_id=session_id,
        entity_type='world_card',
        entity_ref=str(world_event_id),
        mention_context=message2
    )

    print(f"[OK] Logged mentions to session {session_id}")

    # Assemble context
    context = context_assembler.assemble_context(
        client_id=client_id,
        session_id=session_id,
        user_message="Testing"
    )

    print(f"\nContext loaded:")
    print(f"  Self card: {'Yes' if context['self_card'] else 'No'}")
    print(f"  Pinned cards: {len(context['pinned_cards'])}")
    print(f"  Current mentions: {len(context['current_mentions'])}")
    print(f"  Recent cards: {len(context['recent_cards'])}")
    print(f"  Total cards loaded: {context['total_cards_loaded']}")

    # Check that mentioned cards are in context
    current_mention_ids = [card['id'] for card in context['current_mentions']]

    assert char_card_id in current_mention_ids, "Mom card should be in current mentions"
    assert world_event_id in current_mention_ids, "College event should be in current mentions"
    print("[PASS] Mentioned cards persist in session context")

    print("\n=== All Tests Passed ===\n")
    return True

if __name__ == '__main__':
    test_keyword_matching()
