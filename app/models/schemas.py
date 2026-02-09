from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class RoleEnum(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class RelationshipType(str, Enum):
    FAMILY = "family"
    FRIEND = "friend"
    COWORKER = "coworker"
    ROMANTIC = "romantic"
    OTHER = "other"


# Base Models
class BaseModelResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


# Client Profile Models
class PresentingIssue(BaseModel):
    issue: str
    severity: str  # "mild", "moderate", "severe"
    duration: str


class LifeEvent(BaseModel):
    title: str
    date: str
    impact: str
    resolved: bool
    tags: List[str]


class ClientPreferences(BaseModel):
    communication_style: str = "standard"
    pace: str = "moderate"
    focus_areas: List[str] = []


class ClientProfileData(BaseModel):
    spec: str = "client_profile_v1"
    spec_version: str = "1.0"
    data: Dict[str, Any]


class ClientProfileCreate(BaseModel):
    name: str
    personality: str
    traits: List[str]
    presenting_issues: List[PresentingIssue]
    goals: List[str]
    life_events: List[LifeEvent]
    preferences: ClientPreferences = ClientPreferences()


class ClientProfile(BaseModelResponse):
    entity_id: str
    name: str
    profile: ClientProfileData
    tags: List[str]


# Counselor Profile Models
class CounselorProfileData(BaseModel):
    spec: str = "counselor_profile_v1"
    spec_version: str = "1.0"
    data: Dict[str, Any]


class CounselorProfileCreate(BaseModel):
    name: str
    specialization: str
    therapeutic_style: str
    credentials: Optional[str] = None
    session_template: Optional[str] = None
    extensions: Optional[Dict[str, Any]] = None


class CounselorProfile(BaseModelResponse):
    entity_id: str
    name: str
    specialization: str
    therapeutic_style: str
    credentials: Optional[str]
    profile: CounselorProfileData
    tags: List[str]


# Session Models
class MessageCreate(BaseModel):
    role: RoleEnum
    content: str
    speaker: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: int
    message_data: MessageCreate

class Message(BaseModelResponse):
    session_id: int
    role: RoleEnum
    content: str
    speaker: Optional[str]


class SessionCreate(BaseModel):
    client_id: int
    counselor_id: int


class Session(BaseModelResponse):
    client_id: int
    counselor_id: int
    session_number: int
    started_at: datetime
    ended_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]


class SessionWithMessages(Session):
    messages: List[Message]


# Character Card Models
class CharacterCardCreate(BaseModel):
    card_name: str
    relationship_type: RelationshipType
    card_data: Dict[str, Any]


class CharacterCard(BaseModelResponse):
    client_id: int
    card_name: str
    relationship_type: RelationshipType
    card: Dict[str, Any]
    auto_update_enabled: bool = True
    last_updated: datetime

    # Phase 1: New fields
    entity_id: Optional[str] = None
    mention_count: int = 0
    last_mentioned: Optional[datetime] = None
    first_mentioned: Optional[datetime] = None


# Game State Models
class GameState(BaseModelResponse):
    client_id: int
    gold_coins: int
    farm_level: int
    last_coin_award: Optional[datetime]


class FarmItem(BaseModelResponse):
    client_id: int
    item_type: str
    item_name: str
    metadata: Dict[str, Any] = {}


class FarmItemCreate(BaseModel):
    item_type: str
    item_name: str
    metadata: Optional[Dict[str, Any]] = None


# Farm Shop Items
class ShopItem(BaseModel):
    item_type: str
    item_name: str
    cost: int
    description: str


class FarmShopResponse(BaseModel):
    available_items: List[ShopItem]
    player_gold: int


# Session Insights
class SessionInsightCreate(BaseModel):
    session_id: int
    insight_json: Dict[str, Any]


class SessionInsight(BaseModelResponse):
    session_id: int
    insight_json: Dict[str, Any]
    status: str  # "pending", "approved", "rejected"
    approved_at: Optional[datetime]


# Progress Tracking
class ProgressTracking(BaseModelResponse):
    client_id: int
    counselor_id: int
    dimension: str
    score: int
    last_updated: datetime
    notes: Optional[str]


# Change Log
class ChangeLog(BaseModelResponse):
    entity_type: str
    entity_id: int
    action: str
    old_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    changed_by: str
    metadata: Optional[Dict[str, Any]]


# Phase 1: Self Card Models
class SelfCardCreate(BaseModel):
    card_json: str
    auto_update_enabled: bool = True
    is_pinned: bool = False  # NEW


class SelfCard(BaseModelResponse):
    client_id: int
    card_json: str
    auto_update_enabled: bool = True
    is_pinned: bool = False  # NEW
    last_updated: datetime


# Phase 1: World Event Models
class WorldEventCreate(BaseModel):
    entity_id: str
    title: str
    key_array: str  # JSON string
    description: str
    event_type: str
    is_canon_law: bool = False  # Legacy, unused
    auto_update_enabled: bool = True
    resolved: bool = False
    is_pinned: bool = False  # NEW


class WorldEvent(BaseModelResponse):
    client_id: int
    entity_id: str
    title: str
    key_array: str
    description: str
    event_type: str
    is_canon_law: bool  # Legacy, unused
    auto_update_enabled: bool
    resolved: bool
    is_pinned: bool = False  # NEW


# Phase 1: Entity Mention Models
class EntityMentionCreate(BaseModel):
    session_id: int
    entity_type: str
    entity_ref: str
    mention_context: str


class EntityMention(BaseModelResponse):
    client_id: int
    session_id: int
    entity_type: str
    entity_ref: str
    mention_context: str
    mentioned_at: datetime


# API Response Models
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# Health Check
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Phase 2: Card Generator Models
class CardGenerateRequest(BaseModel):
    card_type: str
    plain_text: str
    context: Optional[str] = None
    name: Optional[str] = None


class CardGenerateResponse(BaseModel):
    card_type: str
    generated_card: Dict[str, Any]
    preview: bool = True
    fallback: bool = False


class CardSaveRequest(BaseModel):
    client_id: int
    card_type: str
    card_data: Dict[str, Any]


class CardSaveResponse(BaseModel):
    card_id: int


# Phase 2: Guide System Models
class OnboardingStartRequest(BaseModel):
    client_id: int


class OnboardingStartResponse(BaseModel):
    phase: str
    guide_message: str
    session_id: int
    client_id: int


class OnboardingInputRequest(BaseModel):
    session_id: int
    phase: str
    user_input: str


class OnboardingInputResponse(BaseModel):
    phase: str
    guide_message: str
    conversation_complete: bool
    cards_generated: List[Dict[str, Any]]


# ============================================================
# Phase 3: Unified Card Management Models
# ============================================================

class PaginationInfo(BaseModel):
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    total_items: int = 0


class UnifiedCard(BaseModel):
    """Unified card model for any card type."""
    id: int
    card_type: str
    payload: Dict[str, Any]
    auto_update_enabled: bool = True
    is_pinned: bool = False  # NEW
    created_at: datetime
    updated_at: datetime


class CardListResponse(BaseModel):
    """Paginated response for unified card list."""
    items: List[UnifiedCard]
    pagination: PaginationInfo


class CardUpdateRequest(BaseModel):
    """Partial update request for any card type."""
    card_type: str
    card_json: Optional[str] = None
    card_name: Optional[str] = None
    relationship_type: Optional[str] = None
    card_data: Optional[Dict[str, Any]] = None
    title: Optional[str] = None
    key_array: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    is_canon_law: Optional[bool] = None  # Legacy, ignored
    resolved: Optional[bool] = None
    auto_update_enabled: Optional[bool] = None
    is_pinned: Optional[bool] = None  # NEW


class CardSearchRequest(BaseModel):
    """Search parameters for cross-type card search."""
    q: str
    types: Optional[str] = None
    page: int = 1
    page_size: int = 20


class SearchResult(BaseModel):
    """Individual search result with relevance."""
    id: int
    card_type: str
    payload: Dict[str, Any]
    relevance: float = 1.0


class CardSearchResponse(BaseModel):
    """Paginated search response."""
    items: List[SearchResult]
    pagination: PaginationInfo


# ============================================================
# Phase 4: Session Analysis Models
# ============================================================

class SessionAnalysisResponse(BaseModel):
    """Response from session analysis endpoint."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class CardUpdateResult(BaseModel):
    """Result from CardUpdater service."""
    cards_updated: int
    cards_skipped: int
    updates_applied: List[Dict[str, Any]]


class CanonChangeResult(BaseModel):
    """Result from CanonRefactor service."""
    canon_events_updated: int
    events_marked_canon: List[int]
    events_removed_canon: List[int]
    unchanged: int