# Gameapy - Agent Quick Reference

**Version**: 3.5.0 | **Last Updated**: 2026-02-11 (Streaming chat endpoint with SSE support)

---

## Repository Structure

Gameapy is split into two separate GitHub repositories:

| Repo | URL | Purpose |
|------|-----|---------|
| **Backend** | https://github.com/NeuralRP/gameapy-backend | FastAPI server, database, LLM services, tests |
| **Web** | https://github.com/NeuralRP/gameapy-web | React frontend (Vite + TypeScript + Tailwind) |

### File Organization

```
gameapy-backend/          # Backend repo
├── app/
│   ├── api/              # FastAPI route handlers
│   ├── db/               # Database operations (database.py)
│   ├── services/         # LLM services (card_generator, guide_system, card_updater)
│   ├── models/           # Pydantic schemas
│   └── config/           # Core truths, persona configs
├── data/personas/        # Persona JSON definitions
├── tests/                # Pytest test suite
├── scripts/              # Utility scripts (seed_personas)
├── main.py               # FastAPI app entry point
├── requirements.txt      # Python dependencies
├── schema.sql            # Database schema
└── pytest.ini            # Test configuration

gameapy-web/              # Web frontend repo
├── src/
│   ├── components/      # React components (ui, counselor, shared)
│   ├── contexts/         # React Context (AppContext.tsx)
│   ├── screens/          # Screen components (CounselorSelection, ChatScreen, GuideScreen, CardInventoryModal)
│   ├── services/         # API client (api.ts)
│   ├── types/            # TypeScript types
│   └── utils/            # Utilities (constants.ts)
├── index.css             # Global styles + Tailwind v4
├── package.json          # Node dependencies
├── vite.config.ts        # Vite build config
├── vercel.json           # Vercel deployment config
└── .env.production       # Production environment variables
```

---

## Current Status

**Completed Backend**: Phases 1-7 (All backend features + complete test infrastructure)
**Completed Frontend**: Phases 0-6 (Web MVP complete + deployed to Vercel)
**Latest Update**: CardInventoryModal iOS-style redesign, Easter egg "Summon Deirdre", schema migrations 004-006, auto-seed personas
**Production Deploy**: Backend on Railway, Frontend on Vercel
**Status**: Live at https://gameapy-web.vercel.app

### What's Working (Backend)
- Database: self_cards, character_cards, world_events, entity_mentions tables (with is_pinned columns)
- Card Generator: Plain text → structured JSON (with fallback)
- Organic Guide System: Conversational onboarding with card creation on-demand
- Pin System: "Keep this in mind" cards always load in context
- Keyword-Only Entity Detection: Fast, simple matching (no vector embeddings)
- Auto-Update System: Invisible updates with per-card toggles
- Context Assembly: Self + pinned + current + recent cards
- Pytest Testing Infrastructure: File-based test DB, LLM mocking, test isolation
- **All 99 tests passing** (100% pass rate, 68% code coverage)
- Deterministic test execution (no state pollution, per-request LLM clients)
- **Human-Readable Context**: JSON cards converted to prose for better LLM comprehension
- **Prompt Optimization**: Persona-first ordering, trimmed examples, compressed crisis protocol
- **Easter Egg Feature**: "Summon Deirdre" in Marina chat switches to hidden counselor Deirdre
- **Hidden Counselor Flag**: is_hidden column marks Easter egg counselors (not shown in selection screen)
- **Schema Migrations**: Auto-apply migrations 004-006 on startup
- **Auto-Seed Personas**: Persona JSON → DB sync script with is_hidden support
- **Streaming Chat**: SSE (Server-Sent Events) for real-time chat responses with metadata

### What's Working (Frontend - Web MVP)
- **Phase 0 Complete**: React + Vite + TypeScript project initialized
- **Phase 1 Complete**: Counselor selection screen with 4 colored placeholder cards
- **Phase 2 Complete**: Chat interface with real backend integration
- **Phase 3 Complete**: Card inventory modal with tabs, search, pin/auto-update
- **Phase 4 Complete**: Card detail view and inline editing with validation
- **Phase 5 Complete**: Polish & mobile optimization with animations and touch targets
- **Phase 6 Complete**: Testing, bug fixes, and Vercel deployment
- **Production Deploy**: https://gameapy-web.vercel.app
- **GuideScreen**: Organic card creation flow with conversational onboarding
- **CounselorInfoModal**: View counselor details from chat screen with counselor-specific colors
- **Toast Component**: User notifications (success/error/info)
- **Redesign**: CounselorSelection as 2x2 color block grid
- **Redesign**: ChatScreen with iMessage-style bubbles, counselor info link
- **Redesign**: CardInventoryModal with modern iOS-style UI
- **Auto-Session Analysis**: Every 5 messages, trigger card updates with toast notification
- **Session Message Counting**: Track messages per session for analysis triggers
- **Global State**: Guide flow state (showGuide, guideSessionId) in AppContext
- **Easter Egg Feature**: "Summon Deirdre" in Marina chat switches to hidden counselor Deirdre
- **Counselor Switching**: Frontend handles counselor_switched flag, updates state, shows toast
- **Counselor-Specific Theming**: Colors automatically update based on counselor's visual settings
- **Quick AI Card Creation**: Button in CardInventoryModal for instant card generation
- **Full-Screen Inventory Mode**: Immersive card browsing experience
- **Streaming Chat**: SSE-based real-time chat with smooth text rendering and metadata
- GBA color palette configured in Tailwind CSS v4
- VT323 retro font loaded from Google Fonts
- Client ID auto-generation with localStorage persistence
- Global state management (counselor, inventory modal) via React Context
- Card editing: view details, edit core fields, save changes, validation, unsaved changes confirmation
- Smooth fade-in animations (0.3s) for all screens
- Button hover/active animations with visual feedback
- All touch targets meet WCAG AA (44x44px minimum)
- Responsive layouts for mobile/tablet/desktop
- Retry buttons for all failed API requests
- Mobile keyboard overlap prevention (flex-shrink-0 on headers/footers)
- Vercel configuration with Railway backend integration

---

## Project Vision

**Gameapy** is infrastructure for being known - an AI relationship that evolves with depth based on what you share.

Core philosophy:
1. **Cards Support Chat** (not vice versa) - Memory serves conversation
2. **Transparency Without Friction** - View/edit anytime, updates invisible
3. **User Sovereignty** - Per-card auto-update toggles, explicit consent for creation
4. **Organic Growth** - No forced phases, conversation follows user's lead

---

## Documentation Structure

### Core Documentation (ALWAYS KEEP UP TO DATE)

| File | Purpose | Audience | When to Update |
|------|---------|-----------|-----------------|
| **AGENTS.md** | LLM-optimized high-level overview | AI Agents (you!) | After each phase completion |
| **TECHNICAL.md** | Detailed technical breakdown | Developers | After each phase completion |
| **README.md** | Project overview for GitHub | Public/Users | Before GitHub release |
| **FLUTTER_UI_DEVELOPMENT_PLAN.md** | Flutter implementation plan | Mobile Developers | After Flutter development starts |

### Backend Documentation

| File | Purpose | Status |
|------|---------|--------|
| **API_EXAMPLES.md** | cURL examples for all API endpoints | Current, accurate |
| **SETUP.md** | Backend setup and installation guide | Current, accurate |

### Frontend Documentation

| File | Purpose | Status |
|------|---------|--------|
| **WEB_MVP_DEVELOPMENT_PLAN.md** | Web MVP implementation plan (6 phases, 15-20 hours) | Complete |
| **FLUTTER_UI_DEVELOPMENT_PLAN.md** | Flutter implementation plan (ARCHIVED - replaced by web MVP) | Historical reference |

### Historical/Archive Documentation

| File | Purpose | When Created |
|------|---------|--------------|
| **PIVOT_IMPLEMENTATION_COMPLETE.md** | Documents v3.0 → v3.1 pivot (removal of canon law, 3-phase onboarding) | 2026-02-08 |
| **PHASE7_TEST_FIXES_SUMMARY.md** | Documents journey to 100% test pass rate | 2026-02-08 |
| **TEST_INFRASTRUCTURE_COMPLETE.md** | Initial pytest infrastructure setup | 2026-02-08 |

---

## Documentation Update Guidelines

### ✅ When Completing a Phase

**DO NOT**: Create new markdown files (e.g., PHASE8_COMPLETION.md)

**DO**: Update existing documentation:
1. **AGENTS.md**: Update "Current Status", "Phase Status", add to "Critical Files"
2. **TECHNICAL.md**: Update "Completed Features" section, add new API endpoints
3. **README.md**: Update "Current Status" section, add to "Roadmap"

### 📋 Documentation Update Checklist

After completing any phase:

- [ ] Update AGENTS.md Phase Status table
- [ ] Update TECHNICAL.md with new features/APIs
- [ ] Update README.md status and roadmap
- [ ] Add any new critical files to AGENTS.md
- [ ] Test that all documentation is consistent

---

## Tech Stack

```
Backend: Python 3.11+, FastAPI
Database: SQLite (keyword-only search, no embeddings)
LLM: OpenRouter API (Claude, GPT, etc.)

Frontend (Web MVP): React 19.2.0+, Vite 7.2.4+, TypeScript 5.9.3+, Tailwind CSS 4.1.18+
Mobile (Planned): Flutter (ARCHIVED - replaced by web MVP)
```

---

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
    ├─ character_cards (people in user's life)
    ├─ world_events (life milestones, NeuralRP-style)
    └─ entity_mentions (tracking)
```

### Navigation Flow
```
Counselor Selection → Chat Screen
                        ↓
                Settings Button (⚙️) → Card Inventory Modal
                                            ↓
                        Self | Character | World Tabs
                                            ↓
                                    Card List → Card Detail (Edit Mode)

Chat Screen Header (counselor name) → CounselorInfoModal
```

---

## Key Design Patterns

### API Response Pattern
```python
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
```

### Database Pattern
Use context manager for connections:
```python
with self._get_connection() as conn:
    cursor = conn.execute("SELECT * FROM table WHERE id = ?", (id,))
    return dict(cursor.fetchone())
```

### LLM Integration
```python
response = await simple_llm_client.chat_completion(
    messages=messages,
    model="anthropic/claude-3-haiku",
    temperature=0.7
)
```

---

## Phase Status

| Phase | Status | Key Deliverables |
|-------|--------|------------------|
| 1 | ✅ | Database schema, unified card methods |
| 2 | ✅ | Card Generator, Guide System |
| 3 | ✅ | Unified Card API (CRUD, search, toggle) |
| 4 | ✅ | Auto-updater, Canon Refactor (removed in pivot) |
| 5 | ✅ | Entity Detection, Context Assembly, Guide System |
| 6 | ✅ | Pytest Infrastructure (test isolation, LLM mocking, fixtures) |
| 7 | ✅ | New Test Coverage (DB, API, E2E) - 89/89 tests passing (100%), 68% coverage |
| 8 | ❌ | Flutter UI Development (ARCHIVED - replaced by web MVP) |
| 9 | ⏳ | Garden Minigame (optional - deferred) |

### Frontend Phases (Web MVP)

| Phase | Status | Key Deliverables |
|-------|--------|------------------|
| | 0 | ✅ | Project Setup (React + Vite + Tailwind, GBA colors, VT323 font) |
| | 1 | ✅ | Counselor Selection Screen (4 cards, Settings button, navigation) |
| | 2 | ✅ | Chat Interface (UI complete, backend integration complete) |
| | 3 | ✅ | Card Inventory Modal (tabs, search, card list, pin/auto-update) |
| | 4 | ✅ | Card Editing (detail view, inline editing, validation) |
| | 5 | ✅ | Polish & Mobile Optimization (responsive, loading states, animations) |
| | 6 | ✅ | Testing, Bug Fixes, Vercel Deployment (production live) |

---

## Critical Files

### Documentation

| File | Purpose |
|------|---------|
| `AGENTS.md` | LLM-optimized project documentation (this file) |
| `TECHNICAL.md` | Detailed technical breakdown |
| `CHANGELOG.md` | Project changelog with version history |
| `README.md` | Project overview for GitHub |

### Backend Core

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, route registration |
| `backend/app/db/database.py` | All DB operations (650+ lines) |
| `backend/app/api/cards.py` | Card management endpoints |
| `backend/app/api/guide.py` | Guide onboarding endpoints |
| `backend/app/api/session_analyzer.py` | Session analysis endpoint |
| `backend/app/services/card_generator.py` | LLM card generation (max_tokens=4000) |
| `backend/app/services/guide_system.py` | Organic guide conversation system |
| `backend/app/services/card_updater.py` | Auto-update service |
| `backend/app/services/simple_llm_fixed.py` | HTTP client for OpenRouter API |
 | `backend/app/models/schemas.py` | Pydantic models |
 | `backend/app/config/core_truths.py` | Universal principles for all personas (non-clinical AI companion) |
 | `backend/data/personas/*.json` | Persona definitions (who_you_are, your_vibe, your_worldview) |
 | `backend/scripts/seed_personas.py` | Persona JSON → DB sync script (supports is_hidden) |
 | `backend/migrations/005_add_hidden_flag.py` | Add is_hidden column for Easter egg counselors |
 | `backend/schema.sql` | Database schema |
 | `backend/pytest.ini` | Pytest configuration (asyncio, markers, test discovery, coverage) |

### Frontend Core (Web MVP)

| File | Purpose |
|------|---------|
| `gameapy-web/src/App.tsx` | Root component with routing |
| `gameapy-web/src/main.tsx` | App entry point |
| `gameapy-web/src/index.css` | Global styles + Tailwind v4 |
| `gameapy-web/src/contexts/AppContext.tsx` | Global state (client ID, counselor, inventory) |
| `gameapy-web/src/services/api.ts` | HTTP client for backend API |
| `gameapy-web/src/screens/CounselorSelection.tsx` | Counselor selection screen ✅ |
| `gameapy-web/src/screens/ChatScreen.tsx` | Chat interface (UI complete, with polish) ✅ |
| `gameapy-web/src/screens/CardInventoryModal.tsx` | Card inventory modal (complete with edit) ✅ |
| `gameapy-web/src/screens/GuideScreen.tsx` | Organic card creation flow ✅ |
| `gameapy-web/src/components/ui/button.tsx` | Button component with GBA styling |
| `gameapy-web/src/components/counselor/CounselorCard.tsx` | Counselor card component |
 | `gameapy-web/src/components/counselor/CounselorInfoModal.tsx` | Counselor details modal with counselor-specific colors ✅ |
 | `gameapy-web/src/components/shared/Toast.tsx` | Toast notification component ✅ |
 | `backend/data/personas/Deirdre.json` | Deirdre persona (hidden Easter egg counselor) |
 | `gameapy-web/package.json` | Dependencies (React 19.2.0+, Vite 7.2.4+, Tailwind 4.1.18+) |
| `gameapy-web/vite.config.ts` | Vite build configuration |
| `gameapy-web/vercel.json` | Vercel deployment configuration |
| `gameapy-web/.env.production` | Production environment variables |

### Test Infrastructure

| File | Purpose | Tests |
|------|---------|--------|
| `backend/tests/conftest.py` | Test fixtures (DB isolation, LLM mocking, sample data) | - |
| `backend/tests/test_entity_detector.py` | Entity detection tests | 8 tests ✅ |
| `backend/tests/test_context_assembler.py` | Context assembly tests | 6 tests ✅ |
| `backend/tests/test_guide_system.py` | Guide system tests | 6 tests ✅ |
| `backend/tests/test_database.py` | Database CRUD tests | 20 tests ✅ |
| `backend/tests/test_api_cards.py` | Cards API tests | 17 tests ✅ |
| `backend/tests/test_api_chat.py` | Chat API tests | 11 tests ✅ |
| `backend/tests/test_api_guide.py` | Guide API tests | 8 tests ✅ |
| `backend/tests/test_api_session_analyzer.py` | Session analyzer tests | 5 tests ✅ |
| `backend/tests/test_e2e_flows.py` | E2E flow tests | 6 tests ✅ |
| `backend/tests/test_llm.py` | Real LLM integration tests | 3 tests ✅ |

---

## Important Constraints

1. **Evolution, Not Replacement**: Extend tables, never drop
2. **Invisible Auto-Updates**: No approval workflow
3. **Per-Card Toggle**: Users can freeze specific cards
4. **Conflict Resolution**: AI never overwrites user edits (skips updates)
5. **Full Cards v1**: Claude/GPT have 100k+ context (no capsules)
6. **Simplified World Events**: NeuralRP-style (key_array, is_canon_law)
7. **Keyword-Based Entity Detection**: No embeddings, simple and fast
8. **Documentation Updates**: Update AGENTS.md and TECHNICAL.md, never create new phase summary files
9. **Persona Structure**: Personas use non-therapeutic field names (who_you_are, your_vibe, your_worldview). DB columns (specialization, therapeutic_style, credentials) are repurposed for compatibility. Core truths in `core_truths.py` apply universally.

---

## API Endpoints Reference

**Cards** (`/api/v1/cards`):
- `POST /generate-from-text` - Generate from plain text
- `POST /save` - Save to database
- `PUT /{card_type}/{id}` - Partial update
- `PUT /{card_type}/{id}/pin` - Pin card (always load)
- `PUT /{card_type}/{id}/unpin` - Unpin card
- `PUT /{card_type}/{id}/toggle-auto-update` - Toggle auto-update
- `GET /search` - Search across types
- `DELETE /{card_type}/{id}` - Delete card

**Clients** (`/api/v1/clients/{id}`):
- `GET /cards` - List all cards (paginated)

**Guide** (`/api/v1/guide`):
- `POST /conversation/start` - Start organic conversation
- `POST /conversation/input` - Process user input (may suggest card)
- `POST /conversation/confirm-card` - Create suggested card

**Sessions** (`/api/v1/sessions/{id}`):
- `POST /analyze` - Analyze session and auto-update cards

**Chat** (`/api/v1/chat`):
- `POST /chat` - Send message with streaming SSE response (auto-loads context)
- Returns SSE stream with chunks:
  - Content: `{"type": "content", "content": "..."}`
  - Done: `{"type": "done", "data": {"cards_loaded": N, "counselor_switched": bool, "new_counselor": {...}}}`
  - Error: `{"type": "error", "error": "..."}`

**Farm** (`/api/v1/farm/*`):
- All endpoints available but hidden from main flow (optional)

---

## Color Palette (GBA-Style)

```
Background: #E8D0A0 (warm off-white)
Grass: #88C070 (bright lime)
Borders: #306850 (forest green)
UI Background: #F8F0D8 (cream)
Highlight: #F8D878 (yellow)
Text: #483018 (dark brown)
```

---

## Quick Start

```bash
cd backend
pip install -r requirements.txt
python main.py
# Server at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Testing

```bash
cd backend
# Run all tests
pytest tests/ -v

# Run by category
pytest tests/ -m unit -v          # Unit tests only
pytest tests/ -m integration -v   # Integration tests only
pytest tests/ -m e2e -v           # E2E tests

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Test Infrastructure

- **Database Isolation**: File-based test DB (`gameapy_test.db`) with per-test truncation
- **LLM Mocking**: Deterministic mocks for success/fallback/error/no-card scenarios
- **Per-Request Clients**: No global httpx.AsyncClient caching (prevents event loop issues)
- **Test Categories**: `@pytest.mark.unit/integration/e2e/slow/llm`
- **Fixtures**: Sample data (client, counselor, cards, sessions) and API test client
- **Coverage**: pytest-cov for code coverage reporting (current: 68%)

### Test Results

**All 89 tests passing** (100% pass rate):
- Database tests: 20 tests ✅
- Entity detector tests: 8 tests ✅
- Context assembler tests: 6 tests ✅
- Guide system tests: 6 tests ✅
- Cards API tests: 17 tests ✅
- Chat API tests: 11 tests ✅
- Guide API tests: 8 tests ✅
- Session analyzer tests: 5 tests ✅
- E2E flow tests: 6 tests ✅
- LLM integration tests: 3 tests ✅

See `PHASE7_TEST_FIXES_SUMMARY.md` for full details on test infrastructure.

---

## Deployment

### Production URLs
- **Frontend**: https://gameapy-web.vercel.app
- **Backend**: https://gameapy-backend-production.up.railway.app

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

### Vercel Configuration
- Build: `npm run build`
- Output: `dist/`
- Framework: Vite
- Environment Variable: `VITE_API_BASE_URL=https://gameapy-backend-production.up.railway.app`
- Auto-deploy on push to `main` branch

---

**Questions?** Check `TECHNICAL.md` or `WEB_MVP_DEVELOPMENT_PLAN.md` for comprehensive documentation.
