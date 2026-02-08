from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..models.schemas import APIResponse
from ..db.database import db


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("/{session_id}/analyze")
async def analyze_session_for_card_updates(session_id: int) -> APIResponse:
    """
    Analyze completed session and update cards invisibly.

    Called when user ends a counseling session. Runs CardUpdater
    to analyze transcript and apply updates to character cards, self cards,
    and world events.

    Response is minimal (only counters) to maintain "invisible updates" philosophy.
    Detailed changes are logged in change_log and performance_metrics tables.

    Returns:
        {
            "success": true,
            "message": "Session analysis complete.",
            "data": {
                "cards_updated": 3
            }
        }
    """
    try:
        session = db.get_session(session_id)
        if not session:
            return APIResponse(
                success=False,
                message="Session not found"
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
