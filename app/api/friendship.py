"""
Friendship Level API Endpoints

Endpoints for managing friendship levels between users and advisors.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from pydantic import BaseModel, Field
from ..models.schemas import APIResponse
from ..db.database import db
from ..services.friendship_analyzer import friendship_analyzer
from ..auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/friendship",
    tags=["friendship"]
)


class AnalyzeSessionRequest(BaseModel):
    session_id: int = Field(..., ge=1)


class FriendshipResponse(BaseModel):
    counselor_id: int
    level: int
    points: int
    counselor_name: Optional[str] = None
    last_interaction: Optional[str] = None


@router.get(
    "/{counselor_id}",
    response_model=APIResponse,
    summary="Get friendship level with a counselor"
)
async def get_friendship_level(
    counselor_id: int,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """Get the friendship level for a specific client-counselor pair."""
    try:
        client_id = current_user["id"]
        
        friendship = db.get_friendship_level(client_id, counselor_id)
        
        counselor = db.get_counselor_profile(counselor_id)
        counselor_name = counselor['profile']['data'].get('name') if counselor else None
        
        return APIResponse(
            success=True,
            message="Friendship level retrieved",
            data={
                "counselor_id": counselor_id,
                "level": friendship['level'],
                "points": friendship['points'],
                "counselor_name": counselor_name,
                "last_interaction": friendship.get('last_interaction'),
                "exists": friendship['exists']
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting friendship level: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/",
    response_model=APIResponse,
    summary="Get all friendship levels for current user"
)
async def get_all_friendship_levels(
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """Get all friendship levels for the current user."""
    try:
        client_id = current_user["id"]
        
        friendships = db.get_all_friendship_levels(client_id)
        
        return APIResponse(
            success=True,
            message="Friendship levels retrieved",
            data={
                "friendships": friendships
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting friendship levels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/analyze-session",
    response_model=APIResponse,
    summary="Analyze session for friendship growth"
)
async def analyze_session_friendship(
    request: AnalyzeSessionRequest,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """
    Analyze a completed session for friendship growth signals.
    Called at end of session to update friendship level.
    """
    try:
        client_id = current_user["id"]
        session_id = request.session_id
        
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session['client_id'] != client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )
        
        counselor_id = session['counselor_id']
        
        existing_friendship = db.get_friendship_level(client_id, counselor_id)
        last_analyzed = existing_friendship.get('last_analyzed_session')
        
        if last_analyzed and last_analyzed >= session_id:
            return APIResponse(
                success=True,
                message="Session already analyzed",
                data={
                    "points_delta": 0,
                    "new_level": existing_friendship['level'],
                    "already_analyzed": True
                }
            )
        
        messages = db.get_session_messages(session_id)
        
        if len(messages) < 2:
            return APIResponse(
                success=True,
                message="Not enough messages for analysis",
                data={
                    "points_delta": 0,
                    "new_level": existing_friendship['level']
                }
            )
        
        counselor = db.get_counselor_profile(counselor_id)
        counselor_name = counselor['profile']['data'].get('name', 'Advisor') if counselor else 'Advisor'
        
        analysis = await friendship_analyzer.analyze_session(
            messages=messages,
            counselor_name=counselor_name,
            current_level=existing_friendship['level'],
            current_points=existing_friendship['points']
        )
        
        if not analysis:
            logger.warning(f"Friendship analysis failed for session {session_id}")
            return APIResponse(
                success=False,
                message="Analysis failed",
                data={"points_delta": 0}
            )
        
        points_delta = analysis.get('points_delta', 0)
        
        updated = db.upsert_friendship_level(
            client_id=client_id,
            counselor_id=counselor_id,
            points_delta=points_delta,
            session_id=session_id
        )
        
        logger.info(
            f"Friendship updated: client={client_id}, counselor={counselor_id}, "
            f"delta={points_delta}, new_level={updated['level']}"
        )
        
        return APIResponse(
            success=True,
            message="Friendship analysis complete",
            data={
                "points_delta": points_delta,
                "new_level": updated['level'],
                "new_points": updated['points'],
                "reasoning": analysis.get('reasoning'),
                "signals_detected": analysis.get('signals_detected', []),
                "friendship_tier": analysis.get('friendship_tier')
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing session friendship: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/decay",
    response_model=APIResponse,
    summary="Run friendship decay job (internal)"
)
async def run_decay_job() -> APIResponse:
    """
    Run daily friendship decay job.
    Should be called by APScheduler, not directly.
    """
    try:
        affected = db.decay_friendship_levels(days_inactive=7, decay_amount=1)
        
        return APIResponse(
            success=True,
            message=f"Decay job completed. {affected} friendships decayed.",
            data={"affected_rows": affected}
        )
        
    except Exception as e:
        logger.error(f"Error running decay job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
