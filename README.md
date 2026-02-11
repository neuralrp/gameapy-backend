# Gameapy

**Infrastructure for being known** - An AI relationship that evolves with depth based on what you share.

A retro-style therapeutic storytelling app with GameBoy aesthetics, AI-powered character cards, and creative counselor personas.

## Overview

Gameapy combines therapeutic storytelling with gamification elements:

- **Character Cards**: AI-assisted generation and continuous updating of personality profiles for people in your life
- **Life Events**: Capture important moments, achievements, challenges, and transitions
- **Creative Counselors**: Four unique AI personas (Baseball Coach, Wise Old Man, CBT Therapist, Ocean Guide)
- **Organic Conversation**: No forced onboarding - conversation follows your lead
- **GameBoy UI**: Nostalgic pixel art interface with chiptune sounds (Flutter)

## Vision

Gameapy is infrastructure for being known - an AI relationship that evolves with depth based on what you share.

**Core Philosophy**:
1. **Cards Support Chat** (not vice versa) - Memory serves conversation
2. **Transparency Without Friction** - View/edit anytime, updates invisible
3. **User Sovereignty** - Per-card auto-update toggles, explicit consent for creation
4. **Organic Growth** - No forced phases, conversation follows user's lead

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLite + sqlite-vec (semantic search)
- **LLM**: OpenRouter API (Claude, GPT, Llama, etc.)
- **Testing**: Pytest with 99/99 tests passing (100% pass rate)

### Frontend (Web MVP)
- **Framework**: React 19.2.0+
- **Build Tool**: Vite 7.2.4+
- **Language**: TypeScript 5.9.3+
- **Styling**: Tailwind CSS 4.1.18+ (GBA color palette)
- **Deployment**: Vercel

### Mobile (Phase 8 - Planned)
- **Framework**: Flutter
- **State Management**: Riverpod
- **Design**: GameBoy pixel art UI

## Current Status

### Backend ✅ Complete (Phases 1-7)

- ✅ Database schema & migration system
- ✅ Card Generator Service (plain text → structured JSON)
- ✅ Unified Card Management API (CRUD, search, toggle)
- ✅ Auto-Update System (invisible updates with confidence thresholds)
- ✅ Entity Detection (keyword-based matching)
- ✅ Context Assembly (self + pinned + current + recent cards)
- ✅ Pytest Testing Infrastructure (89/89 tests passing, 100%)
- ✅ Guide System (organic conversation with card creation)
- ✅ Four counselor personas seeded

**Test Coverage**: 68% overall, 100% pass rate

### Mobile ⏳ Planned (Phase 8)

- ⏳ Flutter project initialization
- ⏳ GameBoy UI implementation
- ⏳ Chat interface with context indicators
- ⏳ Card inventory system
- ⏳ Settings & toggle controls

**Estimated Time**: 20-40 hours

### Web ✅ Complete (Phases 0-6)

- ✅ React + Vite + TypeScript project setup
- ✅ Counselor selection screen with 4 unique personas
- ✅ Chat interface with real-time SSE streaming
- ✅ Card inventory modal with tabs, search, pin/auto-update
- ✅ Card detail view and inline editing with validation
- ✅ Polish & mobile optimization with animations and touch targets
- ✅ Testing, bug fixes, and Vercel deployment

**Production**: https://gameapy-web.vercel.app

## Architecture

```
React Web App (Vite, Mobile-Optimized)
    ↓
FastAPI Backend
    ├─ Cards API (/api/v1/cards/*)
    ├─ Guide API (/api/v1/guide/*)
    ├─ Chat API (/api/v1/chat/*)
    └─ Session Analyzer (/api/v1/sessions/{id}/analyze)
    ↓
SQLite Database
    ├─ self_cards (one per client)
    ├─ character_cards (people in your life)
    ├─ world_events (life milestones)
    └─ entity_mentions (tracking)
```

### Deployment Architecture

```
User Browser
    ↓
gameapy-web.vercel.app (Vercel - React Frontend)
    ↓
HTTPS API calls
    ↓
gameapy-backend-production.up.railway.app (Railway - FastAPI Backend)
    ↓
SQLite Database
```

## Quick Start

### Web App (Live)

Access the live web application at: https://gameapy-web.vercel.app

### Backend Setup

1. **Clone repository**
```bash
git clone https://github.com/your-username/gameapy.git
cd gameapy
```

2. **Install dependencies**
```bash
cd backend
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

4. **Start server**
```bash
python main.py
```

Server runs at `http://localhost:8000`
API docs available at `http://localhost:8000/docs`

### Frontend Development

1. **Install dependencies**
```bash
cd gameapy-web
npm install
```

2. **Start development server**
```bash
npm run dev
```

Development server runs at `http://localhost:5176`

### Running Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run by category
pytest tests/ -m unit -v          # Unit tests only
pytest tests/ -m integration -v   # Integration tests only
```

**Test Results**: 89/89 tests passing (100% pass rate)

## Key Features

### Card System

**Three Card Types**:
- **Self Card**: Captures personality, traits, interests, values, goals
- **Character Cards**: People in your life (family, friends, coworkers) with personality profiles
- **Life Events**: Important moments, achievements, challenges, transitions

**Smart Context Loading**:
1. Always: Self card
2. Always: Pinned cards (user marks "keep in mind")
3. Always: Cards mentioned in current session
4. Configurable: Top N cards by recency (default: 5 sessions)

### Guide System

- **Organic Conversation**: No forced phases, follows user's lead
- **Card Suggestions**: Detects card-worthy topics and asks for confirmation
- **Explicit Consent**: Cards created only with user approval
- **Farm Discovery**: Optional feature suggested after 5+ sessions

### Counselor Personas

Four complete AI counselors with unique personalities:

1. **Marina** (New-Age Spiritual Guide) - Feminine, peaceful, eastern spirituality, holistic wellness
2. **Coach San Mateo** (Motivational Coach) - Verbal affirmation, pragmatic, actionable, humorous
3. **Health and Wellness Coach** (Holistic Wellness Specialist) - Wellness Wheel, functional medicine, proactive
4. **Father Red Oak** (Wise Ancient Tree) - Patient, warm, deeply experienced, grandfatherly

### Auto-Update System

- **Invisible Updates**: Cards evolve automatically from session analysis
- **Confidence Thresholds**: Batch ≥0.5, per-field ≥0.7
- **Conflict Resolution**: AI never overwrites user edits (skips updates)
- **Per-Card Toggle**: Users can freeze specific cards

## API Documentation

### Cards API
- `POST /api/v1/cards/generate-from-text` - Generate from plain text
- `POST /api/v1/cards/save` - Save card to database
- `PUT /api/v1/cards/{id}` - Partial update
- `PUT /api/v1/cards/{id}/toggle-auto-update` - Toggle auto-update
- `GET /api/v1/cards/search` - Search across types
- `DELETE /api/v1/cards/{id}` - Delete card

### Guide API
- `POST /api/v1/guide/conversation/start` - Start conversation
- `POST /api/v1/guide/conversation/input` - Process input (may suggest card)
- `POST /api/v1/guide/conversation/confirm-card` - Create suggested card

### Chat API
- `POST /api/v1/chat` - Send message with SSE streaming (real-time response)
- Returns SSE stream with chunks:
  - `{"type": "content", "content": "..."}`
  - `{"type": "done", "data": {"cards_loaded": N, "counselor_switched": bool, "new_counselor": {...}}}`
  - `{"type": "error", "error": "..."}`

See [API_EXAMPLES.md](backend/API_EXAMPLES.md) for detailed API usage examples.

## Documentation

- **[AGENTS.md](AGENTS.md)** - LLM-optimized high-level overview (always loaded into memory)
- **[TECHNICAL.md](TECHNICAL.md)** - Detailed technical documentation
- **[FLUTTER_UI_DEVELOPMENT_PLAN.md](FLUTTER_UI_DEVELOPMENT_PLAN.md)** - Flutter UI implementation plan
- **[backend/API_EXAMPLES.md](backend/API_EXAMPLES.md)** - API usage examples
- **[backend/SETUP.md](backend/SETUP.md)** - Backend setup guide

## Color Palette (GBA-Style)

```
Background: #E8D0A0 (warm off-white)
Grass: #88C070 (bright lime)
Borders: #306850 (forest green)
UI Background: #F8F0D8 (cream)
Highlight: #F8D878 (yellow)
Text: #483018 (dark brown)
```

## Testing

### Test Results (Current)
- **Database**: 20/20 tests passing (100%)
- **Entity Detector**: 8/8 tests passing (100%)
- **Context Assembler**: 6/6 tests passing (100%)
- **Guide System**: 6/6 tests passing (100%)
- **Cards API**: 17/17 tests passing (100%)
- **Chat API**: 16/16 tests passing (100%)
- **Guide API**: 8/8 tests passing (100%)
- **Session Analyzer**: 5/5 tests passing (100%)
- **E2E Flows**: 6/6 tests passing (100%)
- **LLM Integration**: 3/3 tests passing (100%)

**Total**: 99/99 tests passing (100% pass rate)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Development Workflow

### Backend (Complete)
- All features implemented and tested
- 99/99 tests passing with 68% coverage
- Streaming chat with SSE support
- Ready for production testing

### Mobile (Next)
- See [FLUTTER_UI_DEVELOPMENT_PLAN.md](FLUTTER_UI_DEVELOPMENT_PLAN.md) for comprehensive implementation guide
- Estimated 20-40 hours for complete Flutter UI

## Roadmap

### ✅ Completed (Backend)
- [x] Database schema & migration
- [x] Card Generator Service
- [x] Unified Card Management API
- [x] Auto-Update System
- [x] Entity Detection
- [x] Context Assembly
- [x] Pytest Testing Infrastructure
- [x] Guide System

### ✅ Completed (Web Frontend)
- [x] React + Vite + TypeScript project setup
- [x] Counselor selection screen
- [x] Chat interface with backend integration
- [x] Card inventory modal
- [x] Card editing functionality
- [x] Mobile optimization and polish
- [x] Vercel deployment

### ⏳ In Progress (Mobile)
- [ ] Flutter project initialization
- [ ] GameBoy UI implementation
- [ ] Chat interface
- [ ] Card inventory system
- [ ] Settings & controls

### 📋 Future Enhancements
- [ ] Increase test coverage from 68% to 75%+
- [ ] On-device LLM for offline mode
- [ ] Cloud sync with user authentication
- [ ] Farm minigame (optional feature)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **OpenRouter** - Multi-model LLM API
- **FastAPI** - Modern Python web framework
- **Flutter** - Cross-platform UI framework
- **NeuralRP** - Inspiration for world events and entity tracking

---

**Status**: Backend Complete | Web MVP Complete | Mobile Pending
**Last Updated**: 2026-02-11
**Version**: 3.5.0

**Live Demo**: https://gameapy-web.vercel.app
