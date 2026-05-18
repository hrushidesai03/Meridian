import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime

from database.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commitments", tags=["commitments"])


@router.get("")
async def get_commitments(end_user_id: str = "user_001"):
    """Get all commitments for a user."""
    db = get_db()
    docs = await db.commitments.find(
        {"end_user_id": end_user_id}
    ).sort("created_at", -1).to_list(100)
    for d in docs:
        d["_id"] = str(d["_id"])
    return {"commitments": docs, "count": len(docs)}


@router.get("/{commitment_id}")
async def get_commitment(commitment_id: str):
    """Get commitment details."""
    try:
        db = get_db()
        
        commitment = await db.commitments.find_one({"commitment_id": commitment_id})
        if not commitment:
            raise HTTPException(status_code=404, detail="Commitment not found")
        
        commitment["_id"] = str(commitment["_id"])
        return commitment
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get commitment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_commitments(session_id: str):
    """Get all commitments from a session."""
    try:
        db = get_db()
        
        commitments = await db.commitments.find(
            {"session_id": session_id}
        ).to_list(None)
        
        for commitment in commitments:
            commitment["_id"] = str(commitment["_id"])
        
        return {
            "session_id": session_id,
            "commitments": commitments,
            "count": len(commitments)
        }
    
    except Exception as e:
        logger.error(f"Failed to get session commitments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{end_user_id}")
async def get_user_commitments(end_user_id: str, limit: int = 100):
    """Get all commitments for a user."""
    try:
        db = get_db()
        
        commitments = await db.commitments.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        for commitment in commitments:
            commitment["_id"] = str(commitment["_id"])
        
        return {
            "end_user_id": end_user_id,
            "commitments": commitments,
            "count": len(commitments)
        }
    
    except Exception as e:
        logger.error(f"Failed to get user commitments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{commitment_id}/flag")
async def flag_commitment_for_drift(commitment_id: str, flag: bool = True):
    """Flag a commitment for drift detection."""
    try:
        db = get_db()
        
        result = await db.commitments.update_one(
            {"commitment_id": commitment_id},
            {"$set": {"flagged_for_drift": flag}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Commitment not found")
        
        return {
            "commitment_id": commitment_id,
            "flagged_for_drift": flag,
            "updated": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to flag commitment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flagged/{end_user_id}")
async def get_flagged_commitments(end_user_id: str):
    """Get all flagged commitments for a user."""
    try:
        db = get_db()
        
        commitments = await db.commitments.find(
            {
                "end_user_id": end_user_id,
                "flagged_for_drift": True
            }
        ).sort("created_at", -1).to_list(None)
        
        for commitment in commitments:
            commitment["_id"] = str(commitment["_id"])
        
        return {
            "end_user_id": end_user_id,
            "flagged_commitments": commitments,
            "count": len(commitments)
        }
    
    except Exception as e:
        logger.error(f"Failed to get flagged commitments: {e}")
        raise HTTPException(status_code=500, detail=str(e))
