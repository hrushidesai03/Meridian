"""
Endpoint to get comprehensive user data with all relationships intact.
Shows commitments, decisions, and alerts with their linkages.
"""
import logging
from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId

from database.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/user/{end_user_id}/comprehensive")
async def get_user_comprehensive_data(end_user_id: str):
    """
    Get all user data organized by relationships:
    - Commitments with their related decisions and alerts
    - Gap alerts (decisions not acted on)
    - Drift alerts (decisions contradicted by actions)
    """
    try:
        db = get_db()
        
        # Get commitments
        commitments = await db.commitments.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).to_list(100)
        
        # Get decisions
        decisions = await db.decisions.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).to_list(100)
        
        # Get alerts
        alerts = await db.alerts.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).to_list(100)
        
        # Convert ObjectIds and organize
        for c in commitments:
            c["_id"] = str(c["_id"])
            if "session_id" in c:
                c["session_id"] = str(c["session_id"])
        
        for d in decisions:
            d["_id"] = str(d["_id"])
            if "session_id" in d:
                d["session_id"] = str(d["session_id"])
        
        for a in alerts:
            a["_id"] = str(a["_id"])
            if "session_id" in a:
                a["session_id"] = str(a["session_id"])
            if "decision_id" in a:
                a["decision_id"] = str(a["decision_id"])
        
        # Link decisions to commitments (same session)
        for d in decisions:
            d["related_commitment"] = None
            for c in commitments:
                if c.get("session_id") == d.get("session_id"):
                    d["related_commitment"] = c["_id"]
                    break
        
        # Link alerts to decisions and commitments
        for a in alerts:
            a["related_decision"] = None
            a["related_commitment"] = None
            
            if a.get("decision_id"):
                for d in decisions:
                    if str(d.get("_id")) == str(a.get("decision_id")):
                        a["related_decision"] = d["_id"]
                        a["related_commitment"] = d.get("related_commitment")
                        break
        
        return {
            "end_user_id": end_user_id,
            "commitments": {
                "total": len(commitments),
                "data": commitments
            },
            "decisions": {
                "total": len(decisions),
                "data": decisions
            },
            "alerts": {
                "total": len(alerts),
                "drift": len([a for a in alerts if a.get("alert_type") == "drift"]),
                "gap": len([a for a in alerts if a.get("alert_type") == "gap"]),
                "data": alerts
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to get comprehensive data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{end_user_id}/alerts-by-decision")
async def get_alerts_grouped_by_decision(end_user_id: str):
    """
    Get alerts grouped by their related decision.
    Useful for showing which decisions have alerts.
    """
    try:
        db = get_db()
        
        alerts = await db.alerts.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).to_list(100)
        
        decisions = await db.decisions.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).to_list(100)
        
        for a in alerts:
            a["_id"] = str(a["_id"])
            if "decision_id" in a:
                a["decision_id"] = str(a["decision_id"])
        
        for d in decisions:
            d["_id"] = str(d["_id"])
        
        # Group alerts by decision
        alerts_by_decision = {}
        
        for d in decisions:
            decision_id = str(d["_id"])
            alerts_by_decision[decision_id] = {
                "decision": d,
                "alerts": [a for a in alerts if str(a.get("decision_id")) == decision_id]
            }
        
        # Add alerts without decision
        no_decision_alerts = [a for a in alerts if not a.get("decision_id")]
        
        return {
            "end_user_id": end_user_id,
            "alerts_by_decision": alerts_by_decision,
            "unlinked_alerts": no_decision_alerts,
            "total_decisions_with_alerts": len([v for v in alerts_by_decision.values() if v["alerts"]])
        }
    
    except Exception as e:
        logger.error(f"Failed to get alerts by decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))
