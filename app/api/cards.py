import json
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from ..models.schemas import (
    APIResponse,
    CardGenerateRequest,
    CardGenerateResponse,
    CardSaveRequest,
    CardSaveResponse,
    PaginationInfo,
    UnifiedCard,
    CardUpdateRequest,
    CardSearchRequest,
    CardSearchResponse,
    SearchResult,
    CardListResponse
)
from ..services.card_generator import card_generator
from ..db.database import db
from datetime import datetime


router = APIRouter(prefix="/api/v1/cards", tags=["cards"])


@router.post("/generate-from-text", response_model=APIResponse)
async def generate_card_from_text(request: CardGenerateRequest) -> APIResponse:
    """
    Generate a structured card from plain text (preview only, not saved).

    Request Body:
    {
        "card_type": "self|character|world",
        "plain_text": "My mom is overprotective...",
        "context": "Optional extra context",
        "name": "Optional name for character cards"
    }

    Response:
    {
        "success": true,
        "message": "Card generated successfully",
        "data": {
            "card_type": "character",
            "generated_card": {...full card JSON...},
            "preview": true,
            "fallback": false
        }
    }
    """
    try:
        result = await card_generator.generate_card(
            card_type=request.card_type,
            plain_text=request.plain_text,
            context=request.context,
            name=request.name
        )

        return APIResponse(
            success=True,
            message="Card generated successfully",
            data=result
        )

    except ValueError as e:
        return APIResponse(
            success=False,
            message=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Failed to generate card: {str(e)}"
        )


@router.post("/save", response_model=APIResponse)
async def save_card(request: CardSaveRequest) -> APIResponse:
    """
    Save a generated card to database.

    Request Body:
    {
        "client_id": 1,
        "card_type": "self|character|world",
        "card_data": {...full card JSON...}
    }

    Response:
    {
        "success": true,
        "message": "Card saved successfully",
        "data": {"card_id": 123}
    }
    """
    try:
        if request.card_type == "self":
            card_id = db.create_self_card(
                client_id=request.client_id,
                card_json=json.dumps(request.card_data)
            )
        elif request.card_type == "character":
            card_id = db.create_character_card(
                client_id=request.client_id,
                card_name=request.card_data["name"],
                relationship_type=request.card_data["relationship_type"],
                card_data=request.card_data
            )
        elif request.card_type == "world":
            import uuid
            card_id = db.create_world_event(
                client_id=request.client_id,
                entity_id=request.card_data.get("entity_id", f"world_{uuid.uuid4().hex}"),
                title=request.card_data["title"],
                key_array=json.dumps(request.card_data["key_array"]),
                description=request.card_data["description"],
                event_type=request.card_data["event_type"],
                is_canon_law=request.card_data.get("is_canon_law", False),
                resolved=request.card_data.get("resolved", False)
            )
        else:
            return APIResponse(
                success=False,
                message=f"Invalid card type: {request.card_type}"
            )

        return APIResponse(
            success=True,
            message="Card saved successfully",
            data={"card_id": card_id}
        )

    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Failed to save card: {str(e)}"
        )


# ============================================================
# Phase 3: Unified Card Management Endpoints
# ============================================================

@router.put("/{card_id}", response_model=APIResponse)
async def update_card(card_id: int, request: CardUpdateRequest) -> APIResponse:
    """
    Partially update a card (merge provided fields, keep existing).

    Only fields present in request are updated.
    Requires card_type to identify which table to update.
    """
    try:
        success = False

        if request.card_type == 'self':
            # For self cards, we need to look up the client_id first
            # since update_self_card takes client_id, not card_id
            self_card = db.get_self_card_by_id(card_id)
            if not self_card:
                return APIResponse(
                    success=False,
                    message="Self card not found"
                )
            client_id = self_card['client_id']

            if request.card_json is not None:
                success = db.update_self_card(
                    client_id=client_id,
                    card_json=request.card_json,
                    changed_by='user'
                )
            if request.auto_update_enabled is not None:
                success = db.update_auto_update_enabled(
                    card_type='self',
                    card_id=card_id,
                    enabled=request.auto_update_enabled
                )

        elif request.card_type == 'character':
            update_kwargs = {}
            if request.card_name is not None:
                update_kwargs['card_name'] = request.card_name
            if request.relationship_type is not None:
                update_kwargs['relationship_type'] = request.relationship_type
            if request.card_data is not None:
                update_kwargs['card_json'] = json.dumps(request.card_data)

            if update_kwargs:
                update_kwargs['changed_by'] = 'user'
                success = db.update_character_card(card_id, **update_kwargs)

            if request.auto_update_enabled is not None:
                success = db.update_auto_update_enabled(
                    card_type='character',
                    card_id=card_id,
                    enabled=request.auto_update_enabled
                )

        elif request.card_type == 'world':
            update_kwargs = {}
            if request.title is not None:
                update_kwargs['title'] = request.title
            if request.key_array is not None:
                update_kwargs['key_array'] = request.key_array
            if request.description is not None:
                update_kwargs['description'] = request.description
            if request.event_type is not None:
                update_kwargs['event_type'] = request.event_type
            if request.is_canon_law is not None:
                update_kwargs['is_canon_law'] = request.is_canon_law
            if request.resolved is not None:
                update_kwargs['resolved'] = request.resolved

            if update_kwargs:
                update_kwargs['changed_by'] = 'user'
                success = db.update_world_event(card_id, **update_kwargs)

            if request.auto_update_enabled is not None:
                success = db.update_auto_update_enabled(
                    card_type='world',
                    card_id=card_id,
                    enabled=request.auto_update_enabled
                )
        else:
            return APIResponse(
                success=False,
                message=f"Invalid card type: {request.card_type}"
            )

        if success:
            return APIResponse(
                success=True,
                message="Card updated successfully",
                data={"card_id": card_id}
            )
        else:
            return APIResponse(
                success=False,
                message="No fields were updated"
            )

    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Failed to update card: {str(e)}"
        )


@router.put("/{card_id}/toggle-auto-update", response_model=APIResponse)
async def toggle_auto_update(
    card_id: int,
    card_type: str = Query(..., description="Card type: self, character, world")
) -> APIResponse:
    """
    Toggle auto-update enabled status for a card.
    """
    try:
        current_value = db._get_auto_update_enabled(card_type, card_id)
        if current_value is None:
            return APIResponse(
                success=False,
                message="Card not found"
            )

        success = db.update_auto_update_enabled(
            card_type=card_type,
            card_id=card_id,
            enabled=not current_value
        )

        if success:
            return APIResponse(
                success=True,
                message="Auto-update toggled successfully"
            )
        else:
            return APIResponse(
                success=False,
                message="Failed to toggle auto-update"
            )
    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Error: {str(e)}"
        )


@router.put("/{card_type}/{id}/pin")
async def pin_card_endpoint(card_type: str, id: int):
    """Pin a card to always load in context."""
    success = db.pin_card(card_type, id)
    return APIResponse(
        success=success,
        message="Card pinned" if success else "Failed to pin card"
    )


@router.put("/{card_type}/{id}/unpin")
async def unpin_card_endpoint(card_type: str, id: int):
    """Unpin a card."""
    success = db.unpin_card(card_type, id)
    return APIResponse(
        success=success,
        message="Card unpinned" if success else "Failed to unpin card"
    )


@router.get("/search", response_model=APIResponse)
async def search_cards(
    q: str = Query(..., description="Search query"),
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    types: Optional[str] = Query(None, description="Comma-separated types: self,character,world"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
) -> APIResponse:
    """
    Search across all card types or filter by specific types.
    """
    try:
        type_filter = None
        if types:
            type_filter = [t.strip() for t in types.split(',')]

        search_results = db.search_cards(
            query=q,
            card_types=type_filter,
            client_id=client_id,
            limit=100
        )

        total_items = len(search_results)
        offset = (page - 1) * page_size
        paginated_items = search_results[offset:offset + page_size]
        total_pages = (total_items + page_size - 1) // page_size

        return APIResponse(
            success=True,
            message=f"Found {len(paginated_items)} cards",
            data={
                'items': paginated_items,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': total_pages,
                    'total_items': total_items
                }
            }
        )
    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Search failed: {str(e)}"
        )


@router.delete("/{card_id}", response_model=APIResponse)
async def delete_card(
    card_id: int,
    card_type: str = Query(..., description="Card type: self, character, world")
) -> APIResponse:
    """
    Delete a card by ID and type.
    """
    try:
        success = db.delete_card(card_type=card_type, card_id=card_id)

        if success:
            return APIResponse(
                success=True,
                message="Card deleted successfully"
            )
        else:
            return APIResponse(
                success=False,
                message="Card not found or delete failed"
            )
    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Failed to delete card: {str(e)}"
        )
