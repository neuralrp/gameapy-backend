# Changelog

All notable changes to Gameapy (backend and web frontend) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Backend (gameapy-backend)

#### Added
- **Streaming Chat**: SSE (Server-Sent Events) for real-time chat responses
  - `chat_completion_stream()` method in SimpleLLMClient for streaming LLM responses
  - Streaming `/api/v1/chat/chat` endpoint with real-time chunk delivery
  - Support for content chunks, metadata chunks, and error chunks
  - Counselor switching support in streaming responses
- `get_character_card_by_id()` helper for card updates by ID
- Field name mapping for card updates ('name' → 'card_name')
- 5 new streaming tests (content chunks, metadata, error handling, counselor switching, empty response)
- All 99 tests passing (was 89, added 10 new tests)
- Schema migrations 004-006 for database improvements
- Auto-seed personas feature on startup
- Context formatting: Convert JSON cards to human-readable prose for better LLM comprehension
- `is_hidden` flag to counselors table for Easter egg functionality
- Easter egg feature: "Summon Deirdre" - typing this phrase in Marina's chat switches to hidden counselor Deirdre
- Response guidance to core truths
- Detailed logging to `seed_personas.py` for debugging
- Proper `ChatRequest` model for chat endpoint request body parsing

#### Changed
- Removed JSON response from `/api/v1/chat/chat` endpoint, now returns SSE stream
- Updated card updater queries to properly filter cards by ID from lists
- All LLM mock fixtures now support both `chat_completion` and `chat_completion_stream`

#### Changed
- Removed vector embeddings, switched to keyword-only entity detection (v3.1 design)
- Improved error handling with detailed exception details for sqlite-vec
- Updated CORS configuration for Vercel production deployment

#### Fixed
- Chat 500 error caused by profile key mismatch
- CORS settings to allow requests from gameapy-web.vercel.app
- Railway deployment issues (Procfile path, runtime.txt, __init__.py imports)

---

### Frontend (gameapy-web)

#### Added
- **Streaming Chat**: SSE (Server-Sent Events) support for real-time responses
  - `sendMessageStream()` method in ApiService for streaming chat
  - `StreamChunk` TypeScript type for parsing SSE responses
  - Real-time text rendering with smooth updates
  - Auto-scroll to bottom on each content chunk
  - Retry logic for failed streaming requests (max 3 retries)
  - Handle metadata chunks (cards_loaded, counselor_switched, new_counselor)
  - Handle error chunks with user notification
- Easter egg feature: "Summon Deirdre" counselor switching in Marina's chat
- Quick AI card creation button in CardInventoryModal
- Full-screen inventory mode
- GuideScreen for organic card creation flow
- Counselor-specific color theming across all modals and UI elements
- Comprehensive error logging for API failures
- Modern iOS-style UI design for CardInventoryModal

#### Changed
- ChatScreen now uses streaming chat instead of JSON responses
- CardInventoryModal refreshes selected card after pin/auto-update toggle
- Removed `sendMessage()` method (replaced by `sendMessageStream()`)

#### Changed
- Redesigned CardInventoryModal with modern iOS-style aesthetics
- Updated counselor grid to use grid-rows-2 for proper 2x2 layout
- Integrated organic guide flow with seamless navigation between chat and card creation

#### Fixed
- Tailwind CSS utility class generation (added @tailwindcss/vite plugin)
- Counselor color grid display issue
- Layers button now opens CardInventoryModal correctly
- Chat endpoint URL configuration
- Counselor schema mismatch (profile vs profile_json)
- TypeScript types for ClientProfileCreate matching backend schema
- 422 error on client creation (missing required fields)
- Duplicate API base URL in endpoint construction
- API base URL for Vercel production deployment

---

## [3.4.0] - 2026-02-09

### Backend (gameapy-backend)

#### Added
- **Complete Backend Implementation** (Phases 1-7):
  - Database schema with self_cards, character_cards, world_events, entity_mentions tables
  - Card Generator service (plain text → structured JSON)
  - Organic Guide System (conversational onboarding with card creation)
  - Pin System ("Keep this in mind" cards always load in context)
  - Keyword-Only Entity Detection (fast, simple matching)
  - Auto-Update System (invisible updates with per-card toggles)
  - Context Assembly (self + pinned + current + recent cards)
  - Pytest Testing Infrastructure (file-based test DB, LLM mocking, test isolation)
  - **89/89 tests passing** (100% pass rate, 68% code coverage)

#### Technical
- Deterministic test execution (no state pollution, per-request LLM clients)
- API Response pattern with success/message/data structure
- Database context manager pattern for safe connection handling
- OpenRouter API integration with multiple LLM models (Claude, GPT)

---

### Frontend (gameapy-web)

#### Added
- **Complete Web MVP Implementation** (Phases 0-6):
  - Phase 0: React + Vite + TypeScript project initialized
  - Phase 1: Counselor selection screen with 4 colored placeholder cards
  - Phase 2: Chat interface with real backend integration
  - Phase 3: Card inventory modal with tabs, search, pin/auto-update
  - Phase 4: Card detail view and inline editing with validation
  - Phase 5: Polish & mobile optimization with animations and touch targets
  - Phase 6: Testing, bug fixes, and Vercel deployment

#### Features
- GBA color palette (warm off-white, bright lime, forest green, cream, yellow, dark brown)
- VT323 retro font from Google Fonts
- Global state management via React Context (AppContext.tsx)
- Card editing: view details, edit core fields, save changes, validation, unsaved changes confirmation
- Smooth fade-in animations (0.3s) for all screens
- Button hover/active animations with visual feedback
- All touch targets meet WCAG AA (44x44px minimum)
- Responsive layouts for mobile/tablet/desktop
- Retry buttons for all failed API requests
- Mobile keyboard overlap prevention (flex-shrink-0 on headers/footers)

#### Deployment
- Vercel configuration with Railway backend integration
- Production URL: https://gameapy-web.vercel.app
- Environment variable: VITE_API_BASE_URL

---

## [3.3.0] - 2026-02-08

### Backend (gameapy-backend)

#### Added
- Initial commit with complete backend implementation (Phases 1-7)
- Database schema with is_pinned columns for cards
- Card API endpoints (/api/v1/cards/*)
- Guide API endpoints (/api/v1/guide/*)
- Chat API endpoints (/api/v1/chat/*)
- Session Analyzer endpoint (/api/v1/sessions/{id}/analyze)

#### Technical
- SQLite database with keyword-only search (no vector embeddings)
- LLM services: card_generator, guide_system, card_updater
- Persona configuration in data/personas/*.json
- Core truths in app/config/core_truths.py
- Pytest test suite with coverage reporting

---

### Frontend (gameapy-web)

#### Added
- Initial commit with Web MVP complete (Phases 0-5)
- React 19.2.0+, Vite 7.2.4+, TypeScript 5.9.3+, Tailwind CSS 4.1.18+
- Counselor selection screen
- Chat interface with iMessage-style bubbles
- Card inventory modal with self/character/world tabs
- Card detail view with inline editing
- API client for backend communication

---

## [3.1.0] - 2026-02-08

### Backend (gameapy-backend)

#### Breaking Changes
- **Removed vector embeddings**: Switched to keyword-only entity detection
- **Simplified architecture**: No longer using sqlite-vec for similarity search
- **Faster, simpler**: Entity detection now uses direct string matching

#### Rationale
- v3.1 design simplifies the system by removing vector embeddings complexity
- Keyword-based search is faster and more predictable
- Better suited for the current use case of simple entity detection

---

## [3.0.0] - 2026-02-07

### Backend (gameapy-backend)

#### Breaking Changes
- **Removed canon law system**: No longer canon_refactored or canon_law tables
- **Removed 3-phase onboarding**: Simplified to organic guide conversation
- **Card structure simplified**: NeuralRP-style world_events with key_array

#### Rationale
- Pivoted from canon law system to simpler, more flexible approach
- Organic guide conversation feels more natural and less forced
- Simplified card structure reduces complexity and improves maintainability

#### Documentation
- See `PIVOT_IMPLEMENTATION_COMPLETE.md` for full details on the v3.0 → v3.1 pivot

---

## [2.0.0] - 2026-02-06

### Backend (gameapy-backend)

#### Added
- Pytest testing infrastructure with test isolation
- LLM mocking for deterministic tests
- Per-request LLM clients (no global httpx.AsyncClient caching)
- Test categories: unit, integration, e2e, slow, llm
- Fixtures for sample data (client, counselor, cards, sessions)
- Coverage reporting with pytest-cov

#### Achieved
- 89/89 tests passing (100% pass rate)
- 68% code coverage
- File-based test DB (gameapy_test.db) with per-test truncation

---

## [1.0.0] - 2026-02-01

### Backend (gameapy-backend)

#### Initial Release
- First version of Gameapy backend
- Basic card management system
- Chat functionality with counselors
- Session analysis
- Deployment to Railway

---

## Project Structure

Gameapy is split into two separate GitHub repositories:

| Repo | URL | Purpose |
|------|-----|---------|
| **Backend** | https://github.com/NeuralRP/gameapy-backend | FastAPI server, database, LLM services, tests |
| **Web** | https://github.com/NeuralRP/gameapy-web | React frontend (Vite + TypeScript + Tailwind) |

---

## Version History Summary

| Version | Date | Status |
|---------|------|--------|
| 3.4.0 | 2026-02-10 | Current - Easter egg features, UI improvements, bug fixes |
| 3.3.0 | 2026-02-09 | Web MVP complete, deployed to Vercel |
| 3.1.0 | 2026-02-08 | Keyword-only search (no vector embeddings) |
| 3.0.0 | 2026-02-07 | Pivot: Removed canon law, simplified to organic guide |
| 2.0.0 | 2026-02-06 | Test infrastructure complete (100% pass rate) |
| 1.0.0 | 2026-02-01 | Initial backend release |

---

## Current Production Status

- **Backend**: https://gameapy-backend-production.up.railway.app (✅ Live)
- **Frontend**: https://gameapy-web.vercel.app (✅ Live)
- **All tests passing**: 89/89 (100%)
- **Code coverage**: 68%

---

## Roadmap

| Phase | Status | Key Deliverables |
|-------|--------|------------------|
| Backend 1-7 | ✅ Complete | All backend features + test infrastructure |
| Web 0-6 | ✅ Complete | Web MVP complete + deployed to Vercel |
| 8 | ⏳ Planned | Flutter UI Development |
| 9 | ⏳ Planned | Garden Minigame (optional) |

---

## Contributors

- See GitHub commit history for full contributor list
- Backend: https://github.com/NeuralRP/gameapy-backend/commits
- Web: https://github.com/NeuralRP/gameapy-web/commits

---

## Links

- **AGENTS.md**: LLM-optimized project documentation
- **TECHNICAL.md**: Detailed technical breakdown
- **WEB_MVP_DEVELOPMENT_PLAN.md**: Web MVP implementation plan
- **README.md**: Project overview for GitHub

---

**Note**: This changelog follows Keep a Changelog format. For full details on any release, see the commit history in the respective GitHub repositories.
