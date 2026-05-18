import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId

from database.models import AlertType
from database.db import get_db
from services.videodb_service import get_videodb
from services.claude_service import generate_receipt_narrative
from manager import get_connection_manager
from sandbox_manager import get_sandbox_manager, create_session_sandbox
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def get_alerts(end_user_id: str = "user_001"):
    """Get all alerts for a user."""
    db = get_db()
    docs = await db.alerts.find(
        {"end_user_id": end_user_id}
    ).sort("created_at", -1).to_list(100)
    for d in docs:
        d["_id"] = str(d["_id"])
        if "session_id" in d and d["session_id"]:
            d["session_id"] = str(d["session_id"])
        if "decision_id" in d and d["decision_id"]:
            d["decision_id"] = str(d["decision_id"])
    return {"alerts": docs, "count": len(docs)}


@router.get("/{alert_id}")
async def get_alert(alert_id: str):
    """Get alert details."""
    try:
        db = get_db()
        
        alert = await db.alerts.find_one({"_id": ObjectId(alert_id)})
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        alert["_id"] = str(alert["_id"])
        return alert
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{end_user_id}")
async def get_user_alerts(
    end_user_id: str,
    alert_type: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 50
):
    """Get alerts for a user, optionally filtered by type or resolution status."""
    try:
        db = get_db()
        
        query = {"end_user_id": end_user_id}
        
        if alert_type:
            query["alert_type"] = alert_type
        
        if resolved is not None:
            query["resolved"] = resolved
        
        alerts = await db.alerts.find(query).sort("created_at", -1).limit(limit).to_list(limit)
        
        for alert in alerts:
            alert["_id"] = str(alert["_id"])
        
        return {
            "end_user_id": end_user_id,
            "alerts": alerts,
            "count": len(alerts)
        }
    
    except Exception as e:
        logger.error(f"Failed to get user alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/generate-receipt")
async def generate_receipt_video(alert_id: str, use_ai: bool = True):
    """
    Generate accountability receipt video for a drift/gap alert.
    
    With use_ai=True (default): Uses sandbox compute for OmniVoice narration + FLUX imagery
    With use_ai=False: Basic receipt without AI generation
    """
    try:
        db = get_db()
        videodb = get_videodb()
        ws_manager = get_connection_manager()
        
        # Get alert
        alert = await db.alerts.find_one({"_id": ObjectId(alert_id)})
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Get commitment and decision for context
        commitment = None
        decision = None
        
        if alert.get("commitment_id"):
            commitment = await db.commitments.find_one(
                {"commitment_id": alert["commitment_id"]}
            )
        
        if alert.get("decision_id"):
            decision = await db.decisions.find_one(
                {"decision_id": alert["decision_id"]}
            )
        
        # Generate narrative
        commitment_text = commitment["text"] if commitment else "N/A"
        decision_text = decision["text"] if decision else "N/A"
        gap_or_drift = alert["alert_type"]
        evidence = alert.get("drift_evidence") or alert.get("gap_description", "No details")
        
        narrative_result = await generate_receipt_narrative(
            commitment_text=commitment_text,
            decision_text=decision_text,
            gap_or_drift=gap_or_drift,
            evidence=evidence
        )
        
        # Build clip specs for video
        clip_specs = []
        sandbox_id = None
        
        if alert.get("visual_index") is not None and decision and decision.get("watch_terms"):
            # Get the RTStream from session
            session = await db.sessions.find_one({"session_id": decision["session_id"]})
            
            if session and session.get("rtstream_id"):
                clip_specs.append({
                    "rtstream_id": session["rtstream_id"],
                    "start_time": alert.get("visual_index", 0) * 5,  # Approximate timing
                    "end_time": (alert.get("visual_index", 0) + 1) * 5,
                    "annotation": evidence[:100]  # First 100 chars of evidence
                })
        
        # Prepare AI assets if requested
        narration_audio = None
        background_image = None
        
        if use_ai and clip_specs:
            try:
                # Create sandbox for AI generation
                logger.info(f"Creating sandbox for receipt generation")
                sandbox_manager = get_sandbox_manager()
                sandbox_id = await create_session_sandbox()
                
                logger.info(f"Sandbox {sandbox_id} ready, generating AI assets")
                
                # Generate narration using OmniVoice
                narration_audio = await videodb.generate_narration(
                    text=narrative_result.get("narration", "Watch this accountability evidence."),
                    voice_config={
                        "instructions": "professional, clear, authoritative, slightly concerned",
                        "response_format": "wav",
                        "speed": 1.0
                    },
                    sandbox_id=sandbox_id
                )
                
                logger.info(f"Generated narration audio: {narration_audio['audio_id']}")
                
                # Generate background imagery using FLUX
                image_prompt = f"Professional corporate background for {gap_or_drift} accountability report. Clean, modern, formal."
                
                background_image = await videodb.generate_image(
                    prompt=image_prompt,
                    image_config={
                        "size": "1280x720",
                        "num_inference_steps": 28,
                        "guidance_scale": 4.0
                    },
                    sandbox_id=sandbox_id
                )
                
                logger.info(f"Generated background image: {background_image['image_id']}")
                
                # Stop sandbox to conserve credits
                await sandbox_manager.stop_sandbox(sandbox_id)
                logger.info(f"Stopped sandbox {sandbox_id}")
                
            except Exception as e:
                logger.warning(f"Failed to generate AI assets, continuing without: {e}")
                if sandbox_id:
                    try:
                        sandbox_manager = get_sandbox_manager()
                        await sandbox_manager.stop_sandbox(sandbox_id)
                    except:
                        pass
        
        # Generate receipt video with or without AI assets
        video_id = None
        video_url = None
        
        if clip_specs:
            try:
                if narration_audio:
                    # Premium receipt with AI narration
                    video_id = await videodb.build_receipt_video_with_assets(
                        clip_specs=clip_specs,
                        narration_text=narrative_result.get("narration"),
                        background_image_id=background_image.get("image_id") if background_image else None,
                        title=narrative_result.get("title", "Accountability Receipt"),
                        sandbox_id=sandbox_id
                    )
                else:
                    # Basic receipt without narration
                    video_id = await videodb.build_receipt_video(
                        clip_specs=clip_specs,
                        title=narrative_result.get("title", "Accountability Receipt")
                    )
                
                video_url = await videodb.get_video_url(video_id)
                
                # Update alert with receipt
                await db.alerts.update_one(
                    {"_id": ObjectId(alert_id)},
                    {
                        "$set": {
                            "receipt_video_id": video_id,
                            "receipt_video_url": video_url,
                            "receipt_audio_id": narration_audio.get("audio_id") if narration_audio else None,
                            "receipt_image_id": background_image.get("image_id") if background_image else None,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                logger.info(f"Generated receipt video {video_id} for alert {alert_id}")
                
                # Broadcast update
                await ws_manager.broadcast({
                    "type": "receipt_generated",
                    "alert_id": alert_id,
                    "video_id": video_id,
                    "video_url": video_url,
                    "has_narration": bool(narration_audio),
                    "has_imagery": bool(background_image)
                })
                
                return {
                    "alert_id": alert_id,
                    "video_id": video_id,
                    "video_url": video_url,
                    "narrative": narrative_result,
                    "ai_assets": {
                        "narration_id": narration_audio.get("audio_id") if narration_audio else None,
                        "image_id": background_image.get("image_id") if background_image else None
                    }
                }
            
            except Exception as e:
                logger.warning(f"Failed to generate video, returning narrative only: {e}")
        
        # Return narrative even if video generation fails
        return {
            "alert_id": alert_id,
            "video_id": None,
            "narrative": narrative_result,
            "ai_assets": {}
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate receipt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, resolved: bool = True):
    """Mark alert as resolved."""
    try:
        db = get_db()
        
        result = await db.alerts.update_one(
            {"_id": ObjectId(alert_id)},
            {
                "$set": {
                    "resolved": resolved,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "alert_id": alert_id,
            "resolved": resolved,
            "updated": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert."""
    try:
        db = get_db()
        
        result = await db.alerts.delete_one({"_id": ObjectId(alert_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "alert_id": alert_id,
            "deleted": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/receipt")
async def generate_receipt(alert_id: str):
    """Generate accountability receipt for an alert."""
    try:
        from agents.orchestration import RetrospectiveAgent
        result = await RetrospectiveAgent.generate_receipt(alert_id)
        return result or {"error": "Receipt generation failed"}
    except Exception as e:
        logger.error(f"Failed to generate receipt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
