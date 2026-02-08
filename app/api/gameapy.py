from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.models.schemas import (
    ClientProfile, ClientProfileCreate, APIResponse,
    CounselorProfile, CounselorProfileCreate,
    Session, SessionCreate, Message, MessageCreate, SessionWithMessages,
    CharacterCard, CharacterCardCreate,
    GameState, FarmItem, FarmItemCreate, FarmShopResponse,
    ShopItem, HealthResponse
)
from app.db.database import db
from datetime import datetime
import json

router = APIRouter()


# Health Check
@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="0.1.0"
    )


# Client Profile Routes
@router.post("/clients", response_model=APIResponse)
async def create_client(client_data: ClientProfileCreate):
    """Create a new client profile."""
    try:
        profile_data = {
            "spec": "client_profile_v1",
            "spec_version": "1.0",
            "data": client_data.dict()
        }
        
        client_id = db.create_client_profile(profile_data)
        
        return APIResponse(
            success=True,
            message="Client profile created successfully",
            data={"client_id": client_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/clients/{client_id}", response_model=ClientProfile)
async def get_client(client_id: int):
    """Get client profile by ID."""
    client = db.get_client_profile(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# Counselor Profile Routes
@router.post("/counselors", response_model=APIResponse)
async def create_counselor(counselor_data: CounselorProfileCreate):
    """Create a new counselor profile."""
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
async def get_all_counselors():
    """Get all active counselor profiles."""
    return db.get_all_counselors()


@router.get("/counselors/{counselor_id}", response_model=CounselorProfile)
async def get_counselor(counselor_id: int):
    """Get counselor profile by ID."""
    counselor = db.get_counselor_profile(counselor_id)
    if not counselor:
        raise HTTPException(status_code=404, detail="Counselor not found")
    return counselor


# Session Routes
@router.post("/sessions", response_model=APIResponse)
async def create_session(session_data: SessionCreate):
    """Create a new counseling session."""
    try:
        session_id = db.create_session(session_data.client_id, session_data.counselor_id)
        
        return APIResponse(
            success=True,
            message="Session created successfully",
            data={"session_id": session_id}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/messages", response_model=APIResponse)
async def add_message(session_id: int, message_data: MessageCreate):
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
async def get_session_messages(session_id: int, limit: int = 50):
    """Get messages from a session."""
    try:
        return db.get_session_messages(session_id, limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Character Card Routes
@router.post("/clients/{client_id}/character-cards", response_model=APIResponse)
async def create_character_card(client_id: int, card_data: CharacterCardCreate):
    """Create a new character card."""
    try:
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


@router.get("/clients/{client_id}/character-cards", response_model=List[CharacterCard])
async def get_character_cards(client_id: int):
    """Get all character cards for a client."""
    return db.get_character_cards(client_id)


# Game State Routes
@router.get("/clients/{client_id}/game-state", response_model=GameState)
async def get_game_state(client_id: int):
    """Get game state for a client."""
    game_state = db.get_game_state(client_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="Game state not found")
    return game_state


@router.post("/clients/{client_id}/game-state/award-coins", response_model=APIResponse)
async def award_coins(client_id: int, coins: int, reason: str = "session_completion"):
    """Award gold coins to a client."""
    try:
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
@router.get("/clients/{client_id}/farm-items", response_model=List[FarmItem])
async def get_farm_items(client_id: int):
    """Get all farm items for a client."""
    return db.get_farm_items(client_id)


@router.post("/clients/{client_id}/farm-items", response_model=APIResponse)
async def add_farm_item(client_id: int, item_data: FarmItemCreate):
    """Add a new farm item."""
    try:
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


@router.get("/clients/{client_id}/farm-shop", response_model=FarmShopResponse)
async def get_farm_shop(client_id: int):
    """Get farm shop items and player gold."""
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

@router.get("/clients/{client_id}/cards", response_model=APIResponse)
async def get_all_cards(
    client_id: int,
    page: int = Query(1, ge=1),
    page_size: str = Query("20")
) -> APIResponse:
    """
    Get all cards for a client (paginated).

    Query Params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, or "all" for all cards)

    Returns unified response with self, character, and world cards.
    """
    try:
        is_all = page_size.lower() == "all"
        limit = None if is_all else int(page_size)
        offset = 0 if is_all else (page - 1) * int(page_size)

        self_card = db.get_self_card(client_id)
        character_cards = db.get_character_cards(client_id)
        world_events = db.get_world_events(client_id)

        all_cards = []

        if self_card:
            all_cards.append({
                'id': self_card['id'],
                'card_type': 'self',
                'payload': json.loads(self_card['card_json']) if isinstance(self_card['card_json'], str) else self_card['card_json'],
                'auto_update_enabled': self_card['auto_update_enabled'],
                'is_pinned': self_card['is_pinned'],
                'created_at': self_card['created_at'],
                'updated_at': self_card['last_updated']
            })

        for card in character_cards:
            all_cards.append({
                'id': card['id'],
                'card_type': 'character',
                'payload': {**card['card'], 'name': card['card_name']},
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