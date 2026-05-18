"""
VideoDB Webhook Handlers for Real-Time Event Processing

This module handles all incoming webhooks from VideoDB:
- capture.completed - Screen recording capture finished
- rtstream.ready - Real-time stream ready for indexing
- transcript.chunk - Transcript chunk received

These events trigger the full pipeline:
commitment extraction → decision extraction → drift detection
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from bson import ObjectId

from database.db import get_db
from database.models import Session, CaptureType
from agents.orchestration import CommitmentAgent, DecisionAgent, DriftDetector
from services.videodb_service import get_videodb
from manager import get_connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/videodb", tags=["videodb-webhooks"])


@router.post("/capture-completed")
async def on_capture_completed(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """
    Handle VideoDB capture completion webhook.
    
    Payload structure:
    {
        "event": "capture.completed",
        "capture_session_id": "cap_xyz",
        "end_user_id": "user_123",
        "capture_type": "screen_recording" | "transcript",
        "rtstream_id": "rts_xyz",
        "metadata": {...}
    }
    """
    try:
        capture_session_id = payload.get("capture_session_id")
        end_user_id = payload.get("end_user_id")
        capture_type = payload.get("capture_type", "screen_recording")
        rtstream_id = payload.get("rtstream_id")
        metadata = payload.get("metadata", {})
        
        if not capture_session_id or not end_user_id:
            logger.error("Missing required fields in capture webhook")
            raise HTTPException(status_code=400, detail="Missing capture_session_id or end_user_id")
        
        logger.info(f"Received capture.completed event: {capture_session_id} from {end_user_id}")
        
        db = get_db()
        ws_manager = get_connection_manager()
        
        # Create session record
        session_doc = {
            "session_id": f"sess_{capture_session_id}",
            "capture_session_id": capture_session_id,
            "capture_type": capture_type,
            "end_user_id": end_user_id,
            "rtstream_id": rtstream_id,
            "metadata": metadata,
            "processed": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.sessions.insert_one(session_doc)
        session_id = str(result.inserted_id)
        
        logger.info(f"Created session record: {session_id}")
        
        # Queue background processing
        background_tasks.add_task(
            _process_capture_session,
            session_id=session_id,
            capture_session_id=capture_session_id,
            end_user_id=end_user_id,
            rtstream_id=rtstream_id,
            capture_type=capture_type
        )
        
        # Broadcast to dashboard
        await ws_manager.broadcast({
            "type": "capture_received",
            "session_id": session_id,
            "capture_session_id": capture_session_id
        })
        
        return {
            "status": "received",
            "session_id": session_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Capture webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rtstream-ready")
async def on_rtstream_ready(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """
    Handle RTStream ready event (screen recording ready for processing).
    
    Payload structure:
    {
        "event": "rtstream.ready",
        "rtstream_id": "rts_xyz",
        "capture_session_id": "cap_xyz",
        "duration": 3600,
        "media_types": ["video", "audio"]
    }
    """
    try:
        rtstream_id = payload.get("rtstream_id")
        capture_session_id = payload.get("capture_session_id")
        
        if not rtstream_id:
            logger.error("Missing rtstream_id in rtstream.ready webhook")
            raise HTTPException(status_code=400, detail="Missing rtstream_id")
        
        logger.info(f"RTStream ready: {rtstream_id} from capture {capture_session_id}")
        
        db = get_db()
        
        # Find session by capture_session_id
        session = await db.sessions.find_one({"capture_session_id": capture_session_id})
        
        if not session:
            logger.warning(f"Session not found for capture {capture_session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Update session with RTStream info
        await db.sessions.update_one(
            {"_id": session["_id"]},
            {"$set": {
                "rtstream_id": rtstream_id,
                "updated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"Updated session {session['_id']} with RTStream {rtstream_id}")
        
        # Queue visual indexing
        background_tasks.add_task(
            _index_rtstream_visuals,
            session_id=str(session["_id"]),
            rtstream_id=rtstream_id,
            end_user_id=session["end_user_id"]
        )
        
        return {
            "status": "rtstream_acknowledged",
            "rtstream_id": rtstream_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RTStream ready webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcript-chunk")
async def on_transcript_chunk(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """
    Handle transcript chunk received event.
    
    Payload structure:
    {
        "event": "transcript.chunk",
        "capture_session_id": "cap_xyz",
        "end_user_id": "user_123",
        "chunk": {
            "text": "We will launch by Friday",
            "speaker": "Alice",
            "timestamp": 120,
            "is_final": false
        }
    }
    """
    try:
        capture_session_id = payload.get("capture_session_id")
        end_user_id = payload.get("end_user_id")
        chunk = payload.get("chunk", {})
        
        if not capture_session_id or not end_user_id:
            logger.error("Missing required fields in transcript.chunk webhook")
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        logger.info(f"Received transcript chunk from {capture_session_id}: {chunk.get('text', '')[:50]}...")
        
        db = get_db()
        ws_manager = get_connection_manager()
        
        # Find or create session
        session = await db.sessions.find_one({"capture_session_id": capture_session_id})
        
        if not session:
            # Create new session for transcript
            session_doc = {
                "session_id": f"sess_{capture_session_id}",
                "capture_session_id": capture_session_id,
                "capture_type": CaptureType.TRANSCRIPT.value,
                "end_user_id": end_user_id,
                "metadata": {},
                "processed": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "transcript_chunks": []
            }
            result = await db.sessions.insert_one(session_doc)
            session_id = str(result.inserted_id)
            logger.info(f"Created new transcript session: {session_id}")
        else:
            session_id = str(session["_id"])
        
        # Add chunk to session
        await db.sessions.update_one(
            {"_id": session["_id"]},
            {"$push": {"transcript_chunks": chunk}}
        )
        
        logger.info(f"Stored transcript chunk in session {session_id}")
        
        # If this is the final chunk, process the complete transcript
        if chunk.get("is_final"):
            logger.info(f"Final transcript chunk received for session {session_id}, queueing processing")
            
            background_tasks.add_task(
                _process_complete_transcript,
                session_id=session_id,
                capture_session_id=capture_session_id,
                end_user_id=end_user_id
            )
        
        # Broadcast chunk received
        await ws_manager.broadcast({
            "type": "transcript_chunk",
            "session_id": session_id,
            "text_preview": chunk.get("text", "")[:100],
            "is_final": chunk.get("is_final", False)
        })
        
        return {
            "status": "chunk_received",
            "session_id": session_id,
            "is_final": chunk.get("is_final", False)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcript chunk webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ BACKGROUND TASK HANDLERS ============


async def _process_capture_session(
    session_id: str,
    capture_session_id: str,
    end_user_id: str,
    rtstream_id: Optional[str],
    capture_type: str
):
    """
    Background task: Process completed capture session.
    Triggers visual indexing for screen recordings.
    """
    try:
        logger.info(f"Processing capture session: {session_id}")
        
        db = get_db()
        ws_manager = get_connection_manager()
        
        # Get session for update
        session = await db.sessions.find_one({"_id": ObjectId(session_id)})
        if not session:
            logger.error(f"Session not found: {session_id}")
            return
        
        # Screen recording: index visuals
        if capture_type == "screen_recording" and rtstream_id:
            logger.info(f"Processing screen recording with RTStream: {rtstream_id}")
            
            await _index_rtstream_visuals(
                session_id=session_id,
                rtstream_id=rtstream_id,
                end_user_id=end_user_id
            )
        
        # Mark session as processed
        await db.sessions.update_one(
            {"_id": session["_id"]},
            {"$set": {"processed": True}}
        )
        
        logger.info(f"Completed processing for session: {session_id}")
    
    except Exception as e:
        logger.error(f"Error processing capture session {session_id}: {e}", exc_info=True)


async def _index_rtstream_visuals(
    session_id: str,
    rtstream_id: str,
    end_user_id: str
):
    """
    Background task: Index visual content from RTStream.
    Calls VideoDB to analyze screen recording.
    """
    try:
        logger.info(f"Indexing visuals for RTStream: {rtstream_id}")
        
        db = get_db()
        videodb = get_videodb()
        ws_manager = get_connection_manager()
        
        # Index visuals (basic indexing)
        try:
            indexed_visuals = await videodb.index_visuals(rtstream_id)
            
            # Store visual index
            await db.sessions.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {
                    "indexed_visuals": indexed_visuals,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            logger.info(f"Indexed {len(indexed_visuals)} visuals for RTStream {rtstream_id}")
            
            # Broadcast indexing complete
            await ws_manager.broadcast({
                "type": "visuals_indexed",
                "session_id": session_id,
                "count": len(indexed_visuals)
            })
        
        except Exception as e:
            logger.warning(f"Visual indexing failed (non-blocking): {e}")
            await ws_manager.broadcast({
                "type": "indexing_failed",
                "session_id": session_id,
                "error": str(e)
            })
    
    except Exception as e:
        logger.error(f"Error indexing visuals for RTStream {rtstream_id}: {e}", exc_info=True)


async def _process_complete_transcript(
    session_id: str,
    capture_session_id: str,
    end_user_id: str
):
    """
    Background task: Process complete transcript.
    Extracts commitments, decisions, triggers drift detection.
    """
    try:
        logger.info(f"Processing complete transcript for session: {session_id}")
        
        db = get_db()
        ws_manager = get_connection_manager()
        
        # Get session
        from bson import ObjectId
        session = await db.sessions.find_one({"_id": ObjectId(session_id)})
        
        if not session:
            logger.error(f"Session not found: {session_id}")
            return
        
        # Combine transcript chunks into full transcript
        transcript_chunks = session.get("transcript_chunks", [])
        full_transcript = " ".join([chunk.get("text", "") for chunk in transcript_chunks])
        
        logger.info(f"Full transcript ({len(full_transcript)} chars) ready for processing")
        
        # Step 1: Extract commitments with confidence scores
        commitments = await CommitmentAgent.process_transcript(
            transcript=full_transcript,
            session_id=session_id,
            end_user_id=end_user_id
        )
        
        logger.info(f"Extracted {len(commitments)} commitments")
        
        # Broadcast commitments
        for commitment in commitments:
            await ws_manager.broadcast({
                "type": "commitment_extracted",
                "session_id": session_id,
                "commitment_id": str(commitment["_id"]),
                "text": commitment["text"],
                "confidence_score": commitment.get("confidence_score", 0)
            })
        
        # Step 2: Extract decisions for each commitment
        for commitment in commitments:
            try:
                decisions = await DecisionAgent.extract_from_commitment(
                    commitment_id=str(commitment["_id"]),
                    commitment_text=commitment["text"],
                    session_id=session_id,
                    end_user_id=end_user_id,
                    transcript_context=full_transcript
                )
                
                logger.info(f"Extracted {len(decisions)} decisions for commitment {commitment['_id']}")
                
                # Broadcast decisions
                for decision in decisions:
                    await ws_manager.broadcast({
                        "type": "decision_extracted",
                        "session_id": session_id,
                        "decision_id": str(decision["_id"]),
                        "text": decision["text"],
                        "watch_terms": decision.get("watch_terms", [])
                    })
            
            except Exception as e:
                logger.error(f"Decision extraction failed for commitment {commitment['_id']}: {e}")
                continue
        
        # Mark session as processed
        await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"processed": True}}
        )
        
        # Broadcast processing complete
        await ws_manager.broadcast({
            "type": "transcript_processed",
            "session_id": session_id,
            "commitment_count": len(commitments)
        })
        
        logger.info(f"Completed transcript processing for session: {session_id}")
    
    except Exception as e:
        logger.error(f"Error processing complete transcript {session_id}: {e}", exc_info=True)
