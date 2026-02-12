from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from app.models.schemas import (
    ClientProfile, APIResponse,
    CounselorProfile, CounselorProfileCreate,
    Session, SessionCreate, Message, MessageCreate,
    CharacterCard, CharacterCardCreate,
    GameState, FarmItem, FarmItemCreate, FarmShopResponse,
    ShopItem, HealthResponse
)
from app.db.database import db
from app.auth import get_current_user
from datetime import datetime
import json

router = APIRouter()
optional_security = HTTPBearer(auto_error=False)


# Health Check (public)
@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="0.1.0"
    )


# Client Profile Routes
@router.get("/clients/me", response_model=ClientProfile)
async def get_current_client(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user's profile."""
    client = db.get_client_profile(current_user["id"])
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# Counselor Profile Routes (public list, no auth required for browsing)
@router.post("/counselors", response_model=APIResponse)
async def create_counselor(counselor_data: CounselorProfileCreate):
    """Create a new counselor profile (admin only in future)."""
    try:
        profile_data = {
            "spec": "counselor_profile_v1",
            "spec_version": "1.0",
            "data": counselor_data.dict()
        }
        
        counselor_id = db.create_counselor_profile(profile_data)
        
        return APIResponse(
            success=True,
            message="Counselor profile created successfully",
            data={"counselor_id": counselor_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/counselors", response_model=List[CounselorProfile])
async def get_all_counselors(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security)
):
    """
    Get all active counselors (system personas + user's custom advisors).
    If authenticated, includes user's custom advisors. If not, returns system counselors only.
    """
    try:
        client_id = 0
        if credentials:
            try:
                user = await get_current_user(credentials)
                client_id = user["id"]
            except HTTPException:
                pass
        
        counselors = db.get_all_counselors_including_custom(client_id)
        return counselors
    except Exception as e:
        import logging
        logging.exception("Error retrieving counselors")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve counselors"
        )


@router.get("/counselors/{counselor_id}", response_model=CounselorProfile)
async def get_counselor(counselor_id: int):
    """Get counselor profile by ID (public)."""
    counselor = db.get_counselor_profile(counselor_id)
    if not counselor:
        raise HTTPException(status_code=404, detail="Counselor not found")
    return counselor


# Session Routes
@router.post("/sessions", response_model=APIResponse)
async def create_session(
    session_data: SessionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new counseling session."""
    try:
        client_id = current_user["id"]
        session_id = db.create_session(client_id, session_data.counselor_id)
        
        return APIResponse(
            success=True,
            message="Session created successfully",
            data={"session_id": session_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/messages", response_model=APIResponse)
async def add_message(
    session_id: int,
    message_data: MessageCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a message to a session."""
    try:
        message_id = db.add_message(
            session_id=session_id,
            role=message_data.role,
            content=message_data.content,
            speaker=message_data.speaker
        )
        
        return APIResponse(
            success=True,
            message="Message added successfully",
            data={"message_id": message_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/messages", response_model=List[Message])
async def get_session_messages(
    session_id: int,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get messages from a session."""
    try:
        return db.get_session_messages(session_id, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Character Card Routes
@router.post("/character-cards", response_model=APIResponse)
async def create_character_card(
    card_data: CharacterCardCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new character card."""
    try:
        client_id = current_user["id"]
        card_id = db.create_character_card(
            client_id=client_id,
            card_name=card_data.card_name,
            relationship_type=card_data.relationship_type,
            card_data=card_data.card_data
        )
        
        return APIResponse(
            success=True,
            message="Character card created successfully",
            data={"card_id": card_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/character-cards", response_model=List[CharacterCard])
async def get_character_cards(current_user: dict = Depends(get_current_user)):
    """Get all character cards for current user."""
    client_id = current_user["id"]
    return db.get_character_cards(client_id)


# Game State Routes
@router.get("/game-state", response_model=GameState)
async def get_game_state(current_user: dict = Depends(get_current_user)):
    """Get game state for current user."""
    client_id = current_user["id"]
    game_state = db.get_game_state(client_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="Game state not found")
    return game_state


@router.post("/game-state/award-coins", response_model=APIResponse)
async def award_coins(
    coins: int,
    reason: str = "session_completion",
    current_user: dict = Depends(get_current_user)
):
    """Award gold coins to current user."""
    try:
        client_id = current_user["id"]
        success = db.update_gold_coins(client_id, coins, reason)
        if not success:
            raise HTTPException(status_code=404, detail="Client not found")
        
        return APIResponse(
            success=True,
            message=f"Awarded {coins} gold coins",
            data={"coins_awarded": coins, "reason": reason}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Farm Routes
@router.get("/farm-items", response_model=List[FarmItem])
async def get_farm_items(current_user: dict = Depends(get_current_user)):
    """Get all farm items for current user."""
    client_id = current_user["id"]
    return db.get_farm_items(client_id)


@router.post("/farm-items", response_model=APIResponse)
async def add_farm_item(
    item_data: FarmItemCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a new farm item."""
    try:
        client_id = current_user["id"]
        item_id = db.add_farm_item(
            client_id=client_id,
            item_type=item_data.item_type,
            item_name=item_data.item_name,
            item_metadata=item_data.metadata
        )
        
        return APIResponse(
            success=True,
            message="Farm item added successfully",
            data={"item_id": item_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/farm-shop", response_model=FarmShopResponse)
async def get_farm_shop(current_user: dict = Depends(get_current_user)):
    """Get farm shop items and player gold."""
    client_id = current_user["id"]
    game_state = db.get_game_state(client_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="Client not found")
    
    available_items = [
        ShopItem(
            item_type="egg",
            item_name="Chicken Egg",
            cost=10,
            description="A fresh egg ready to hatch into a chicken"
        ),
        ShopItem(
            item_type="egg",
            item_name="Duck Egg",
            cost=10,
            description="A duck egg that will hatch into a duckling"
        ),
        ShopItem(
            item_type="hay",
            item_name="Bale of Hay",
            cost=10,
            description="Food for your animals"
        ),
        ShopItem(
            item_type="seed",
            item_name="Corn Seeds",
            cost=10,
            description="Plant these to grow corn"
        )
    ]
    
    return FarmShopResponse(
        available_items=available_items,
        player_gold=game_state.get('gold_coins', 0)
    )


# ============================================================
# Phase 3: Unified Card Management Endpoints
# ============================================================

@router.get("/cards", response_model=APIResponse)
async def get_all_cards(
    page: int = Query(1, ge=1),
    page_size: str = Query("20"),
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """
    Get all cards for current user (paginated).

    Query Params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, or "all" for all cards)

    Returns unified response with self, character, and world cards.
    """
    try:
        client_id = current_user["id"]
        is_all = page_size.lower() == "all"
        limit = None if is_all else int(page_size)
        offset = 0 if is_all else (page - 1) * int(page_size)

        self_card = db.get_self_card(client_id)
        character_cards = db.get_character_cards(client_id)
        world_events = db.get_world_events(client_id)

        all_cards = []

        if self_card:
            raw_payload = json.loads(self_card['card_json']) if isinstance(self_card['card_json'], str) else self_card['card_json']
            normalized_payload = db.normalize_self_card_payload(raw_payload)
            all_cards.append({
                'id': self_card['id'],
                'card_type': 'self',
                'payload': normalized_payload,
                'auto_update_enabled': self_card['auto_update_enabled'],
                'is_pinned': self_card['is_pinned'],
                'created_at': self_card['created_at'],
                'updated_at': self_card['last_updated']
            })

        for card in character_cards:
            payload = {**card['card'], 'name': card['card_name']}
            if card.get('relationship_label'):
                payload['relationship_label'] = card['relationship_label']
            all_cards.append({
                'id': card['id'],
                'card_type': 'character',
                'payload': payload,
                'auto_update_enabled': card['auto_update_enabled'],
                'is_pinned': card['is_pinned'],
                'created_at': card['created_at'],
                'updated_at': card['last_updated']
            })

        for event in world_events:
            all_cards.append({
                'id': event['id'],
                'card_type': 'world',
                'payload': {
                    'title': event['title'],
                    'description': event['description'],
                    'event_type': event['event_type'],
                    'key_array': json.loads(event['key_array']),
                    'is_canon_law': bool(event['is_canon_law']),
                    'resolved': bool(event['resolved'])
                },
                'auto_update_enabled': event['auto_update_enabled'],
                'is_pinned': event['is_pinned'],
                'created_at': event['created_at'],
                'updated_at': event['updated_at']
            })

        all_cards.sort(key=lambda x: x['updated_at'], reverse=True)

        total_items = len(all_cards)
        if not is_all:
            paginated_items = all_cards[offset:offset + int(page_size)]
            total_pages = (total_items + int(page_size) - 1) // int(page_size)
        else:
            paginated_items = all_cards
            total_pages = 1

        return APIResponse(
            success=True,
            message=f"Retrieved {len(paginated_items)} cards",
            data={
                'items': paginated_items,
                'pagination': {
                    'page': page,
                    'page_size': total_items if is_all else int(page_size),
                    'total_pages': total_pages,
                    'total_items': total_items
                }
            }
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Failed to retrieve cards: {str(e)}"
        )
