import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta

from database.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/commitments")
async def search_commitments(
    end_user_id: str,
    query: Optional[str] = None,
    min_confidence: float = 0.0,
    flagged_only: bool = False,
    limit: int = 50
):
    """Search commitments with filters."""
    try:
        db = get_db()
        
        filters = {"end_user_id": end_user_id}
        
        if min_confidence > 0:
            filters["confidence_score"] = {"$gte": min_confidence}
        
        if flagged_only:
            filters["flagged_for_drift"] = True
        
        if query:
            # Text search on commitment text
            filters["$text"] = {"$search": query}
        
        commitments = await db.commitments.find(filters).sort("created_at", -1).limit(limit).to_list(limit)
        
        for commitment in commitments:
            commitment["_id"] = str(commitment["_id"])
        
        return {
            "query": query,
            "filters": {
                "min_confidence": min_confidence,
                "flagged_only": flagged_only
            },
            "commitments": commitments,
            "count": len(commitments)
        }
    
    except Exception as e:
        logger.error(f"Failed to search commitments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions")
async def search_decisions(
    end_user_id: str,
    query: Optional[str] = None,
    watch_term: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50
):
    """Search decisions with filters."""
    try:
        db = get_db()
        
        filters = {"end_user_id": end_user_id}
        
        if query:
            filters["$text"] = {"$search": query}
        
        if category:
            filters["category"] = category
        
        if watch_term:
            filters["watch_terms"] = {"$in": [watch_term]}
        
        decisions = await db.decisions.find(filters).sort("created_at", -1).limit(limit).to_list(limit)
        
        for decision in decisions:
            decision["_id"] = str(decision["_id"])
        
        return {
            "query": query,
            "filters": {
                "watch_term": watch_term,
                "category": category
            },
            "decisions": decisions,
            "count": len(decisions)
        }
    
    except Exception as e:
        logger.error(f"Failed to search decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def search_alerts(
    end_user_id: str,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    days: int = 30,
    limit: int = 50
):
    """Search alerts with filters."""
    try:
        db = get_db()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        filters = {
            "end_user_id": end_user_id,
            "created_at": {"$gte": cutoff_date}
        }
        
        if alert_type:
            filters["alert_type"] = alert_type
        
        if severity:
            filters["severity"] = severity
        
        if resolved is not None:
            filters["resolved"] = resolved
        
        alerts = await db.alerts.find(filters).sort("created_at", -1).limit(limit).to_list(limit)
        
        for alert in alerts:
            alert["_id"] = str(alert["_id"])
        
        return {
            "filters": {
                "alert_type": alert_type,
                "severity": severity,
                "resolved": resolved,
                "days": days
            },
            "alerts": alerts,
            "count": len(alerts)
        }
    
    except Exception as e:
        logger.error(f"Failed to search alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commitment-drift")
async def find_commitment_with_drifts(commitment_id: str):
    """Get a commitment and all its associated drift alerts."""
    try:
        db = get_db()
        
        # Get commitment
        from bson import ObjectId
        commitment = await db.commitments.find_one({"_id": ObjectId(commitment_id)})
        
        if not commitment:
            raise HTTPException(status_code=404, detail="Commitment not found")
        
        commitment["_id"] = str(commitment["_id"])
        
        # Get decisions
        decisions = await db.decisions.find(
            {"commitment_id": str(commitment["_id"])}
        ).to_list(None)
        
        for decision in decisions:
            decision["_id"] = str(decision["_id"])
        
        # Get drift alerts
        drift_alerts = await db.alerts.find({
            "commitment_id": str(commitment["_id"]),
            "alert_type": "drift"
        }).sort("created_at", -1).to_list(None)
        
        for alert in drift_alerts:
            alert["_id"] = str(alert["_id"])
        
        return {
            "commitment": commitment,
            "decisions": decisions,
            "drift_alerts": drift_alerts,
            "drift_count": len(drift_alerts)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find commitment with drifts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-summary/{end_user_id}")
async def get_user_summary(end_user_id: str):
    """Get summary statistics for a user."""
    try:
        db = get_db()
        
        # Count commitments by confidence level
        total_commitments = await db.commitments.count_documents({"end_user_id": end_user_id})
        high_confidence = await db.commitments.count_documents({
            "end_user_id": end_user_id,
            "confidence_score": {"$gte": 0.7}
        })
        flagged_commitments = await db.commitments.count_documents({
            "end_user_id": end_user_id,
            "flagged_for_drift": True
        })
        
        # Count decisions
        total_decisions = await db.decisions.count_documents({"end_user_id": end_user_id})
        
        # Count alerts
        total_alerts = await db.alerts.count_documents({"end_user_id": end_user_id})
        unresolved_alerts = await db.alerts.count_documents({
            "end_user_id": end_user_id,
            "resolved": False
        })
        
        gap_alerts = await db.alerts.count_documents({
            "end_user_id": end_user_id,
            "alert_type": "gap"
        })
        drift_alerts = await db.alerts.count_documents({
            "end_user_id": end_user_id,
            "alert_type": "drift"
        })
        
        return {
            "end_user_id": end_user_id,
            "commitments": {
                "total": total_commitments,
                "high_confidence": high_confidence,
                "flagged_for_drift": flagged_commitments
            },
            "decisions": {
                "total": total_decisions
            },
            "alerts": {
                "total": total_alerts,
                "unresolved": unresolved_alerts,
                "gap_alerts": gap_alerts,
                "drift_alerts": drift_alerts
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to get user summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
