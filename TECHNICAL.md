# Gameapy Technical Documentation

**Version**: 3.6.0
**Last Updated**: 2026-02-11
**Status**: Backend Complete (Phases 1-7), Web MVP Complete (Phases 0-6), Production Live

---

## Overview

Gameapy is infrastructure for being known - an AI relationship that evolves with depth based on what you share. It combines persona-driven companionship with GameBoy-style pixel art aesthetics, featuring character cards that capture people and events in your life, AI personas with unique personalities, and an organic conversation system that grows with you.

### Core Philosophy

1. **Cards Support Chat** (not vice versa) - Memory serves conversation
2. **Transparency Without Friction** - View/edit anytime, updates invisible
3. **User Sovereignty** - Per-card auto-update toggles, explicit consent for creation
4. **Organic Growth** - No forced phases, conversation follows user's lead

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
├── pytest.ini            # Test configuration
├── AGENTS.md            # LLM-optimized quick reference
└── TECHNICAL.md         # This file

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

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  React Web App (Vite)                      │
│             (GameBoy-style pixel UI)                        │
│  - Counselor Selection (2x2 color grid)                     │
│  - Chat Screen (iMessage bubbles)                           │
│  - Card Inventory Modal (tabs + search + edit)              │
│  - Guide Screen (organic card creation)                     │
└────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                        │
│                   (Railway - Production)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │  API Routes  │  │  LLM Client  │  │ Database  │ │
│  │  (chat/     │  │  (OpenRouter)│  │ (SQLite) │ │
│  │   cards/    │  └──────────────┘  └──────────┘ │
│  │   guide/)   │                                     │
│  └─────────────┘                                     │
└────────────────────────┬────────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │   OpenRouter API    │
            │  (Claude, GPT, etc) │
            └──────────────────────┘
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
Guide Flow: Chat → "Create Cards" button → GuideScreen → Card Suggestion → Confirm
```

---

## Completed Features

### Phase 1: Database Schema & Migration ✅

**Status**: Complete (2026-02-07)  
**Tests**: 20/20 passing

**Database Tables**:
- `self_cards` - Roleplay-style user cards (one per client)
- `character_cards` - People in user's life with personality profiles
- `world_events` - Life events (achievements, trauma, transitions, unresolved)
- `entity_mentions` - Keyword frequency tracking

**Key Features**:
- Migration tracking system with auto-apply on startup
- Keyword-only search (no vector embeddings - v3.1 pivot)
- Auto-update toggle mechanism (`auto_update_enabled` column)
- Pin system (`is_pinned` column) for "always load" cards
- Comprehensive indexing for performance

**Schema Evolution**:
- Extended `character_cards`: Added `entity_id`, `mention_count`, `last_mentioned`, `first_mentioned`
- All tables use evolution pattern (extend, never drop)

---

### Phase 2: Card Generator Service ✅

**Status**: Complete (2025-02-07)  
**Tests**: 17 tests created

**CardGenerator Service** (`backend/app/services/card_generator.py`):
- LLM-based plain text → structured JSON conversion (max_tokens=4000)
- Supports 3 card types: `self`, `character`, `world`
- Retry logic: 3 attempts with exponential backoff
- Fallback: Returns plain text card if JSON parsing fails
- Logs failures to `performance_metrics` table
- Uses `openrouter/free` model by default

**Guide System** (`backend/app/services/guide_system.py`):
- Organic conversation (no forced phases)
- Background card topic detection
- Explicit confirmation before card creation
- Creates real Guide counselor profile
- Farm discovery after 5+ sessions

**API Endpoints**:
- `POST /api/v1/cards/generate-from-text` - Generate card preview
- `POST /api/v1/cards/save` - Save card to database
- `POST /api/v1/guide/conversation/start` - Start guide conversation
- `POST /api/v1/guide/conversation/input` - Process user input
- `POST /api/v1/guide/conversation/confirm-card` - Create suggested card

---

### Phase 3: Unified Card Management API ✅

**Status**: Complete  
**Tests**: 17/17 passing

**Unified Card List**:
- `GET /api/v1/clients/{id}/cards` - Retrieves all card types (self, character, world)
- Pagination support with `page_size=all` option
- Unified response format for all card types

**Card Management**:
- `PUT /api/v1/cards/{card_type}/{id}` - Partial updates for any card type
- `PUT /api/v1/cards/{card_type}/{id}/pin` - Pin card (always load)
- `PUT /api/v1/cards/{card_type}/{id}/unpin` - Unpin card
- `PUT /api/v1/cards/{card_type}/{id}/toggle-auto-update` - Per-card toggle
- `DELETE /api/v1/cards/{card_type}/{id}` - Delete any card type

**Search**:
- `GET /api/v1/cards/search` - Cross-type search with filtering
- Type-specific filtering (self, character, world)
- Client ID filtering support

**Bug Fixes**:
- Character card name synchronization (column → JSON payload)
- Boolean type conversion for SQLite integer fields
- Test URL path corrections

---

### Phase 4: Auto-Update System ✅

**Status**: Complete  
**Tests**: 19/19 passing

**Card Updater Service** (`backend/app/services/card_updater.py`):
- Invisible auto-updates with timestamped evolution
- Confidence thresholds: batch ≥ 0.5, per-field ≥ 0.7
- Conflict resolution: personality (merge+dedupe), patterns (append)
- Skip updates if user edited card (detected via change log)
- Change logging with `changed_by` tracking (user vs system)

**Session Analysis**:
- `POST /api/v1/sessions/{id}/analyze` - Analyze session and auto-update cards
- Returns `cards_updated` counter
- Integrates with entity detection and context assembly

---

### Phase 5: Entity Detection ✅

**Status**: Complete  
**Tests**: 8/8 passing (100% pass rate)

**Entity Detector Service** (`backend/app/services/entity_detector.py`):
- Simplified keyword matching (no embeddings or semantic search)
- Character cards: Exact name matching + relationship keywords
- World events: Title matching + `key_array` keyword matching
- Deduplication by card ID
- Relationship categories: family, friend, coworker, romantic

**Relationship Keywords**:
- Family: mom, mother, dad, father, parent, brother, sister
- Friends: friend, best friend, buddy, pal
- Romantic: partner, boyfriend, girlfriend, wife, husband
- Work: boss, manager, coworker, colleague, teacher

---

### Phase 6: Context Assembly ✅

**Status**: Complete  
**Tests**: 6/6 passing (100% pass rate)

**Context Assembler Service** (`backend/app/services/context_assembler.py`):
- Loads full cards into LLM prompts (no capsule optimization)
- Layered loading with priorities:
  1. Always: Self card
  2. Always: Pinned cards (user marks "keep in mind")
  3. Always: Cards mentioned in current session
  4. Configurable: Top N cards by recency (default: 5 sessions)
- Proper exclusion of duplicates (self/pinned don't appear in recent)
- Configurable via `RECENT_CARD_SESSION_LIMIT` (1-20)

**Integration**:
- Wired into `/api/v1/chat` endpoint
- Returns `cards_loaded` count in chat response
- Logs entity mentions to database

---

### Phase 7: Pytest Testing Infrastructure ✅

**Status**: Complete (2026-02-08)  
**Tests**: 89/89 passing (100% pass rate)  
**Coverage**: 68% overall

**Test Infrastructure** (`backend/tests/`):
- File-based test DB (`gameapy_test.db`) with per-test truncation
- LLM mocking with deterministic fixtures (success, fallback, error)
- Per-request HTTP clients (no global state pollution)
- Test categories: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`, `@pytest.mark.llm`
- Coverage reporting with pytest-cov

**Test Categories**:
- Database: 20 tests ✅
- Entity detector: 8 tests ✅
- Context assembler: 6 tests ✅
- Guide system: 6 tests ✅
- Cards API: 17 tests ✅
- Chat API: 11 tests ✅
- Guide API: 8 tests ✅
- Session analyzer: 5 tests ✅
- E2E flows: 6 tests ✅
- LLM integration: 3 tests ✅

**Key Achievements**:
- Fixed module reload issues with monkeypatch fixtures
- Eliminated global httpx.AsyncClient caching (per-request clients)
- Achieved 100% test pass rate (from 89.9%)
- Increased coverage from 44% to 68%

---

### Web MVP Phases 0-6 ✅

**Status**: Complete (2026-02-09)  
**Production**: https://gameapy-web.vercel.app

#### Phase 0: Project Setup ✅
- React 19.2.0+ with Vite 7.2.4+
- TypeScript 5.9.3+ for type safety
- Tailwind CSS 4.1.18+ with GBA color palette
- VT323 retro font from Google Fonts
- Project structure: components, contexts, screens, services, types, utils

#### Phase 1: Counselor Selection ✅
- 2x2 color block grid design (replaced card-based UI)
- Counselor selection with visual feedback
- "View Cards" button (stacked cards icon) to access inventory
- Responsive layout for mobile/tablet/desktop
- Loading states and error handling

#### Phase 2: Chat Interface ✅
- iMessage-style message bubbles (rounded, with colors)
- Counselor name as clickable link → CounselorInfoModal
- Real-time message streaming
- Auto-load context (self, pinned, mentioned, recent cards)
- Backend integration with `/api/v1/chat` endpoint
- Toast notifications for success/error states

#### Phase 3: Card Inventory Modal ✅
- Tab system: Self | Character | World
- Search functionality (keyword-based)
- Card list with filtering
- Pin/unpin cards
- Toggle auto-update per card
- Responsive modal with scrollable content

#### Phase 4: Card Detail & Editing ✅
- Card detail view with all fields
- Inline editing with validation
- Save changes to backend
- Unsaved changes confirmation
- Real-time feedback on API calls

#### Phase 5: Polish & Mobile Optimization ✅
- Smooth fade-in animations (0.3s) for all screens
- Button hover/active animations with visual feedback
- All touch targets meet WCAG AA (44x44px minimum)
- Mobile keyboard overlap prevention (flex-shrink-0 on headers/footers)
- Responsive layouts for all screen sizes
- Loading spinners and error messages
- Retry buttons for all failed API requests

#### Phase 6: Testing, Bug Fixes, Vercel Deployment ✅
- Manual testing across mobile/tablet/desktop
- Bug fixes: API URL corrections, state management, type errors
- Vercel configuration with Railway backend integration
- Auto-deploy on push to `main` branch
- Production environment variables configured

#### Latest Updates (2026-02-11)
- **Field-Level Timestamps**: CardMetadata utility tracks individual field changes with smart recency indicators
- **Recency Indicators**: [new], [updated today], [updated this week], [updated 2 weeks ago], [updated this month], [established]
- **Source Tracking**: Distinguishes between LLM-created and user-edited fields for transparency
- **LLM Context Enhancement**: Temporal awareness helps AI distinguish fresh vs. established information
- **GuideScreen**: Organic card creation flow with conversational onboarding
- **CounselorInfoModal**: View counselor details from chat screen
- **Toast Component**: User notifications (success/error/info) with auto-dismiss
- **Auto-Session Analysis**: Every 5 messages, trigger card updates with toast notification
- **Session Message Counting**: Track messages per session for analysis triggers
- **Global State**: Guide flow state (showGuide, guideSessionId) in AppContext

---

## Card System

### Three Card Types

**Self Card** (1 per user)
- Captures: personality, traits, interests, values, goals, challenges
- Created: During onboarding or manually
- Updates: Auto-updates enabled by default
- Pin: Can be pinned to always load

**Character Cards** (many per user)
- Captures: People in user's life (family, friends, coworkers)
- Fields: name, relationship_type, personality, patterns, emotional_state
- Created: Guide suggests → user confirms, or manually
- Updates: Auto-updates enabled by default
- Pin: Can be pinned to always load

**Life Events** (world_events table)
- Captures: Important moments, achievements, challenges, transitions
- Created: Guide suggests → user confirms, or manually
- Updates: Auto-updates enabled by default
- Pin: Can be pinned to always load

### Context Loading Rules

1. **Always**: Self card
2. **Always**: Pinned cards (user marks "keep in mind")
3. **Always**: Cards mentioned in current session
4. **Configurable**: Top N cards by recency (default: 5 sessions)

### Field-Level Timestamps

Cards now include embedded metadata tracking individual field timestamps:

**Metadata Structure:**
```json
{
  "_metadata": {
    "personality": {
      "first_seen": "2026-01-15T10:30:00",
      "last_updated": "2026-02-11T14:22:00",
      "update_count": 3,
      "source": "llm"  // or "user"
    }
  }
}
```

**Recency Indicators (shown to LLM):**
- `[new]` - Updated in last hour
- `[updated today]` - Updated today
- `[updated this week]` - Updated within 7 days
- `[updated 2 weeks ago]` - Updated within 14 days
- `[updated this month]` - Updated within 30 days
- `[established]` - Older than 30 days

**Behavior:**
- **LLM creates card**: Initialize all fields with current timestamp, source: "llm"
- **LLM updates card**: Only update timestamp for changed fields, source: "llm"
- **User edits card**: Reset all field timestamps, source: "user"

**Benefits:**
- ~15-20 tokens per card overhead (minimal cost)
- AI can distinguish fresh vs. established information
- Reduces contradictions in conversations
- Transparent tracking of who modified what

**Implementation:**
- `app/utils/card_metadata.py` - Core CardMetadata class
- `app/services/card_generator.py` - Initializes timestamps on creation
- `app/services/card_updater.py` - Tracks field changes during LLM updates
- `app/api/chat.py` - Formats context with recency indicators
- `app/api/cards.py` - Resets metadata on user edits

---

## Database Schema

### Database Configuration

The database path is configurable via environment and supports Railway persistent volumes:

```python
# Priority order (app/core/config.py)
1. DATABASE_PATH env variable (explicit override)
2. RAILWAY_VOLUME_MOUNT_PATH env variable (Railway auto-injected)
3. Default: "gameapy.db" (local development)
```

**Production (Railway with volume):**
- Path: `/app/data/gameapy.db`
- Volume: `gameapy-backend-volume`
- Mount: `/app/data`
- Environment: `RAILWAY_VOLUME_MOUNT_PATH=/app/data` (auto-injected)

**Development (Local):**
- Path: `gameapy.db` (current directory)
- No volume needed

**Database Initialization** (`app/db/database.py`):
```python
def __init__(self, db_path: Optional[str] = None):
    if db_path is None:
        from app.core.config import settings
        db_path = settings.database_path or "gameapy.db"
    
    self.db_path = db_path
    
    # Log database location for debugging
    print(f"[INFO] Database path: {db_path}")
    
    # Ensure database directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"[INFO] Created database directory: {db_dir}")
```

### Entity Relationships

```
client_profiles (1) ────── (n) sessions (n) ────── (1) counselor_profiles
                               │
                               │ messages (n)
                               │
client_profiles (1) ────── (n) character_cards
client_profiles (1) ────── (1) self_cards
client_profiles (1) ────── (n) world_events

All entities ────── (n) entity_mentions
All entities ────── (n) change_log
```

### Key Tables

#### Client Profiles
```sql
client_profiles (
    id INTEGER PRIMARY KEY,
    entity_id TEXT UNIQUE,
    name TEXT,
    profile_json TEXT,
    tags TEXT,
    is_active BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

#### Self Cards
```sql
self_cards (
    id INTEGER PRIMARY KEY,
    client_id INTEGER UNIQUE,
    card_json TEXT,
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

#### Character Cards
```sql
character_cards (
    id INTEGER PRIMARY KEY,
    client_id INTEGER,
    card_name TEXT,
    relationship_type TEXT,
    card_json TEXT,
    entity_id TEXT UNIQUE,
    mention_count INTEGER DEFAULT 0,
    last_mentioned TIMESTAMP,
    first_mentioned TIMESTAMP,
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

#### World Events
```sql
world_events (
    id INTEGER PRIMARY KEY,
    client_id INTEGER,
    entity_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    key_array TEXT NOT NULL,
    description TEXT NOT NULL,
    event_type TEXT NOT NULL,
    is_canon_law BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE,
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

---

## API Endpoints Reference

### Cards API (`/api/v1/cards`)
- `POST /generate-from-text` - Generate from plain text (preview)
- `POST /save` - Save to database
- `PUT /{card_type}/{id}` - Partial update
- `PUT /{card_type}/{id}/pin` - Pin card (always load)
- `PUT /{card_type}/{id}/unpin` - Unpin card
- `PUT /{card_type}/{id}/toggle-auto-update` - Toggle auto-update
- `GET /search` - Search across types
- `DELETE /{card_type}/{id}` - Delete card

### Guide API (`/api/v1/guide`)
- `POST /conversation/start` - Begin organic conversation
- `POST /conversation/input` - Process user input (may suggest card)
- `POST /conversation/confirm-card` - Create suggested card

### Chat API (`/api/v1/chat`)
- `POST /chat` - Send message, get AI response (with context loading)
  - Request body: `{"session_id": 123, "message_data": {"role": "user", "content": "Hello"}}`
  - Response: `{"ai_response": "...", "cards_loaded": 5}`
- `POST /chat/stream` - Stream AI response (Server-Sent Events)

### Sessions API (`/api/v1/sessions/{id}`)
- `POST /analyze` - Analyze session and auto-update cards
  - Response: `{"cards_updated": 3}`

### Farm API (`/api/v1/farm/*`)
- All endpoints available but hidden from main flow (optional feature)
- Game state, farm items, shop functionality

### Clients API (`/api/v1/clients/{id}`)
- `GET /cards` - List all cards (paginated)

---

## Configuration

### Environment Variables

```bash
# OpenRouter API Key
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional: Override default model
DEFAULT_MODEL=anthropic/claude-3-haiku
FALLBACK_MODEL=openai/gpt-3.5-turbo

# Optional: Adjust LLM parameters
MAX_TOKENS=1000
TEMPERATURE=0.7
TIMEOUT=30

# Recent card session limit (1-20)
RECENT_CARD_SESSION_LIMIT=5

# Debug mode
DEBUG=false
```

### Running Backend

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Start server
python main.py

# Server at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Running Frontend

```bash
# Install dependencies
cd gameapy-web
npm install

# Start dev server
npm run dev

# Dev server at http://localhost:5173

# Build for production
npm run build

# Preview production build
npm run preview
```

### Running Tests

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

### Backend Deployment (Railway)
- Repository: https://github.com/NeuralRP/gameapy-backend
- Runtime: Python 3.11+
- Build command: `pip install -r requirements.txt`
- Start command: `python main.py`
- Environment variables: `OPENROUTER_API_KEY`, `RAILWAY_VOLUME_MOUNT_PATH` (auto-injected)
- Auto-deploy on push to `main` branch
- **Persistent Volume**: Railway volume mounted at `/app/data` for database persistence
  - Database path: `/app/data/gameapy.db` (production)
  - Auto-created directory: `/app/data/`
  - Database location logged on startup: `[INFO] Database path: <path>`
  - Configuration: `DATABASE_PATH` in `Settings` class with fallback to `gameapy.db` (local)
  - Setup guide: `RAILWAY_VOLUME_SETUP.md` with CLI commands
  - Resolves: Character cards deleted on deployment (ephemeral storage issue)
- **Healthcheck Fix**: Database initialization moved to FastAPI startup event
  - App starts immediately and responds to healthchecks
  - Database initialization runs in background after volume is mounted
  - Resolves: "service unavailable" errors during Railway deployment

### Frontend Deployment (Vercel)
- Repository: https://github.com/NeuralRP/gameapy-web
- Framework: Vite
- Build: `npm run build`
- Output: `dist/`
- Environment variable: `VITE_API_BASE_URL=https://gameapy-backend-production.up.railway.app`
- Auto-deploy on push to `main` branch

---

## Counselor Personas

Four complete personas seeded with full profiles:

1. **Marina** - New-Age Spiritual Guide
   - Style: Feminine, peaceful, grounded in eastern spirituality and nature
   - Focus: Mental, emotional, and physical wellness; positive energy; horoscopes/astrology
   - 2 session examples: Energy grounding techniques; Karmic lesson reframing

2. **Coach San Mateo** - Thoughtful Motivational Coach
   - Style: Verbal affirmation, pragmatic, actionable, humorous
   - Focus: Believes in user, breaks problems into manageable steps
   - 2 session examples: Affirmation + actionable pieces; Self-awareness affirmation + small step

3. **Health and Wellness Coach** - Holistic Wellness Specialist
   - Style: Evidence-based, empowering, focuses on root causes
   - Focus: Wellness Wheel (7 dimensions), functional/lifestyle medicine, proactive daily actions
   - 2 session examples: Wellness Wheel approach + physical foundations; Functional medicine lens + proactive action

4. **Father Red Oak** - Wise Ancient Tree
   - Style: Patient, warm, grandfatherly, deeply experienced
   - Focus: Long memory, thoughtful feedback on both trivial and important matters
   - 2 session examples: Tree longevity metaphor; Normalizes patterns + genuine interest

Each persona includes:
- **Core fields**: who_you_are, your_vibe, your_worldview (non-therapeutic language)
- **Session template**: Opening greeting for new chats
- **Session examples**: user_situation, your_response, approach (shows how they think)
- **Tags**: Categorization (ocean, sports, mythology, etc.)
- **Crisis protocol**: Safety resources with US hotlines (988, Crisis Text Line, SAMHSA)

**Core Truths** (from `backend/app/config/core_truths.py`):
- Universal principles applied to ALL personas
- Non-clinical AI companion philosophy
- Remember user through character/world cards
- Be helpful (not performative), have opinions, be resourceful
- Treat user's life with respect as a guest

---

## Frontend Architecture

### React Components

**UI Components** (`src/components/ui/`):
- `Button` - GBA-styled button with hover/active states
- Loading spinner component

**Counselor Components** (`src/components/counselor/`):
- `CounselorCard` - Counselor selection card (archived, replaced by color blocks)
- `CounselorInfoModal` - Modal showing counselor details

**Shared Components** (`src/components/shared/`):
- `LoadingSpinner` - Loading state indicator
- `Toast` - Notification toast (success/error/info)
- `ErrorMessage` - Error display with retry button

### Screens

**CounselorSelection** (`src/screens/CounselorSelection.tsx`):
- 2x2 color block grid for counselor selection
- "View Cards" button (stacked cards icon)
- Loading states and error handling
- Responsive design

**ChatScreen** (`src/screens/ChatScreen.tsx`):
- iMessage-style message bubbles
- Counselor name as clickable link
- Auto-session analysis every 5 messages
- Toast notifications for card updates
- Real-time message streaming

**CardInventoryModal** (`src/screens/CardInventoryModal.tsx`):
- Tab system: Self | Character | World
- Search functionality
- Card list with filtering
- Pin/unpin cards
- Toggle auto-update per card
- Card detail view with editing

**GuideScreen** (`src/screens/GuideScreen.tsx`):
- Organic card creation flow
- Conversational onboarding
- Card suggestion with confirm/decline
- Integrated with guide API endpoints

### State Management

**AppContext** (`src/contexts/AppContext.tsx`):
- `clientId` - Auto-generated with localStorage
- `counselor` - Selected counselor
- `sessionId` - Current chat session
- `showInventory` - Inventory modal visibility
- `showGuide` - Guide screen visibility
- `guideSessionId` - Guide conversation session
- `sessionMessageCount` - Track messages for auto-analysis
- `toast` - Toast notifications

### API Client

**ApiService** (`src/services/api.ts`):
- HTTP client with Axios-like interface
- Error handling with retry logic
- API endpoint constants
- Type-safe request/response handling

---

## Design Patterns

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
    temperature=0.7,
    max_tokens=4000
)
```

### React State Pattern
```typescript
const { counselor, showInventory, setShowInventory, toast, showToast } = useApp();
```

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

### Color Usage Guide
- Chat background: #E8D0A0 (warm, cozy)
- Chat text: #483018 (high contrast, readable)
- UI borders: #306850 (forest green accent)
- Selected/highlighted items: #F8D878 (warm yellow)
- Card editor background: #F8F0D8 (off-white cream)
- Inventory overlay: #D8C8A8 (85% opacity)
- Toast notifications: success (#88C070), error (#F87070), info (#78C0D8)

---

## Technical Decisions

### Why OpenRouter?
- Model flexibility: Access to Claude, GPT, Llama, etc.
- Cost-effective: Pay per use, no commitments
- Easy fallback: Switch models if one is down
- Future-proof: Can add new models without code changes

### Why SQLite?
- Local-first: No cloud database needed initially
- Zero configuration: No separate database server
- Mobile-friendly: Works on iOS/Android
- Simplicity: Easy to backup and migrate
- Keyword-only search: Fast, simple matching (no embeddings)

### Why FastAPI?
- Async support: Natural fit for OpenRouter calls
- Auto docs: `/docs` endpoint for API exploration
- Type safety: Pydantic validation
- Performance: Faster than Flask/Django

### Why React + Vite?
- Mature ecosystem: Large community and library support
- Fast development: Vite's instant HMR
- Type safety: TypeScript catches bugs early
- Easy deployment: Simple static site for Vercel
- Mobile-first: Responsive design patterns

### Why Tailwind CSS v4?
- Utility-first: Rapid UI development
- GBA palette: Easy color customization
- Small bundle: Purge unused styles
- Great DX: Intellisense and visual consistency

---

## Testing

### Test Categories

- **Unit Tests**: Pure logic tests (entity detector, data structures)
- **Integration Tests**: API and DB tests (context assembler, guide system)
- **E2E Tests**: Full user flows (onboarding, card creation, chat)
- **LLM Tests**: Real LLM integration tests (requires API key)

### Coverage Report

Current coverage: 68% overall

Critical modules:
- Database: 75% ✅
- Card generator: 88% ✅
- Context assembler: 89% ✅
- Entity detector: 100% ✅
- Guide system: 92% ✅
- Simple LLM client: 93% ✅

---

## Next Steps

### Future Enhancements

1. **Test Coverage**: Increase from 68% to 75%+
2. **On-device LLM**: Research Phi/Llama models for offline mode
3. **Cloud Sync**: User authentication, encrypted data backup, cross-device sync
4. **Mobile App**: Flutter or React Native for native mobile experience
5. **Garden Minigame**: Optional gamification feature (deferred)
6. **Voice Input**: Speech-to-text for chat messages
7. **Card Templates**: Pre-built card structures for common use cases

---

## Dependencies

### Backend

- `fastapi==0.104.1` - Web framework
- `uvicorn[standard]==0.24.0` - ASGI server
- `httpx==0.25.2` - HTTP client
- `pydantic==2.5.0` - Data validation
- `pydantic-settings==2.1.0` - Configuration
- `python-dotenv==1.0.0` - Environment variables
- `pytest==7.4.3` - Testing framework
- `pytest-cov==4.1.0` - Coverage reporting
- `pytest-asyncio==0.21.1` - Async test support

### Frontend

- `react==19.2.0` - UI framework
- `vite==7.2.4` - Build tool
- `typescript==5.9.3` - Type safety
- `tailwindcss==4.1.18` - CSS framework
- `lucide-react` - Icon library
- `axios` - HTTP client (or custom fetch wrapper)

---

## License

MIT License

---

**Last Updated**: 2026-02-09  
**Version**: 3.4.0  
**Status**: Backend Complete (Phases 1-7), Web MVP Complete (Phases 0-6), Production Live
