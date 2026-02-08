# Database Schema for Gameapy
# Core Entity Tables

CREATE TABLE IF NOT EXISTS client_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT UNIQUE NOT NULL,  -- Format: "client_{uuid}"
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    profile_json TEXT NOT NULL,  -- JSON: personality, traits, goals, timeline
    tags TEXT,  -- JSON array: ["anxiety", "depression", "relationship"]
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS counselor_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT UNIQUE NOT NULL,  -- Format: "counselor_{uuid}"
    name TEXT NOT NULL,
    specialization TEXT NOT NULL,  -- "Baseball Coach", "Wise Old Man", "Mermaid", "Zeus"
    therapeutic_style TEXT NOT NULL,
    credentials TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    profile_json TEXT NOT NULL,  -- JSON: clinical approach, examples, protocols
    tags TEXT,  -- JSON array: ["sports", "wisdom", "mythology", "ocean"]
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    counselor_id INTEGER NOT NULL,
    session_number INTEGER NOT NULL,  -- Increment per client-counselor pair
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    metadata TEXT,  -- JSON: mood_start, mood_end, topics, crisis_flags
    FOREIGN KEY (client_id) REFERENCES client_profiles(id),
    FOREIGN KEY (counselor_id) REFERENCES counselor_profiles(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,  -- "user", "assistant", "system"
    content TEXT NOT NULL,
    speaker TEXT,  -- "client", "counselor"
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,  -- JSON: additional context
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Game Elements Tables
CREATE TABLE IF NOT EXISTS game_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    gold_coins INTEGER DEFAULT 0,
    farm_level INTEGER DEFAULT 1,
    last_coin_award TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES client_profiles(id),
    UNIQUE(client_id)
);

CREATE TABLE IF NOT EXISTS farm_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,  -- "egg", "chicken", "duck", "seed", "hay"
    item_name TEXT NOT NULL,
    item_metadata TEXT,  -- JSON: growth_stage, health, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES client_profiles(id)
);

-- Character Cards Tables (for people in user's life)
CREATE TABLE IF NOT EXISTS character_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    card_name TEXT NOT NULL,  -- "Mom", "Best Friend John"
    relationship_type TEXT NOT NULL,  -- "family", "friend", "coworker"
    card_json TEXT NOT NULL,  -- JSON: personality, traits, conversation summary
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES client_profiles(id)
);

CREATE TABLE IF NOT EXISTS card_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    session_id INTEGER,
    update_type TEXT NOT NULL,  -- "auto_generated", "user_edited", "session_insight"
    old_values TEXT,  -- JSON of changed fields
    new_values TEXT NOT NULL,  -- JSON of new values
    user_approved BOOLEAN DEFAULT FALSE,  -- For auto-generated updates
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (card_id) REFERENCES character_cards(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Progress Tracking Tables
CREATE TABLE IF NOT EXISTS progress_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    counselor_id INTEGER NOT NULL,
    dimension TEXT NOT NULL,  -- "engagement", "mood", "insight", "functioning"
    score INTEGER NOT NULL,  -- 0-100
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (client_id) REFERENCES client_profiles(id),
    FOREIGN KEY (counselor_id) REFERENCES counselor_profiles(id),
    UNIQUE(client_id, counselor_id, dimension)
);

-- Insight and Feedback Tables
CREATE TABLE IF NOT EXISTS session_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    insight_json TEXT NOT NULL,  -- JSON: extracted insights
    status TEXT NOT NULL,  -- "pending", "approved", "rejected"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Audit and System Tables
CREATE TABLE IF NOT EXISTS change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- "client_profile", "character_card", "game_state"
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- "created", "updated", "deleted"
    old_value TEXT,  -- JSON snapshot before change
    new_value TEXT,  -- JSON snapshot after change
    changed_by TEXT,  -- "user", "system", "session_{id}"
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT  -- JSON: additional context
);

-- Performance monitoring
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,  -- "llm_call", "insight_extraction", "protocol_search"
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL,  -- "success", "error"
    error_message TEXT,
    metadata TEXT,  -- JSON: tokens used, model, etc.
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_sessions_client_counselor ON sessions(client_id, counselor_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp ON messages(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_progress_tracking_client_counselor ON progress_tracking(client_id, counselor_id);
CREATE INDEX IF NOT EXISTS idx_change_log_entity ON change_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_session_insights_status ON session_insights(status);
CREATE INDEX IF NOT EXISTS idx_character_cards_client ON character_cards(client_id);
CREATE INDEX IF NOT EXISTS idx_game_state_client ON game_state(client_id);
CREATE INDEX IF NOT EXISTS idx_farm_items_client ON farm_items(client_id);

-- ============================================================
-- PHASE 1: Character Card System Extensions
-- ============================================================

-- Extend character_cards table with new columns
-- Note: auto_update_enabled may already exist (line 85), check first in migration script
-- ALTER TABLE character_cards ADD COLUMN entity_id TEXT;  -- UNIQUE added via index
-- ALTER TABLE character_cards ADD COLUMN mention_count INTEGER DEFAULT 0;
-- ALTER TABLE character_cards ADD COLUMN last_mentioned TIMESTAMP;
-- ALTER TABLE character_cards ADD COLUMN first_mentioned TIMESTAMP;
-- ALTER TABLE character_cards ADD COLUMN vector_embedding BLOB;
-- auto_update_enabled: Check in migration (may already exist)

-- Indexes for character_cards (Phase 1)
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_character_cards_entity ON character_cards(entity_id);
-- CREATE INDEX IF NOT EXISTS idx_character_cards_auto_update ON character_cards(auto_update_enabled);
-- CREATE INDEX IF NOT EXISTS idx_character_cards_mentions ON character_cards(mention_count DESC);

-- Self Cards Table (Phase 1)
CREATE TABLE IF NOT EXISTS self_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL UNIQUE,
    card_json TEXT NOT NULL,
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES client_profiles(id)
);

-- Indexes for self_cards
CREATE INDEX IF NOT EXISTS idx_self_cards_client ON self_cards(client_id);
CREATE INDEX IF NOT EXISTS idx_self_cards_auto_update ON self_cards(auto_update_enabled);

-- World Events Table (Phase 1 - Simplified NeuralRP-style)
CREATE TABLE IF NOT EXISTS world_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    entity_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    key_array TEXT NOT NULL,
    description TEXT NOT NULL,
    event_type TEXT NOT NULL,
    is_canon_law BOOLEAN DEFAULT FALSE,
    auto_update_enabled BOOLEAN DEFAULT TRUE,
    resolved BOOLEAN DEFAULT FALSE,
    vector_embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES client_profiles(id)
);

-- Indexes for world_events
CREATE INDEX IF NOT EXISTS idx_world_events_client ON world_events(client_id);
CREATE INDEX IF NOT EXISTS idx_world_events_canon ON world_events(is_canon_law);
CREATE INDEX IF NOT EXISTS idx_world_events_entity ON world_events(entity_id);
CREATE INDEX IF NOT EXISTS idx_world_events_auto_update ON world_events(auto_update_enabled);
CREATE INDEX IF NOT EXISTS idx_world_events_type ON world_events(event_type);

-- Entity Mentions Table (Phase 1 - Semantic frequency tracking)
CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    mention_context TEXT NOT NULL,
    vector_embedding BLOB,
    mentioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES client_profiles(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Indexes for entity_mentions
CREATE INDEX IF NOT EXISTS idx_entity_mentions_client ON entity_mentions(client_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_session ON entity_mentions(session_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_type ON entity_mentions(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_ref ON entity_mentions(entity_ref);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_time ON entity_mentions(mentioned_at DESC);

-- Additional index for change_log (Phase 1)
CREATE INDEX IF NOT EXISTS idx_change_log_entity_time ON change_log(entity_type, entity_id, changed_at DESC);

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