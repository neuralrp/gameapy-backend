from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from ..models.schemas import APIResponse
from ..db.database import db
from ..auth import get_current_user


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/{session_id}/analyze")
async def analyze_session_for_card_updates(
    session_id: int,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """
    Analyze completed session and update cards invisibly.
    Uses authenticated user's ID from JWT.
    """
    try:
        session = db.get_session(session_id)
        if not session:
            return APIResponse(
                success=False,
                message="Session not found"
            )
        
        if session['client_id'] != current_user["id"]:
            return APIResponse(
                success=False,
                message="Access denied"
            )

        messages = db.get_session_messages(session_id)

        from ..services.card_updater import card_updater
        card_results = await card_updater.analyze_and_update(
            client_id=session['client_id'],
            session_id=session_id,
            messages=messages
        )

        return APIResponse(
            success=True,
            message="Session analysis complete.",
            data={
                "cards_updated": card_results['cards_updated']
            }
        )

    except Exception as e:
        return APIResponse(
            success=False,
            message=f"Analysis failed: {str(e)}"
        )
