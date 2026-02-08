"""
Seed test data for Phase 1 development
Run ONLY on development/test databases, never production
"""

import sqlite3
import json
from datetime import datetime


def seed_test_data(db_path: str = "gameapy_test.db"):
    """Seed test data for Phase 1 features."""
    print(f"⚠️  Seeding test data into {db_path}")
    print("⚠️  DO NOT run this on production database!")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create test client
        print("\n--- Creating test client ---")
        cursor.execute("""
            INSERT INTO client_profiles (entity_id, name, profile_json, tags, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "client_test_001",
            "Test User",
            json.dumps({
                "spec": "client_profile_v1",
                "spec_version": "1.0",
                "data": {
                    "name": "Test User",
                    "personality": "Perfectionist, people-pleaser",
                    "traits": ["anxious", "creative", "empathetic"],
                    "presenting_issues": [
                        {"issue": "work stress", "severity": "moderate", "duration": "3 months"}
                    ],
                    "goals": ["improve confidence", "set boundaries"],
                    "life_events": [],
                    "preferences": {
                        "communication_style": "gentle",
                        "pace": "moderate",
                        "focus_areas": ["work-life balance", "self-care"]
                    }
                }
            }),
            json.dumps(["anxiety", "work stress", "perfectionism"]),
            True
        ))
        client_id = cursor.lastrowid
        print(f"✅ Created test client (id={client_id})")

        # Create test counselor
        print("\n--- Creating test counselor ---")
        cursor.execute("""
            INSERT INTO counselor_profiles (entity_id, name, specialization, therapeutic_style, credentials, profile_json, tags, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "counselor_test_001",
            "Dr. Test Counselor",
            "General Therapy",
            "Supportive and empathetic",
            "PhD in Psychology",
            json.dumps({
                "spec": "counselor_profile_v1",
                "spec_version": "1.0",
                "data": {
                    "name": "Dr. Test Counselor",
                    "specialization": "General Therapy",
                    "therapeutic_style": "Supportive and empathetic",
                    "credentials": "PhD in Psychology",
                    "session_template": "Hello, how are you feeling today?",
                    "extensions": {}
                }
            }),
            json.dumps(["empathetic", "supportive", "general"]),
            True
        ))
        counselor_id = cursor.lastrowid
        print(f"✅ Created test counselor (id={counselor_id})")

        # Create test session
        print("\n--- Creating test session ---")
        cursor.execute("""
            INSERT INTO sessions (client_id, counselor_id, session_number, started_at)
            VALUES (?, ?, ?, ?)
        """, (client_id, counselor_id, 1, datetime.now().isoformat()))
        session_id = cursor.lastrowid
        print(f"✅ Created test session (id={session_id})")

        # Create test self card
        print("\n--- Creating test self card ---")
        self_card_json = json.dumps({
            "spec": "gameapy_self_card_v1",
            "spec_version": "1.0",
            "data": {
                "name": "Test User",
                "personality": "Perfectionist, people-pleaser, anxious",
                "traits": ["anxious", "creative", "empathetic", "perfectionist"],
                "interests": ["guitar", "golf", "AI development", "reading"],
                "triggers": ["conflict", "criticism", "tight deadlines"],
                "coping_mechanisms": ["exercise", "music", "deep breathing"],
                "emotional_patterns": {
                    "typical_mood": "anxious but functional",
                    "stress_response": "overthinking and rumination",
                    "recovery_pattern": "needs alone time"
                }
            }
        })
        cursor.execute("""
            INSERT INTO self_cards (client_id, card_json, auto_update_enabled)
            VALUES (?, ?, ?)
        """, (client_id, self_card_json, True))
        self_card_id = cursor.lastrowid
        print(f"✅ Created test self card (id={self_card_id})")

        # Create test character card
        print("\n--- Creating test character card ---")
        char_card_json = json.dumps({
            "spec": "gameapy_character_card_v1",
            "spec_version": "1.0",
            "data": {
                "name": "Mom",
                "relationship_type": "family",
                "personality": "Overprotective, well-meaning",
                "patterns": [
                    {"pattern": "nags about homework/career", "weight": 0.8, "mentions": 5},
                    {"pattern": "expresses concern through cooking", "weight": 0.6, "mentions": 3}
                ],
                "key_events": [
                    {"event": "Helped through college", "date": "2015-05", "impact": "positive"},
                    {"event": "Opposed career change", "date": "2018-08", "impact": "negative"}
                ],
                "user_feelings": [
                    {"feeling": "loves her but feels smothered", "weight": 0.85},
                    {"feeling": "appreciates her care", "weight": 0.7}
                ],
                "emotional_state": {
                    "user_to_other": {
                        "trust": 75,
                        "emotional_bond": 85,
                        "conflict": 60,
                        "power_dynamic": -20,
                        "fear_anxiety": 45
                    },
                    "other_to_user": None
                }
            }
        })
        cursor.execute("""
            INSERT INTO character_cards
            (client_id, card_name, relationship_type, card_json, entity_id, mention_count, first_mentioned, last_mentioned, auto_update_enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            "Mom",
            "family",
            char_card_json,
            "char_mom_001",
            5,
            datetime(2024, 1, 1).isoformat(),
            datetime.now().isoformat(),
            True
        ))
        char_card_id = cursor.lastrowid
        print(f"✅ Created test character card (id={char_card_id})")

        # Create test world event
        print("\n--- Creating test world events ---")
        cursor.execute("""
            INSERT INTO world_events
            (client_id, entity_id, title, key_array, description, event_type, is_canon_law, auto_update_enabled, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            "evt_gameapy_started",
            "Started Gameapy Development",
            json.dumps(["gameapy", "ai", "development", "career"]),
            "[Achievement: Started Gameapy, type(career), impact(high), timeline(2024)]",
            "achievement",
            True,
            True,
            False
        ))
        world_event_id = cursor.lastrowid
        print(f"✅ Created test world event (id={world_event_id})")

        # Create another world event (trauma example)
        cursor.execute("""
            INSERT INTO world_events
            (client_id, entity_id, title, key_array, description, event_type, is_canon_law, auto_update_enabled, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            "evt_childhood_assault",
            "Childhood Trauma",
            json.dumps(["assault", "childhood", "trauma", "uncle", "trust issues"]),
            "[Trauma: Childhood assault, type(trauma), time(age 12), actor(uncle), result(trust issues), legacy(ongoing therapy)]",
            "trauma",
            True,
            True,
            False
        ))
        trauma_event_id = cursor.lastrowid
        print(f"✅ Created test trauma event (id={trauma_event_id})")

        # Create test entity mentions
        print("\n--- Creating test entity mentions ---")
        mention_data = [
            ("person", "Mom", "My mom called again about my job", 1),
            ("person", "Mom", "She really worries about me", 2),
            ("person", "Mom", "Made mom's recipe today", 3),
            ("person", "Mom", "Mom visited last weekend", 4),
            ("person", "Mom", "Called mom for advice", 5),
            ("trait", "perfectionist", "I need everything to be perfect", 1),
            ("trait", "anxious", "Feeling anxious about the presentation", 2),
            ("interest", "guitar", "Practiced guitar after work", 1),
            ("interest", "golf", "Played golf with friends", 2),
            ("emotion", "anxious", "I'm feeling really anxious lately", 1),
        ]

        for entity_type, entity_ref, context, msg_num in mention_data:
            cursor.execute("""
                INSERT INTO entity_mentions (client_id, session_id, entity_type, entity_ref, mention_context, mentioned_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                client_id,
                session_id,
                entity_type,
                entity_ref,
                context,
                datetime(2024, 1, msg_num, 12, 0).isoformat()
            ))

        print(f"✅ Created {len(mention_data)} test entity mentions")

        # Create test messages
        print("\n--- Creating test messages ---")
        messages = [
            ("user", "Hi Dr. Test Counselor, I've been feeling anxious lately about my career.", None),
            ("assistant", "Hello! I'm here to support you. Tell me more about what's been on your mind.", "Dr. Test Counselor"),
            ("user", "My mom keeps nagging me about finding a 'real job', but I love what I'm doing now.", None),
            ("assistant", "It sounds like there's some tension there between your passions and your mother's expectations. How does that make you feel?", "Dr. Test Counselor"),
            ("user", "Smothered. I appreciate that she cares, but it's overwhelming.", None),
        ]

        for role, content, speaker in messages:
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, speaker, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, role, content, speaker, datetime.now().isoformat()))

        print(f"✅ Created {len(messages)} test messages")

        conn.commit()
        print("\n" + "="*60)
        print("✅ Test data seeded successfully!")
        print("="*60)
        print(f"\nClient ID: {client_id}")
        print(f"Counselor ID: {counselor_id}")
        print(f"Session ID: {session_id}")
        print(f"Self Card ID: {self_card_id}")
        print(f"Character Card ID: {char_card_id}")
        print(f"World Event IDs: {world_event_id}, {trauma_event_id}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Failed to seed test data: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "gameapy_test.db"

    # Warning check
    if "test" not in db_path.lower():
        print("⚠️  WARNING: Database name doesn't contain 'test'.")
        response = input("Are you sure you want to seed this database? (yes/no): ")
        if response.lower() != "yes":
            print("Aborting.")
            sys.exit(1)

    seed_test_data(db_path)
