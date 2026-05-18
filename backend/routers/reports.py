import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timedelta

from database.db import get_db
from agents.orchestration import RetrospectiveAgent
from services.claude_service import generate_sprint_retro

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/accountability/{end_user_id}")
async def get_accountability_report(
    end_user_id: str,
    days: int = 30,
    include_resolved: bool = False
):
    """Get accountability report for a user."""
    try:
        db = get_db()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        alert_filters = {
            "end_user_id": end_user_id,
            "created_at": {"$gte": cutoff_date}
        }
        
        if not include_resolved:
            alert_filters["resolved"] = False
        
        # Get alerts
        alerts = await db.alerts.find(alert_filters).sort("created_at", -1).to_list(None)
        
        for alert in alerts:
            alert["_id"] = str(alert["_id"])
        
        # Count by type
        gap_count = len([a for a in alerts if a["alert_type"] == "gap"])
        drift_count = len([a for a in alerts if a["alert_type"] == "drift"])
        
        # Count by severity
        severity_counts = {}
        for alert in alerts:
            severity = alert.get("severity", "medium")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Count by resolution
        resolved_count = len([a for a in alerts if a.get("resolved", False)])
        unresolved_count = len(alerts) - resolved_count
        
        return {
            "end_user_id": end_user_id,
            "period_days": days,
            "report_generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_alerts": len(alerts),
                "gap_alerts": gap_count,
                "drift_alerts": drift_count,
                "resolved": resolved_count,
                "unresolved": unresolved_count,
                "severity_breakdown": severity_counts
            },
            "alerts": alerts
        }
    
    except Exception as e:
        logger.error(f"Failed to generate accountability report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/receipts/{end_user_id}")
async def get_accountability_receipts(
    end_user_id: str,
    limit: int = 50
):
    """Get accountability receipts (videos) for a user."""
    try:
        db = get_db()
        
        # Find alerts with receipts
        alerts_with_receipts = await db.alerts.find({
            "end_user_id": end_user_id,
            "receipt": {"$exists": True}
        }).sort("created_at", -1).limit(limit).to_list(limit)
        
        receipts = []
        
        for alert in alerts_with_receipts:
            receipt = alert.get("receipt", {})
            
            receipts.append({
                "alert_id": str(alert["_id"]),
                "alert_type": alert["alert_type"],
                "created_at": alert["created_at"],
                "receipt": {
                    "video_id": receipt.get("video_id"),
                    "video_url": receipt.get("video_url"),
                    "narrative": receipt.get("narrative"),
                    "generated_at": receipt.get("generated_at")
                }
            })
        
        return {
            "end_user_id": end_user_id,
            "receipts": receipts,
            "count": len(receipts)
        }
    
    except Exception as e:
        logger.error(f"Failed to get accountability receipts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commitment-analysis/{commitment_id}")
async def get_commitment_analysis(commitment_id: str):
    """Detailed analysis of a commitment and its lifecycle."""
    try:
        from bson import ObjectId
        db = get_db()
        
        # Get commitment
        commitment = await db.commitments.find_one({"_id": ObjectId(commitment_id)})
        
        if not commitment:
            raise HTTPException(status_code=404, detail="Commitment not found")
        
        commitment["_id"] = str(commitment["_id"])
        
        # Get related decisions
        decisions = await db.decisions.find(
            {"commitment_id": commitment_id}
        ).to_list(None)
        
        for decision in decisions:
            decision["_id"] = str(decision["_id"])
        
        # Get related alerts
        alerts = await db.alerts.find({
            "commitment_id": commitment_id
        }).sort("created_at", -1).to_list(None)
        
        for alert in alerts:
            alert["_id"] = str(alert["_id"])
        
        # Get source session
        session = None
        if commitment.get("session_id"):
            session = await db.sessions.find_one(
                {"session_id": commitment["session_id"]}
            )
            if session:
                session["_id"] = str(session["_id"])
        
        return {
            "commitment": commitment,
            "session": session,
            "decisions": decisions,
            "alerts": alerts,
            "analysis": {
                "confidence_score": commitment.get("confidence_score", 0),
                "risk_factors": commitment.get("risk_factors", []),
                "decision_count": len(decisions),
                "alert_count": len(alerts),
                "is_flagged": commitment.get("flagged_for_drift", False)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get commitment analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-summary")
async def generate_team_summary(
    end_user_ids: List[str],
    days: int = 30
):
    """Generate summary report for a team of users."""
    try:
        db = get_db()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        team_stats = {
            "team_size": len(end_user_ids),
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "users": []
        }
        
        for user_id in end_user_ids:
            user_alerts = await db.alerts.find({
                "end_user_id": user_id,
                "created_at": {"$gte": cutoff_date}
            }).to_list(None)
            
            user_commitments = await db.commitments.find({
                "end_user_id": user_id,
                "created_at": {"$gte": cutoff_date}
            }).to_list(None)
            
            high_confidence_count = len([
                c for c in user_commitments 
                if c.get("confidence_score", 0) >= 0.7
            ])
            
            gap_count = len([a for a in user_alerts if a["alert_type"] == "gap"])
            drift_count = len([a for a in user_alerts if a["alert_type"] == "drift"])
            
            team_stats["users"].append({
                "user_id": user_id,
                "commitments": len(user_commitments),
                "high_confidence_commitments": high_confidence_count,
                "total_alerts": len(user_alerts),
                "gap_alerts": gap_count,
                "drift_alerts": drift_count
            })
        
        # Calculate team totals
        total_commitments = sum(u["commitments"] for u in team_stats["users"])
        total_alerts = sum(u["total_alerts"] for u in team_stats["users"])
        total_gaps = sum(u["gap_alerts"] for u in team_stats["users"])
        total_drifts = sum(u["drift_alerts"] for u in team_stats["users"])
        
        team_stats["totals"] = {
            "commitments": total_commitments,
            "alerts": total_alerts,
            "gap_alerts": total_gaps,
            "drift_alerts": total_drifts,
            "avg_commitments_per_person": total_commitments / len(end_user_ids) if end_user_ids else 0,
            "avg_alerts_per_person": total_alerts / len(end_user_ids) if end_user_ids else 0
        }
        
        return team_stats
    
    except Exception as e:
        logger.error(f"Failed to generate team summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retro")
async def generate_retro(request: Request):
    """Generate sprint retrospective from commitments and decisions."""
    try:
        body = await request.json()
        end_user_id = body.get("end_user_id", "user_001")
        date_range = body.get("date_range", "this week")
        
        db = get_db()
        
        commitments = await db.commitments.find(
            {"end_user_id": end_user_id}
        ).to_list(100)
        
        decisions = await db.decisions.find(
            {"end_user_id": end_user_id}
        ).to_list(100)
        
        # Convert ObjectId to string
        for c in commitments:
            c["_id"] = str(c["_id"])
        for d in decisions:
            d["_id"] = str(d["_id"])
        
        result = await generate_sprint_retro(commitments, decisions, date_range)
        return result
    
    except Exception as e:
        logger.error(f"Failed to generate sprint retrospective: {e}")
        raise HTTPException(status_code=500, detail=str(e))
