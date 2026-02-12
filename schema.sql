-- PostgreSQL Schema for Gameapy
-- Core Entity Tables

CREATE TABLE IF NOT EXISTS client_profiles (
    id SERIAL PRIMARY KEY,
    entity_id TEXT UNIQUE NOT NULL,  -- Format: "client_{uuid}"
    username TEXT UNIQUE,  -- New: for authentication
    password_hash TEXT,    -- New: for authentication
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    profile_json JSONB NOT NULL,  -- JSON: personality, traits, goals, timeline
    tags JSONB,  -- JSON array: ["anxiety", "depression", "relationship"]
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMPTZ,
    recovery_code_hash TEXT,
    recovery_code_expires_at TIMESTAMPTZ,
    last_recovery_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS counselor_profiles (
    id SERIAL PRIMARY KEY,
    entity_id TEXT UNIQUE NOT NULL,  -- Format: "counselor_{uuid}"
    name TEXT NOT NULL,
    specialization TEXT NOT NULL,  -- "Baseball Coach", "Wise Old Man", "Mermaid", "Zeus"
    therapeutic_style TEXT NOT NULL,
    credentials TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    profile_json JSONB NOT NULL,  -- JSON: clinical approach, examples, protocols
    tags JSONB,  -- JSON array: ["sports", "wisdom", "mythology", "ocean"]
    is_active BOOLEAN DEFAULT TRUE,
    is_hidden BOOLEAN DEFAULT FALSE,  -- Easter egg counselors (e.g., Deirdre)
    deleted_at TIMESTAMPTZ,
    client_id INTEGER REFERENCES client_profiles(id),
    is_custom BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    last_image_regenerated TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
    counselor_id INTEGER NOT NULL REFERENCES counselor_profiles(id),
    session_number INTEGER NOT NULL,  -- Increment per client-counselor pair
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    metadata JSONB  -- JSON: mood_start, mood_end, topics, crisis_flags
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,  -- "user", "assistant", "system"
    content TEXT NOT NULL,
    speaker TEXT,  -- "client", "counselor"
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB  -- JSON: additional context
);

-- Game Elements Tables
CREATE TABLE IF NOT EXISTS game_state (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL UNIQUE REFERENCES client_profiles(id),
    gold_coins INTEGER DEFAULT 0,
    farm_level INTEGER DEFAULT 1,
    last_coin_award TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS farm_items (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
    item_type TEXT NOT NULL,  -- "egg", "chicken", "duck", "seed", "hay"
    item_name TEXT NOT NULL,
    item_metadata JSONB,  -- JSON: growth_stage, health, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Character Cards Tables (for people in user's life)
CREATE TABLE IF NOT EXISTS character_cards (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
    card_name TEXT NOT NULL,  -- "Mom", "Best Friend John"
    relationship_type TEXT NOT NULL,  -- "family", "friend", "coworker"
    relationship_label TEXT,  -- Custom label for specific matching (e.g., "Sister", "Mother")
    card_json JSONB NOT NULL,  -- JSON: personality, traits, conversation summary
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,  -- Always load in context
    entity_id TEXT,  -- Unique identifier for entity tracking
    mention_count INTEGER DEFAULT 0,  -- Number of times mentioned
    last_mentioned TIMESTAMPTZ,  -- Last time this card was mentioned
    first_mentioned TIMESTAMPTZ,  -- First time this card was mentioned
    vector_embedding BYTEA,  -- Reserved for future vector search (migration 001)
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS card_updates (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES character_cards(id),
    session_id INTEGER REFERENCES sessions(id),
    update_type TEXT NOT NULL,  -- "auto_generated", "user_edited", "session_insight"
    old_values JSONB,  -- JSON of changed fields
    new_values JSONB NOT NULL,  -- JSON of new values
    user_approved BOOLEAN DEFAULT FALSE,  -- For auto-generated updates
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Self Cards Table (Phase 1)
CREATE TABLE IF NOT EXISTS self_cards (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL UNIQUE REFERENCES client_profiles(id),
    card_json JSONB NOT NULL,
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,  -- Always load in context
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- World Events Table (Phase 1 - Simplified NeuralRP-style)
CREATE TABLE IF NOT EXISTS world_events (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
    entity_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    key_array JSONB NOT NULL,
    description TEXT NOT NULL,
    event_type TEXT NOT NULL,
    is_canon_law BOOLEAN DEFAULT FALSE,
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    is_pinned BOOLEAN DEFAULT FALSE,  -- Always load in context
    resolved BOOLEAN DEFAULT FALSE,
    vector_embedding BYTEA,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Entity Mentions Table (Phase 1 - Semantic frequency tracking)
CREATE TABLE IF NOT EXISTS entity_mentions (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    entity_type TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    mention_context TEXT NOT NULL,
    vector_embedding BYTEA,
    mentioned_at TIMESTAMPTZ DEFAULT NOW()
);

-- Progress Tracking Tables
CREATE TABLE IF NOT EXISTS progress_tracking (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES client_profiles(id),
    counselor_id INTEGER NOT NULL REFERENCES counselor_profiles(id),
    dimension TEXT NOT NULL,  -- "engagement", "mood", "insight", "functioning"
    score INTEGER NOT NULL,  -- 0-100
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,
    UNIQUE(client_id, counselor_id, dimension)
);

-- Insight and Feedback Tables
CREATE TABLE IF NOT EXISTS session_insights (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    insight_json JSONB NOT NULL,  -- JSON: extracted insights
    status TEXT NOT NULL,  -- "pending", "approved", "rejected"
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);

-- Audit and System Tables
CREATE TABLE IF NOT EXISTS change_log (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,  -- "client_profile", "character_card", "game_state"
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- "created", "updated", "deleted"
    old_value JSONB,  -- JSON snapshot before change
    new_value JSONB,  -- JSON snapshot after change
    changed_by TEXT,  -- "user", "system", "session_{id}"
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB  -- JSON: additional context
);

-- Performance monitoring
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    operation_type TEXT NOT NULL,  -- "llm_call", "insight_extraction", "protocol_search"
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL,  -- "success", "error"
    error_message TEXT,
    metadata JSONB,  -- JSON: tokens used, model, etc.
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_sessions_client_counselor ON sessions(client_id, counselor_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp ON messages(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_progress_tracking_client_counselor ON progress_tracking(client_id, counselor_id);
CREATE INDEX IF NOT EXISTS idx_change_log_entity ON change_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_session_insights_status ON session_insights(status);
CREATE INDEX IF NOT EXISTS idx_character_cards_client ON character_cards(client_id);
CREATE INDEX IF NOT EXISTS idx_character_cards_entity ON character_cards(entity_id);
CREATE INDEX IF NOT EXISTS idx_character_cards_auto_update ON character_cards(auto_update_enabled);
CREATE INDEX IF NOT EXISTS idx_character_cards_mentions ON character_cards(mention_count DESC);
CREATE INDEX IF NOT EXISTS idx_game_state_client ON game_state(client_id);
CREATE INDEX IF NOT EXISTS idx_farm_items_client ON farm_items(client_id);

-- Indexes for self_cards
CREATE INDEX IF NOT EXISTS idx_self_cards_client ON self_cards(client_id);
CREATE INDEX IF NOT EXISTS idx_self_cards_auto_update ON self_cards(auto_update_enabled);
CREATE INDEX IF NOT EXISTS idx_self_cards_pinned ON self_cards(client_id, is_pinned);

-- Indexes for world_events
CREATE INDEX IF NOT EXISTS idx_world_events_client ON world_events(client_id);
CREATE INDEX IF NOT EXISTS idx_world_events_canon ON world_events(is_canon_law);
CREATE INDEX IF NOT EXISTS idx_world_events_entity ON world_events(entity_id);
CREATE INDEX IF NOT EXISTS idx_world_events_auto_update ON world_events(auto_update_enabled);
CREATE INDEX IF NOT EXISTS idx_world_events_type ON world_events(event_type);
CREATE INDEX IF NOT EXISTS idx_world_events_pinned ON world_events(client_id, is_pinned);

-- Indexes for entity_mentions
CREATE INDEX IF NOT EXISTS idx_entity_mentions_client ON entity_mentions(client_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_session ON entity_mentions(session_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_type ON entity_mentions(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_ref ON entity_mentions(entity_ref);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_time ON entity_mentions(mentioned_at DESC);

-- Additional index for change_log (Phase 1)
CREATE INDEX IF NOT EXISTS idx_change_log_entity_time ON change_log(entity_type, entity_id, changed_at DESC);

-- Pinned card indexes (Phase 4 - Migration 004)
CREATE INDEX IF NOT EXISTS idx_character_cards_pinned ON character_cards(client_id, is_pinned);

-- Indexes for counselor_profiles (Migration 007/008)
CREATE INDEX IF NOT EXISTS idx_counselor_profiles_client_custom ON counselor_profiles(client_id, is_custom);

-- Index for client_profiles username (authentication)
CREATE INDEX IF NOT EXISTS idx_client_profiles_username ON client_profiles(username) WHERE username IS NOT NULL;

-- ============================================================
-- LEGACY COLUMNS (Reserved for future use)
-- ============================================================
-- These columns exist but are no longer used by the application:
-- - character_cards.vector_embedding
-- - world_events.vector_embedding
-- - world_events.is_canon_law
-- - entity_mentions.vector_embedding
--
-- They are preserved for backward compatibility and potential future use.
-- No code paths reference these columns as of pivot v3.1.

-- ============================================================
-- MIGRATION 007/008: Custom Advisors Support (Applied 2026-02-12)
-- ============================================================
-- These columns were added via migration 007/008 and are now in the base schema:
-- - client_id: References client_profiles(id), NULL for system personas
-- - is_custom: TRUE for user-created advisors, FALSE for system personas
-- - image_url: Future use for generated avatar images
-- - last_image_regenerated: Future use for daily image regeneration cooldown
