from fastapi import APIRouter
from ..models.schemas import APIResponse
from ..services.guide_system import guide_system

router = APIRouter(prefix="/guide", tags=["Guide"])


# NEW: Organic conversation endpoints
@router.post("/conversation/start")
async def start_conversation(client_id: int):
    """Start organic guide conversation."""
    result = await guide_system.start_conversation(client_id)
    return APIResponse(success=True, message="Started conversation", data=result)


@router.post("/conversation/input")
async def process_conversation_input(session_id: int, user_input: str):
    """Process user input in organic conversation."""
    result = await guide_system.process_conversation(session_id, user_input)
    return APIResponse(success=True, message="Processed input", data=result)


@router.post("/conversation/confirm-card")
async def confirm_card_creation(session_id: int, card_type: str, topic: str):
    """Confirm and create suggested card."""
    result = await guide_system.confirm_card_creation(
        session_id=session_id, card_type=card_type, topic=topic
    )
    return APIResponse(success=True, message="Card created", data=result)


# DEPRECATED: Old 3-phase endpoints (remove after migration)
# These are kept for backward compatibility but will be removed in future versions
# @router.post("/onboarding")
# async def start_onboarding(...): ...

# @router.post("/onboarding/input")  
# async def process_onboarding_input(...): ...