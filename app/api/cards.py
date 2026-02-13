import json
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, Any, Optional, List
from ..models.schemas import (
    APIResponse,
    CardGenerateRequest,
    CardSaveRequest,
    CardUpdateRequest,
)
from ..services.card_generator import card_generator
from ..db.database import db
from ..utils.card_metadata import reset_card_metadata
from ..auth import get_current_user
from datetime import datetime


router = APIRouter(prefix="/api/v1/cards", tags=["cards"])


@router.post("/generate-from-text", response_model=APIResponse)
async def generate_card_from_text(
    request: CardGenerateRequest,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """
    Generate a structured card from plain text (preview only, not saved).
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
async def save_card(
    request: CardSaveRequest,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """
    Save a generated card to database.
    Uses authenticated user's ID from JWT.
    """
    try:
        client_id = current_user["id"]
        
        if request.card_type == "self":
            normalized_payload = db.normalize_self_card_payload(request.card_data)
            card_id = db.upsert_self_card(
                client_id=client_id,
                card_json=normalized_payload,
                changed_by='user'
            )
        elif request.card_type == "character":
            card_id = db.create_character_card(
                client_id=client_id,
                card_name=request.card_data["name"],
                relationship_type=request.card_data["relationship_type"],
                relationship_label=request.card_data.get("relationship_label"),
                card_data=request.card_data
            )
        elif request.card_type == "world":
            import uuid
            card_id = db.create_world_event(
                client_id=client_id,
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

        db.update_gold_coins(client_id, 10, "card_created")

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


@router.put("/{card_id}", response_model=APIResponse)
async def update_card(
    card_id: int,
    request: CardUpdateRequest,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """
    Partially update a card (merge provided fields, keep existing).
    """
    try:
        client_id = current_user["id"]
        success = False
        request_dict = request.model_dump(exclude_none=True, exclude={'card_type'})

        if request.card_type == 'self':
            self_card = db.get_self_card_by_id(card_id)
            if not self_card:
                return APIResponse(
                    success=False,
                    message="Self card not found"
                )
            
            if self_card['client_id'] != client_id:
                return APIResponse(
                    success=False,
                    message="Access denied"
                )

            card_json = self_card['card_json']
            existing_data = json.loads(card_json) if isinstance(card_json, str) else card_json
            updated_data = {**existing_data}

            if 'name' in request_dict:
                updated_data['name'] = request_dict.pop('name')
            elif 'card_name' in request_dict:
                updated_data['name'] = request_dict.pop('card_name')

            if 'description' in request_dict:
                updated_data['description'] = request_dict.pop('description')
            if 'personality' in request_dict:
                updated_data['personality'] = request_dict.pop('personality')
            if 'background' in request_dict:
                updated_data['background'] = request_dict.pop('background')

            updated_data_with_metadata = reset_card_metadata(updated_data)
            success = db.update_self_card(
                client_id=client_id,
                card_json=json.dumps(updated_data_with_metadata),
                changed_by='user'
            )

            if 'auto_update_enabled' in request_dict:
                db.update_auto_update_enabled(
                    card_type='self',
                    card_id=card_id,
                    enabled=request_dict['auto_update_enabled']
                )

        elif request.card_type == 'character':
            char_card = db.get_character_card_by_id(card_id)
            if not char_card:
                return APIResponse(
                    success=False,
                    message="Character card not found"
                )
            
            if char_card['client_id'] != client_id:
                return APIResponse(
                    success=False,
                    message="Access denied"
                )
            
            update_kwargs = {}

            if 'name' in request_dict:
                update_kwargs['card_name'] = request_dict.pop('name')
            elif 'card_name' in request_dict:
                update_kwargs['card_name'] = request_dict.pop('card_name')

            if 'relationship_type' in request_dict:
                update_kwargs['relationship_type'] = request_dict.pop('relationship_type')
            if 'relationship_label' in request_dict:
                update_kwargs['relationship_label'] = request_dict.pop('relationship_label')

            if 'personality' in request_dict or 'card_data' in request_dict:
                existing_card_data = json.loads(char_card['card_json']) if char_card['card_json'] else {}
                updated_card_data = {**existing_card_data}

                if 'personality' in request_dict:
                    updated_card_data['personality'] = request_dict.pop('personality')
                if 'card_data' in request_dict:
                    updated_card_data.update(request_dict.pop('card_data'))

                update_kwargs['card_json'] = json.dumps(updated_card_data)

            if update_kwargs:
                if 'card_json' in update_kwargs:
                    card_data = json.loads(update_kwargs['card_json'])
                    card_data_with_metadata = reset_card_metadata(card_data)
                    update_kwargs['card_json'] = json.dumps(card_data_with_metadata)
                update_kwargs['changed_by'] = 'user'
                success = db.update_character_card(card_id, **update_kwargs)

            if 'auto_update_enabled' in request_dict:
                db.update_auto_update_enabled(
                    card_type='character',
                    card_id=card_id,
                    enabled=request_dict['auto_update_enabled']
                )

        elif request.card_type == 'world':
            world_event = db.get_world_event_by_id(card_id)
            if not world_event:
                return APIResponse(
                    success=False,
                    message="World event not found"
                )
            
            if world_event['client_id'] != client_id:
                return APIResponse(
                    success=False,
                    message="Access denied"
                )
            
            update_kwargs = {}
            if 'title' in request_dict:
                update_kwargs['title'] = request_dict.pop('title')
            if 'key_array' in request_dict:
                update_kwargs['key_array'] = request_dict.pop('key_array')
            if 'description' in request_dict:
                update_kwargs['description'] = request_dict.pop('description')
            if 'event_type' in request_dict:
                update_kwargs['event_type'] = request_dict.pop('event_type')
            if 'is_canon_law' in request_dict:
                update_kwargs['is_canon_law'] = request_dict.pop('is_canon_law')
            if 'resolved' in request_dict:
                update_kwargs['resolved'] = request_dict.pop('resolved')

            if update_kwargs:
                update_kwargs['changed_by'] = 'user'
                success = db.update_world_event(card_id, **update_kwargs)

            if 'auto_update_enabled' in request_dict:
                db.update_auto_update_enabled(
                    card_type='world',
                    card_id=card_id,
                    enabled=request_dict['auto_update_enabled']
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
    card_type: str = Query(..., description="Card type: self, character, world"),
    current_user: dict = Depends(get_current_user)
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
async def pin_card_endpoint(
    card_type: str,
    id: int,
    current_user: dict = Depends(get_current_user)
):
    """Pin a card to always load in context."""
    success = db.pin_card(card_type, id)
    return APIResponse(
        success=success,
        message="Card pinned" if success else "Failed to pin card"
    )


@router.put("/{card_type}/{id}/unpin")
async def unpin_card_endpoint(
    card_type: str,
    id: int,
    current_user: dict = Depends(get_current_user)
):
    """Unpin a card."""
    success = db.unpin_card(card_type, id)
    return APIResponse(
        success=success,
        message="Card unpinned" if success else "Failed to unpin card"
    )


@router.get("/search", response_model=APIResponse)
async def search_cards(
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated types: self,character,world"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """
    Search across all card types for current user.
    """
    try:
        client_id = current_user["id"]
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
    card_type: str = Query(..., description="Card type: self, character, world"),
    current_user: dict = Depends(get_current_user)
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
