import logging
import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket
from datetime import datetime

from database.models import Session, CaptureType
from database.db import get_db
from services.videodb_service import get_videodb
from services.claude_service import (
    extract_commitments,
    score_commitment_confidence,
    extract_decisions,
    verify_decision_drift,
    assess_commitment_gap
)
from manager import get_connection_manager
from sandbox_manager import get_sandbox_manager, create_session_sandbox

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Background task queue
_task_queue: asyncio.Queue = asyncio.Queue()


@router.post("/capture")
async def on_capture_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Webhook called by VideoDB when a capture session completes.
    
    Expected payload structure (based on corrected API):
    {
        "event": "capture.completed",
        "capture_session_id": "cap_xxx",
        "end_user_id": "user_xxx",
        "data": {
            "rtstreams": [
                {"id": "rts_xxx", "media_types": ["video", "audio"]},
                ...
            ]
        }
    }
    """
    try:
        capture_session_id = payload.get("capture_session_id")
        end_user_id = payload.get("end_user_id")
        data = payload.get("data", {})
        rtstreams = data.get("rtstreams", [])
        
        if not capture_session_id or not end_user_id:
            logger.error("Missing capture_session_id or end_user_id in webhook payload")
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        logger.info(f"Received webhook: capture_session_id={capture_session_id}, end_user_id={end_user_id}")
        
        # Determine capture type
        capture_type = CaptureType.SCREEN_RECORDING if rtstreams else CaptureType.TRANSCRIPT
        
        # Save session to database
        db = get_db()
        session_doc = {
            "session_id": f"sess_{capture_session_id}",
            "capture_session_id": capture_session_id,
            "capture_type": capture_type.value,
            "end_user_id": end_user_id,
            "rtstream_id": rtstreams[0]["id"] if rtstreams else None,
            "processed": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.sessions.insert_one(session_doc)
        session_id = result.inserted_id
        
        # Queue background processing
        background_tasks.add_task(
            _process_capture_session,
            session_id=str(session_id),
            capture_session_id=capture_session_id,
            end_user_id=end_user_id,
            rtstreams=rtstreams,
            capture_type=capture_type
        )
        
        logger.info(f"Queued processing for session: {session_id}")
        
        return {
            "status": "received",
            "session_id": str(session_id),
            "capture_session_id": capture_session_id
        }
    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcript")
async def on_transcript_chunk(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Alternative endpoint for transcript-only sessions.
    
    Expected payload:
    {
        "session_id": "sess_xxx",
        "end_user_id": "user_xxx",
        "transcript_chunk": {
            "timestamp": 0,
            "text": "meeting transcript",
            "speaker": "name"
        }
    }
    """
    try:
        session_id = payload.get("session_id")
        end_user_id = payload.get("end_user_id")
        transcript_chunk = payload.get("transcript_chunk")
        
        if not all([session_id, end_user_id, transcript_chunk]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Save to database
        db = get_db()
        
        # Create or update session
        await db.sessions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "end_user_id": end_user_id,
                    "capture_type": CaptureType.TRANSCRIPT.value,
                    "updated_at": datetime.utcnow()
                },
                "$push": {"transcript_chunks": transcript_chunk}
            },
            upsert=True
        )
        
        logger.info(f"Received transcript chunk for session: {session_id}")
        
        # Queue processing if we have a complete transcript
        if transcript_chunk.get("is_final"):
            background_tasks.add_task(
                _process_transcript_session,
                session_id=session_id,
                end_user_id=end_user_id
            )
        
        return {"status": "received"}
    
    except Exception as e:
        logger.error(f"Transcript webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _process_capture_session(
    session_id: str,
    capture_session_id: str,
    end_user_id: str,
    rtstreams: list,
    capture_type: CaptureType
):
    """Background task: process a capture session with sandbox-backed VLM indexing."""
    try:
        logger.info(f"Starting background processing for session: {session_id}")
        
        db = get_db()
        videodb = get_videodb()
        ws_manager = get_connection_manager()
        sandbox_manager = get_sandbox_manager()
        sandbox_id = None
        
        if capture_type == CaptureType.SCREEN_RECORDING and rtstreams:
            # Index visuals from screen recording using VLM
            rtstream_id = rtstreams[0]["id"]
            
            try:
                # Create sandbox for visual indexing
                logger.info(f"Creating sandbox for visual indexing of session {session_id}")
                sandbox_id = await create_session_sandbox()
                
                # Use advanced VLM indexing with sandbox compute
                logger.info(f"Indexing RTStream {rtstream_id} with VLM (sandbox: {sandbox_id})")
                
                visual_index_id = await videodb.index_rtstream_visuals_with_ai(
                    rtstream_id=rtstream_id,
                    prompt="Describe the screen content, active applications, user actions, and any visible decisions or commitments being executed. Note timestamps, window titles, and specific actions taken.",
                    model_name="GEMMA_4_31B",  # Best VLM for detailed visual understanding
                    sandbox_id=sandbox_id
                )
                
                # Convert indexed visuals to structured format
                indexed_visuals = await videodb._extract_visual_descriptions(visual_index_id, rtstream_id)
                
                # Store indexed visuals
                await db.sessions.update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "rtstream_id": rtstream_id,
                            "indexed_visuals": indexed_visuals,
                            "visual_index_id": visual_index_id,
                            "sandbox_id": sandbox_id
                        }
                    }
                )
                
                # Broadcast to dashboard
                await ws_manager.broadcast({
                    "type": "session_indexed",
                    "session_id": session_id,
                    "visual_count": len(indexed_visuals),
                    "method": "VLM-enhanced"
                })
                
                logger.info(f"Indexed {len(indexed_visuals)} visuals for session: {session_id} (VLM-enhanced)")
                
                # Stop sandbox after visual indexing completes
                if sandbox_id:
                    try:
                        await sandbox_manager.stop_sandbox(sandbox_id)
                        logger.info(f"Stopped sandbox {sandbox_id} after visual indexing")
                    except Exception as e:
                        logger.warning(f"Failed to stop sandbox {sandbox_id}: {e}")
            
            except Exception as e:
                logger.error(f"Failed to index visuals: {e}")
                
                # Stop sandbox on error
                if sandbox_id:
                    try:
                        await sandbox_manager.stop_sandbox(sandbox_id)
                    except:
                        pass
                
                # Try fallback to basic indexing
                try:
                    logger.info("Attempting fallback basic visual indexing")
                    indexed_visuals = await videodb.index_visuals(rtstream_id)
                    
                    await db.sessions.update_one(
                        {"session_id": session_id},
                        {
                            "$set": {
                                "rtstream_id": rtstream_id,
                                "indexed_visuals": indexed_visuals
                            }
                        }
                    )
                    
                    await ws_manager.broadcast({
                        "type": "session_indexed",
                        "session_id": session_id,
                        "visual_count": len(indexed_visuals),
                        "method": "basic"
                    })
                    
                    logger.info(f"Fallback indexing: {len(indexed_visuals)} visuals for session {session_id}")
                
                except Exception as fallback_error:
                    logger.error(f"Fallback visual indexing also failed: {fallback_error}")
                    await ws_manager.broadcast({
                        "type": "error",
                        "session_id": session_id,
                        "error": f"Visual indexing failed: {str(e)}"
                    })
        
        # Mark as processed
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"processed": True}}
        )
        
        logger.info(f"Completed background processing for session: {session_id}")
    
    except Exception as e:
        logger.error(f"Background processing error: {e}", exc_info=True)


async def _process_transcript_session(session_id: str, end_user_id: str):
    """Background task: process a transcript session."""
    try:
        logger.info(f"Starting transcript processing for session: {session_id}")
        
        db = get_db()
        ws_manager = get_connection_manager()
        
        # Get full transcript
        session = await db.sessions.find_one({"session_id": session_id})
        if not session:
            logger.error(f"Session not found: {session_id}")
            return
        
        transcript_chunks = session.get("transcript_chunks", [])
        transcript = " ".join([chunk.get("text", "") for chunk in transcript_chunks])
        
        # Extract commitments
        commitments_result = await extract_commitments(transcript)
        
        # Process each commitment
        for commitment in commitments_result.get("commitments", []):
            try:
                # Score confidence
                confidence_result = await score_commitment_confidence(
                    commitment["text"],
                    transcript
                )
                
                # Extract decisions
                decisions_result = await extract_decisions(
                    commitment["text"],
                    transcript
                )
                
                # Store commitment
                commitment_doc = {
                    "session_id": session_id,
                    "end_user_id": end_user_id,
                    "text": commitment["text"],
                    "confidence_score": confidence_result.get("confidence_score", 0.5),
                    "flagged_for_drift": False,
                    "created_at": datetime.utcnow()
                }
                
                comm_result = await db.commitments.insert_one(commitment_doc)
                commitment_id = comm_result.inserted_id
                
                # Store decisions
                for decision in decisions_result.get("decisions", []):
                    decision_doc = {
                        "session_id": session_id,
                        "commitment_id": str(commitment_id),
                        "end_user_id": end_user_id,
                        "text": decision["text"],
                        "watch_terms": decision.get("watch_terms", []),
                        "created_at": datetime.utcnow()
                    }
                    
                    await db.decisions.insert_one(decision_doc)
                
                # Broadcast commitment to dashboard
                await ws_manager.broadcast({
                    "type": "commitment_extracted",
                    "session_id": session_id,
                    "commitment_id": str(commitment_id),
                    "text": commitment["text"],
                    "confidence_score": confidence_result.get("confidence_score", 0.5),
                    "decision_count": len(decisions_result.get("decisions", []))
                })
            
            except Exception as e:
                logger.error(f"Failed to process commitment: {e}")
                continue
        
        # Mark session as processed
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"processed": True}}
        )
        
        logger.info(f"Completed transcript processing for session: {session_id}")
    
    except Exception as e:
        logger.error(f"Transcript processing error: {e}", exc_info=True)


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for dashboard real-time updates."""
    ws_manager = get_connection_manager()
    
    try:
        await ws_manager.connect(websocket)
        
        # Keep connection alive
        while True:
            # Listen for pings from client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        await ws_manager.disconnect(websocket)
