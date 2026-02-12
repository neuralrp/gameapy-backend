from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from pydantic import BaseModel, Field
from ..models.schemas import APIResponse
from ..db.database import db
from ..services.advisor_generator import advisor_generator
from ..auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/counselors/custom",
    tags=["custom-counselors"]
)


class AdvisorCreateRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=50
    )
    specialty: str = Field(
        ...,
        min_length=3,
        max_length=200
    )
    vibe: str = Field(
        ...,
        min_length=3,
        max_length=200
    )


class AdvisorUpdateRequest(BaseModel):
    counselor_id: int = Field(..., ge=1)
    persona_data: dict


@router.post(
    "/create",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom advisor"
)
async def create_custom_advisor(
    request: AdvisorCreateRequest,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """Create a custom advisor from 3 questions."""
    try:
        client_id = current_user["id"]
        
        current_count = db.count_custom_counselors(client_id)
        if current_count >= 5:
            logger.warning(
                f"Client {client_id} attempted to exceed advisor limit"
            )
            return APIResponse(
                success=False,
                message="Maximum of 5 custom advisors allowed. Delete an advisor to create a new one.",
                data={"current_count": current_count, "max_allowed": 5}
            )
        
        logger.info(
            f"Generating advisor for client {client_id}: {request.name}"
        )
        
        persona = await advisor_generator.generate_advisor(
            name=request.name,
            specialty=request.specialty,
            vibe=request.vibe
        )
        
        counselor_id = db.create_custom_counselor(
            client_id=client_id,
            persona_data=persona
        )
        
        logger.info(
            f"Created custom advisor {counselor_id} for client {client_id}"
        )
        
        return APIResponse(
            success=True,
            message="Advisor created successfully",
            data={
                "counselor_id": counselor_id,
                "persona": persona
            }
        )
        
    except ValueError as e:
        logger.error(f"Validation error creating advisor: {str(e)}")
        return APIResponse(
            success=False,
            message=f"Invalid input: {str(e)}"
        )
        
    except Exception as e:
        logger.exception("Unexpected error creating advisor")
        return APIResponse(
            success=False,
            message=f"Failed to create advisor: {str(e)}"
        )


@router.get(
    "/list",
    response_model=List[dict],
    summary="List custom advisors"
)
async def list_custom_advisors(
    current_user: dict = Depends(get_current_user)
) -> List[dict]:
    """Get all custom advisors for the authenticated user."""
    try:
        client_id = current_user["id"]
        advisors = db.get_custom_counselors(client_id)
        
        return [
            {
                "id": adv['id'],
                "entity_id": adv['entity_id'],
                "name": adv['name'],
                "specialization": adv['specialization'],
                "therapeutic_style": adv['therapeutic_style'],
                "credentials": adv['credentials'],
                "profile": adv['profile'],
                "tags": adv['tags'],
                "created_at": adv['created_at'],
                "updated_at": adv['updated_at']
            }
            for adv in advisors
        ]
        
    except Exception as e:
        logger.exception(f"Error listing advisors for client {current_user['id']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve advisors"
        )


@router.put(
    "/update",
    response_model=APIResponse,
    summary="Update custom advisor"
)
async def update_custom_advisor(
    request: AdvisorUpdateRequest,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """Update a custom advisor."""
    try:
        client_id = current_user["id"]
        
        if not isinstance(request.persona_data, dict):
            return APIResponse(
                success=False,
                message="persona_data must be an object"
            )
        
        if 'data' not in request.persona_data:
            return APIResponse(
                success=False,
                message="persona_data must contain 'data' key"
            )
        
        counselor = db.get_counselor_profile(request.counselor_id)
        if not counselor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Advisor not found"
            )
        
        if counselor.get('client_id') != client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        success = db.update_custom_counselor(
            counselor_id=request.counselor_id,
            persona_data=request.persona_data
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update advisor"
            )
        
        logger.info(f"Updated custom advisor {request.counselor_id}")
        
        return APIResponse(
            success=True,
            message="Advisor updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating advisor {request.counselor_id}")
        return APIResponse(
            success=False,
            message=f"Failed to update advisor: {str(e)}"
        )


@router.delete(
    "/{counselor_id}",
    response_model=APIResponse,
    summary="Delete custom advisor"
)
async def delete_custom_advisor(
    counselor_id: int,
    current_user: dict = Depends(get_current_user)
) -> APIResponse:
    """Delete (soft-delete) a custom advisor."""
    try:
        client_id = current_user["id"]
        
        success = db.delete_custom_counselor(
            counselor_id=counselor_id,
            client_id=client_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Advisor not found or not owned by this client"
            )
        
        logger.info(
            f"Deleted custom advisor {counselor_id} "
            f"by client {client_id}"
        )
        
        return APIResponse(
            success=True,
            message="Advisor deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting advisor {counselor_id}")
        return APIResponse(
            success=False,
            message=f"Failed to delete advisor: {str(e)}"
        )
