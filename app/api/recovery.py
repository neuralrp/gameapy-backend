"""
Recovery API Router

Provides endpoints for account recovery using recovery codes.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict
from ..db.database import db
from ..models.schemas import APIResponse
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recovery", tags=["recovery"])

# Rate limiting storage (in-memory for alpha stage)
# Format: {ip_address: [timestamp1, timestamp2, timestamp3]}
_recovery_attempts: Dict[str, list] = {}
MAX_ATTEMPTS = 3
TIME_WINDOW = 3600  # 1 hour in seconds


def _check_rate_limit(ip_address: str) -> bool:
    """Check if IP has exceeded rate limit for recovery attempts."""
    now = time.time()
    
    # Clean old entries
    if ip_address in _recovery_attempts:
        _recovery_attempts[ip_address] = [
            ts for ts in _recovery_attempts[ip_address]
            if now - ts < TIME_WINDOW
        ]
    
    # Check if exceeded limit
    if ip_address not in _recovery_attempts:
        _recovery_attempts[ip_address] = []
    
    if len(_recovery_attempts[ip_address]) >= MAX_ATTEMPTS:
        return False
    
    # Record this attempt
    _recovery_attempts[ip_address].append(now)
    return True


@router.post("/generate", response_model=APIResponse)
async def generate_recovery_code(request: Request, client_id: int):
    """
    Generate new recovery code for existing client.
    This will invalidate the old recovery code.
    """
    if db is None:
        logger.error("[Recovery] Database not initialized")
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        recovery_code = db.generate_new_recovery_code(client_id)
        
        if recovery_code is None:
            logger.warning(f"[Recovery] Client {client_id} not found for code generation")
            return APIResponse(
                success=False,
                message="Client not found"
            )
        
        logger.info(f"[Recovery] Generated new code for client {client_id}")
        return APIResponse(
            success=True,
            message="Recovery code generated successfully. Save this code - your old code is now invalid.",
            data={"recovery_code": recovery_code}
        )
    except Exception as e:
        logger.error(f"[Recovery] Failed to generate code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=APIResponse)
async def validate_recovery_code(request: Request, recovery_code: str):
    """
    Validate recovery code and return client_id if valid.
    Rate limited: 3 attempts per hour per IP.
    """
    # Get client IP for rate limiting
    client_ip = request.client.host
    
    if not _check_rate_limit(client_ip):
        logger.warning(f"[Recovery] Rate limit exceeded for IP {client_ip}")
        return APIResponse(
            success=False,
            message="Too many attempts. Please try again in 1 hour."
        )
    
    if db is None:
        logger.error("[Recovery] Database not initialized")
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        client_id = db.validate_recovery_code(recovery_code)
        
        if client_id is None:
            logger.warning(f"[Recovery] Invalid code attempt from {client_ip}")
            return APIResponse(
                success=False,
                message="Invalid or expired recovery code"
            )
        
        logger.info(f"[Recovery] Successfully recovered client {client_id}")
        return APIResponse(
            success=True,
            message="Recovery code validated successfully",
            data={"client_id": client_id}
        )
    except Exception as e:
        logger.error(f"[Recovery] Failed to validate code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{client_id}", response_model=APIResponse)
async def get_recovery_status(client_id: int):
    """
    Get recovery code status for a client.
    """
    if db is None:
        logger.error("[Recovery] Database not initialized")
        raise HTTPException(status_code=503, detail="Database not initialized")
    
    try:
        status = db.get_recovery_code_status(client_id)
        
        if status is None:
            return APIResponse(
                success=False,
                message="Client not found"
            )
        
        return APIResponse(
            success=True,
            message="Recovery status retrieved",
            data=status
        )
    except Exception as e:
        logger.error(f"[Recovery] Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
