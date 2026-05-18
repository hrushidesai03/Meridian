import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime

from database.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("")
async def get_decisions(end_user_id: str = "user_001"):
    """Get all decisions for a user."""
    db = get_db()
    docs = await db.decisions.find(
        {"end_user_id": end_user_id}
    ).sort("created_at", -1).to_list(100)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


@router.get("/{decision_id}")
async def get_decision(decision_id: str):
    """Get decision details."""
    try:
        db = get_db()
        
        decision = await db.decisions.find_one({"decision_id": decision_id})
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")
        
        decision["_id"] = str(decision["_id"])
        return decision
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commitment/{commitment_id}")
async def get_commitment_decisions(commitment_id: str):
    """Get all decisions linked to a commitment."""
    try:
        db = get_db()
        
        decisions = await db.decisions.find(
            {"commitment_id": commitment_id}
        ).to_list(None)
        
        for decision in decisions:
            decision["_id"] = str(decision["_id"])
        
        return {
            "commitment_id": commitment_id,
            "decisions": decisions,
            "count": len(decisions)
        }
    
    except Exception as e:
        logger.error(f"Failed to get commitment decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_decisions(session_id: str):
    """Get all decisions from a session."""
    try:
        db = get_db()
        
        decisions = await db.decisions.find(
            {"session_id": session_id}
        ).to_list(None)
        
        for decision in decisions:
            decision["_id"] = str(decision["_id"])
        
        return {
            "session_id": session_id,
            "decisions": decisions,
            "count": len(decisions)
        }
    
    except Exception as e:
        logger.error(f"Failed to get session decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{end_user_id}")
async def get_user_decisions(end_user_id: str, limit: int = 100):
    """Get all decisions for a user."""
    try:
        db = get_db()
        
        decisions = await db.decisions.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        for decision in decisions:
            decision["_id"] = str(decision["_id"])
        
        return {
            "end_user_id": end_user_id,
            "decisions": decisions,
            "count": len(decisions)
        }
    
    except Exception as e:
        logger.error(f"Failed to get user decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-drift")
async def verify_decision_drift_check(
    decision_id: str,
    screen_observation: str
):
    """Verify if a decision is drifting based on screen observation."""
    try:
        from services.claude_service import verify_decision_drift
        
        db = get_db()
        
        # Get decision
        decision = await db.decisions.find_one({"decision_id": decision_id})
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found")
        
        # Run drift verification
        drift_result = await verify_decision_drift(
            decision_text=decision["text"],
            watch_terms=decision.get("watch_terms", []),
            screen_observation=screen_observation
        )
        
        # If drift detected, create alert
        if drift_result.get("drift_detected"):
            alert_doc = {
                "alert_type": "drift",
                "commitment_id": decision.get("commitment_id"),
                "decision_id": decision_id,
                "end_user_id": decision["end_user_id"],
                "drift_description": drift_result.get("drift_description"),
                "drift_evidence": drift_result.get("evidence"),
                "created_at": datetime.utcnow(),
                "resolved": False
            }
            
            alert_result = await db.alerts.insert_one(alert_doc)
            
            logger.info(f"Created drift alert: {alert_result.inserted_id}")
            
            return {
                "drift_detected": True,
                "alert_id": str(alert_result.inserted_id),
                "drift_description": drift_result.get("drift_description"),
                "severity": drift_result.get("severity", "medium")
            }
        
        return {
            "drift_detected": False,
            "message": "No drift detected"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify drift: {e}")
        raise HTTPException(status_code=500, detail=str(e))
