# Gameapy API Examples

## Guide API (Organic Conversation)

### Start Conversation
```bash
curl -X POST "http://localhost:8000/api/v1/guide/conversation/start" \
  -H "Content-Type: application/json" \
  -d '{"client_id": 1}'
```

**Response:**
```json
{
  "success": true,
  "message": "Started conversation",
  "data": {
    "guide_message": "Hey there! I'm here to get to know you...",
    "session_id": 123,
    "client_id": 1
  }
}
```

### Process Conversation Input
```bash
curl -X POST "http://localhost:8000/api/v1/guide/conversation/input" \
  -H "Content-Type: application/json" \
  -d '{"session_id": 123, "user_input": "My boss is being difficult"}'
```

**Response (with card suggestion):**
```json
{
  "success": true,
  "message": "It sounds like this person is important here...",
  "data": {
    "guide_message": "Want me to create a card for this person?",
    "suggested_card": {
      "card_type": "character",
      "topic": "My boss, John, is demanding",
      "confidence": 0.8
    },
    "conversation_complete": false
  }
}
```

**Response (no suggestion):**
```json
{
  "success": true,
  "message": "Tell me more about that.",
  "data": {
    "guide_message": "Tell me more about that.",
    "suggested_card": null,
    "conversation_complete": false
  }
}
```

### Confirm Card Creation
```bash
curl -X POST "http://localhost:8000/api/v1/guide/conversation/confirm-card" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 123,
    "card_type": "character",
    "topic": "My boss, John, is demanding"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Got it! I've created a card for My boss.",
  "data": {
    "card_id": 456,
    "card_data": {
      "spec": "gameapy_character_card_v1",
      "data": {
        "name": "My boss",
        "relationship_type": "coworker",
        ...
      }
    },
    "guide_message": "Anything else you'd like to share?"
  }
}
```

---

## Cards API

### Generate Card from Text
```bash
curl -X POST "http://localhost:8000/api/v1/cards/generate-from-text" \
  -H "Content-Type: application/json" \
  -d '{
    "card_type": "character",
    "plain_text": "My mom is overprotective",
    "name": "Mom"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Card generated successfully",
  "data": {
    "card_type": "character",
    "generated_card": {
      "spec": "gameapy_character_card_v1",
      "data": {
        "name": "Mom",
        "relationship_type": "family",
        "personality": "Overprotective, well-meaning",
        ...
      }
    },
    "preview": true,
    "fallback": false
  }
}
```

### Save Card
```bash
curl -X POST "http://localhost:8000/api/v1/cards/save" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "card_type": "character",
    "card_data": {
      "name": "Mom",
      "relationship_type": "family",
      "personality": "Overprotective"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Card saved successfully",
  "data": {
    "card_id": 789
  }
}
```

### Update Card
```bash
curl -X PUT "http://localhost:8000/api/v1/cards/character/789" \
  -H "Content-Type: application/json" \
  -d '{
    "card_json": "{\"personality\": \"Overprotective, caring\"}",
    "changed_by": "user"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Card updated successfully"
}
```

### Pin Card
```bash
curl -X PUT "http://localhost:8000/api/v1/cards/character/789/pin"
```

**Response:**
```json
{
  "success": true,
  "message": "Card pinned"
}
```

### Unpin Card
```bash
curl -X PUT "http://localhost:8000/api/v1/cards/character/789/unpin"
```

**Response:**
```json
{
  "success": true,
  "message": "Card unpinned"
}
```

### Search Cards
```bash
curl "http://localhost:8000/api/v1/cards/search?q=mom&types=character"
```

**Response:**
```json
{
  "success": true,
  "message": "Search completed",
  "data": {
    "items": [
      {
        "id": 789,
        "card_type": "character",
        "payload": {
          "name": "Mom",
          "relationship_type": "family",
          "personality": "Overprotective"
        },
        "relevance": 1.0
      }
    ]
  }
}
```

### Delete Card
```bash
curl -X DELETE "http://localhost:8000/api/v1/cards/character/789"
```

**Response:**
```json
{
  "success": true,
  "message": "Card deleted successfully"
}
```

---

## Chat API

### Send Message
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": 123,
    "message_data": {
      "role": "user",
      "content": "Hi, how are you?"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Message processed successfully",
  "data": {
    "user_message_id": 456,
    "ai_message_id": 789,
    "ai_response": "Hi there! I'm doing well, thanks for asking.",
    "cards_loaded": 3
  }
}
```

---

## Custom Advisors API

### Create Custom Advisor
```bash
curl -X POST "http://localhost:8000/api/v1/counselors/custom/create" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "name": "Captain Wisdom",
    "specialty": "Life advice with maritime metaphors",
    "vibe": "Gruff but caring old sea captain"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Advisor created successfully",
  "data": {
    "counselor_id": 123,
    "persona": {
      "spec": "persona_profile_v1",
      "spec_version": "1.0",
      "data": {
        "name": "Captain Wisdom",
        "who_you_are": "A grizzled sea captain...",
        "your_vibe": "Gruff but caring...",
        "your_worldview": "...",
        "session_template": "...",
        "session_examples": [...],
        "tags": ["wisdom", "maritime"],
        "visuals": {...},
        "crisis_protocol": "...",
        "hotlines": [...]
      }
    }
  }
}
```

### List Custom Advisors
```bash
curl "http://localhost:8000/api/v1/counselors/custom/list/1"
```

**Response:**
```json
[
  {
    "id": 123,
    "entity_id": "counselor_...",
    "name": "Captain Wisdom",
    "specialization": "Life advice with maritime metaphors",
    "therapeutic_style": "Gruff but caring old sea captain",
    "credentials": "Help",
    "profile": {...},
    "tags": ["wisdom", "maritime"],
    "created_at": "2026-02-12T10:30:00",
    "updated_at": "2026-02-12T10:30:00"
  }
]
```

### Delete Custom Advisor
```bash
curl -X DELETE "http://localhost:8000/api/v1/counselors/custom/delete" \
  -H "Content-Type: application/json" \
  -d '{
    "counselor_id": 123,
    "client_id": 1
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Advisor deleted successfully"
}
```

---

## Farm API (Optional)

### Get Game State
```bash
curl "http://localhost:8000/api/v1/farm/state/1"
```

**Response:**
```json
{
  "success": true,
  "message": "Game state retrieved",
  "data": {
    "id": 1,
    "client_id": 1,
    "gold_coins": 50,
    "farm_level": 1,
    ...
  }
}
```

### Buy Farm Item
```bash
curl -X POST "http://localhost:8000/api/v1/farm/buy" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "item_type": "egg",
    "item_name": "Chicken Egg"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Item purchased",
  "data": {
    "gold_coins": 40,
    "new_item": {
      "id": 123,
      "item_type": "egg",
      "item_name": "Chicken Egg"
    }
  }
}
```