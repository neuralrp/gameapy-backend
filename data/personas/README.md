# Persona Management Guide

## Quick Start

Edit a persona JSON file:
```bash
# Edit Marina's persona
vim data/personas/marina.json
```

Sync to database:
```bash
cd backend
python scripts/seed_personas.py
```

Test in app at http://localhost:5176

## Workflow

1. **Edit JSON** in `data/personas/*.json`
2. **Sync to DB** with `python scripts/seed_personas.py`
3. **Test in app** - start a new session with that counselor
4. **Repeat** until satisfied

## Commands

```bash
# List all personas
python scripts/seed_personas.py --list

# Sync all personas
python scripts/seed_personas.py

# Sync specific persona
python scripts/seed_personas.py --name "Marina"
```

## Persona JSON Structure

```json
{
  "spec": "persona_profile_v1",
  "spec_version": "1.0",
  "data": {
    "name": "Your Name",
    "who_you_are": "Core identity/role",
    "your_vibe": "Communication style and personality",
    "your_worldview": "Philosophical perspective",
    "session_template": "Opening greeting",
    "session_examples": [
      {
        "user_situation": "What user might say",
        "your_response": "How you'd respond",
        "approach": "Why you respond that way"
      }
    ],
    "tags": ["tag1", "tag2"],
    "crisis_protocol": "Safety instructions",
    "hotlines": [...]
  }
}
```

## Key Fields

- **name**: Persona's name
- **who_you_are**: Core identity and role (e.g., "An ancient ocean spirit who guides travelers through emotional waters")
- **your_vibe**: Communication style and personality (e.g., "Flowing, empathetic, speaks in gentle tides and ripples")
- **your_worldview**: Philosophical perspective (e.g., "Emotions are like the ocean - sometimes calm, sometimes stormy...")
- **session_template**: Opening greeting when starting a chat
- **session_examples**: Sample interactions showing their voice
  - `user_situation`: Example input from user
  - `your_response`: How you'd respond
  - `approach`: Brief description of your approach
- **tags**: Categorization (sports, mythology, etc.)
- **crisis_protocol**: Safety resources for emergencies

## Current Personas

| File | Name | ID |
|------|------|-----|
| `coach_san_mateo.json` | Coach San Mateo | 1255 |
| `father_red_oak.json` | Father Red Oak | 1257 |
| `health_and_wellness_coach.json` | Health and Wellness Coach | 1256 |
| `marina.json` | Marina | 1258 |

## Tips for Editing

1. **Voice matters**: Keep `session_examples` consistent with personality
2. **Approach descriptions**: Use `approach` field to explain the intent behind responses
3. **Tags**: Add relevant tags for categorization
4. **Crisis protocol**: Keep consistent across all personas
5. **Test changes**: Always sync and test before committing

## Core Truths

All personas share universal principles defined in `backend/app/config/core_truths.py`. These include:
- Remember user through character and world cards
- Be genuinely helpful, not performatively helpful
- Have opinions
- Be resourceful
- Earn trust through competence
- Treat user's life with respect

## How It Works

1. JSON files in `data/personas/` are the source of truth
2. `seed_personas.py` reads JSONs and updates database
3. Chat API loads counselor from session and builds system prompt dynamically
4. Each counselor gets unique responses based on their JSON profile
5. Core truths are applied universally to all personas
