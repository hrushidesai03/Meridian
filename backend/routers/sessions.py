import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from datetime import datetime
from bson import ObjectId
import tempfile
import os
import base64
import pytesseract
from PIL import Image
import io

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

from database.models import CaptureType
from database.db import get_db
from services.videodb_service import get_videodb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/create")
async def create_session(request: Request):
    """Create a new capture session (generic endpoint for web client)."""
    try:
        body = await request.json()
        session_type = body.get("session_type", "meeting")
        end_user_id = body.get("end_user_id", "user_001")
        
        videodb = get_videodb()
        
        # Create VideoDB session - returns CaptureSession object
        result = await videodb.create_capture_session(
            end_user_id=end_user_id,
            capture_type=session_type,
            metadata={"type": session_type, "end_user_id": end_user_id}
        )
        
        logger.info(f"create_capture_session returned type: {type(result).__name__}, has id: {hasattr(result, 'id')}, has get: {hasattr(result, 'get')}")
        
        # Extract session ID - handle both dict and object responses
        session_id = None
        if isinstance(result, dict):
            session_id = result.get("capture_session_id")
        if session_id is None and hasattr(result, 'id'):
            session_id = result.id
        if session_id is None:
            session_id = str(result)
        
        # Generate client token
        token = await videodb.generate_client_token(expires_in=3600)
        
        logger.info(f"Created {session_type} session for {end_user_id}: {session_id}")
        
        return {
            "session_id": session_id,
            "client_token": token,
            "session_type": session_type
        }
    
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-transcript")
async def create_transcript_session(end_user_id: str):
    """Create a new transcript capture session."""
    try:
        videodb = get_videodb()
        
        # Create VideoDB session
        result = await videodb.create_capture_session(
            end_user_id=end_user_id,
            capture_type="transcript"
        )
        
        # Extract session ID - handle both dict and object responses
        capture_session_id = None
        if isinstance(result, dict):
            capture_session_id = result.get("capture_session_id")
        if capture_session_id is None and hasattr(result, 'id'):
            capture_session_id = result.id
        if capture_session_id is None:
            capture_session_id = str(result)
        
        # Generate client token for embedding
        client_token = await videodb.generate_client_token(expires_in=1800)
        
        logger.info(f"Created transcript session: {capture_session_id}")
        
        return {
            "capture_session_id": capture_session_id,
            "client_token": client_token,
            "capture_type": "transcript"
        }
    
    except Exception as e:
        logger.error(f"Failed to create transcript session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-screen")
async def create_screen_session(end_user_id: str):
    """Create a new screen recording capture session."""
    try:
        videodb = get_videodb()
        
        # Create VideoDB session
        result = await videodb.create_capture_session(
            end_user_id=end_user_id,
            capture_type="screen_recording"
        )
        
        # Extract session ID - handle both dict and object responses
        capture_session_id = None
        if isinstance(result, dict):
            capture_session_id = result.get("capture_session_id")
        if capture_session_id is None and hasattr(result, 'id'):
            capture_session_id = result.id
        if capture_session_id is None:
            capture_session_id = str(result)
        
        # Generate client token
        client_token = await videodb.generate_client_token(expires_in=1800)
        
        logger.info(f"Created screen session: {capture_session_id}")
        
        return {
            "capture_session_id": capture_session_id,
            "client_token": client_token,
            "capture_type": "screen_recording"
        }
    
    except Exception as e:
        logger.error(f"Failed to create screen session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    try:
        db = get_db()
        
        session = await db.sessions.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Convert ObjectId to string
        session["_id"] = str(session["_id"])
        
        return session
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{end_user_id}")
async def get_user_sessions(end_user_id: str, limit: int = 50):
    """Get all sessions for a user."""
    try:
        db = get_db()
        
        sessions = await db.sessions.find(
            {"end_user_id": end_user_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Convert ObjectIds
        for session in sessions:
            session["_id"] = str(session["_id"])
        
        return {"sessions": sessions, "count": len(sessions)}
    
    except Exception as e:
        logger.error(f"Failed to get user sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio-chunk")
async def receive_audio_chunk(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    end_user_id: str = Form(...),
    session_type: str = Form(default="meeting")
):
    """Receive audio chunk from browser, transcribe with Groq. Extract commitments ONLY for meeting sessions."""
    from groq import Groq
    from config import get_settings

    settings = get_settings()
    tmp_path = None
    
    try:
        # Validate inputs
        if not settings.groq_api_key:
            logger.error("Groq API key not configured")
            raise HTTPException(
                status_code=500,
                detail="Groq API key not configured"
            )
        
        # Save audio chunk temporarily
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
            content = await audio.read()
            if not content:
                logger.warning("Empty audio chunk received")
                return {"transcribed": "", "commitments_found": 0}
            tmp.write(content)
            tmp_path = tmp.name
        
        logger.info(f"Received audio chunk: {len(content)} bytes from {audio.filename}")
        
        # Skip very small chunks (less than 512 bytes is likely silence)
        if len(content) < 512:
            logger.info(f"Audio chunk too small ({len(content)} bytes), skipping transcription")
            return {"transcribed": "", "commitments_found": 0}

        # Transcribe with Groq Whisper
        try:
            client = Groq(api_key=settings.groq_api_key)
            with open(tmp_path, 'rb') as f:
                logger.info(f"Sending audio to Groq for transcription...")
                transcription = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("chunk.webm", f, "audio/webm"),
                    language="en"
                )
            
            text = transcription.text.strip()
            logger.info(f"Transcribed: {text[:100]}...")
            
            if not text or len(text.split()) < 3:
                return {"transcribed": "", "commitments_found": 0}

            logger.info(f"Processing meeting transcript: {text[:200]}")

            # ONLY extract commitments for meeting sessions
            db = get_db()
            commitments_found = 0
            
            if session_type.lower() == "meeting":
                try:
                    from services.claude_service import extract_commitments, extract_decisions
                    
                    # Extract commitments
                    logger.info(f"Extracting commitments from: {text[:150]}")
                    commitments_result = await extract_commitments(text)
                    logger.info(f"Commitments extraction result: {commitments_result}")
                    commitments = commitments_result.get("commitments", [])
                    logger.info(f"Found {len(commitments)} commitments")
                    
                    # Insert commitments directly (skip scoring to avoid rate limits)
                    for c in commitments:
                        logger.info(f"Saving commitment: {c.get('text')}")
                        try:
                            await db.commitments.insert_one({
                                "session_id": session_id,
                                "end_user_id": end_user_id,
                                "text": c.get("text",""),
                                "confidence_score": 0.8,  # Default confidence
                                "risk_factors": [],
                                "flagged_for_drift": False,
                                "created_at": datetime.utcnow()
                            })
                            logger.info(f"✅ Saved commitment to database")
                        except Exception as e:
                            logger.error(f"Failed to insert commitment: {e}")
                    
                    # Also extract decisions for meetings
                    try:
                        decisions_result = await extract_decisions(text, text)
                        for d in decisions_result.get("decisions", []):
                            await db.decisions.insert_one({
                                "session_id": session_id,
                                "end_user_id": end_user_id,
                                "text": d.get("text",""),
                                "watch_terms": d.get("watch_terms", []),
                                "category": d.get("category", "general"),
                                "created_at": datetime.utcnow()
                            })
                        logger.info(f"Meeting session: Extracted {len(commitments)} commitments and {len(decisions_result.get('decisions', []))} decisions")
                    except Exception as e:
                        logger.warning(f"Decision extraction failed (non-critical): {e}")
                    
                    commitments_found = len(commitments)
                except Exception as e:
                    logger.error(f"Commitment extraction failed: {e}", exc_info=True)
                    # Continue anyway - commitments extraction is not critical
            else:
                logger.info(f"Work session: Skipping commitment extraction (audio is only for context, not analysis)")

            return {
                "transcribed": text,
                "commitments_found": commitments_found
            }
        
        except Exception as e:
            logger.warning(f"Groq transcription failed (skipping chunk): {e}")
            # Return empty result instead of failing - the chunk might just be noise
            return {
                "transcribed": "",
                "commitments_found": 0,
                "warning": "Transcription failed for this chunk"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio chunk processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Audio processing failed: {str(e)[:100]}"
        )
    
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


@router.post("/screen-frame")
async def receive_screen_frame(
    image: UploadFile = File(...),
    session_id: str = Form(...),
    end_user_id: str = Form(...)
):
    db = get_db()
    
    # Read image
    image_bytes = await image.read()
    
    # Extract text using Tesseract OCR
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        extracted_text = pytesseract.image_to_string(pil_image)
        extracted_text_lower = extracted_text.lower()
        print(f"[OCR] Extracted text: {extracted_text[:300]}")
    except Exception as e:
        print(f"[OCR] Failed: {e}")
        return {"drift_detected": False, "error": str(e)}

    if not extracted_text.strip():
        return {"drift_detected": False, "description": "no text found"}

    # Check against all decisions
    decisions = await db.decisions.find(
        {"end_user_id": end_user_id}
    ).to_list(50)

    for decision in decisions:
        decision_text_lower = decision.get("text", "").lower()
        
        # Build contradiction keywords from decision text
        contradiction_keywords = []
        
        if "mongodb" in decision_text_lower:
            contradiction_keywords.extend(["mongodb", "mongoose", "mongo"])
        if "mysql" in decision_text_lower:
            contradiction_keywords.extend(["mysql", "pymysql"])
        if "react" in decision_text_lower:
            contradiction_keywords.extend(["vue", "angular", "svelte"])
        if "postgres" in decision_text_lower or "postgresql" in decision_text_lower:
            contradiction_keywords.extend(["mongodb", "mongoose", "mysql"])
        if "rest" in decision_text_lower:
            contradiction_keywords.extend(["graphql"])
            
        # Also use stored contradiction_terms
        stored = [t.lower() for t in decision.get(
            "contradiction_terms", []
        )]
        contradiction_keywords.extend(stored)
        contradiction_keywords = list(set(contradiction_keywords))

        # Check if any contradiction appears in OCR text
        matched = [
            t for t in contradiction_keywords 
            if t in extracted_text_lower
        ]

        if matched:
            # Check if alert already exists
            existing = await db.alerts.find_one({
                "end_user_id": end_user_id,
                "decision_id": str(decision["_id"]),
                "resolved": False
            })

            if not existing:
                await db.alerts.insert_one({
                    "alert_type": "drift",
                    "end_user_id": end_user_id,
                    "session_id": session_id,
                    "decision_id": str(decision["_id"]),
                    "drift_description": (
                        f"'{matched[0]}' detected on screen — "
                        f"decision was: {decision.get('text', '')}"
                    ),
                    "drift_evidence": (
                        f"OCR detected: {', '.join(matched)}"
                    ),
                    "severity": "high",
                    "resolved": False,
                    "created_at": datetime.utcnow()
                })
                print(f"[DRIFT] Alert created for: {matched}")

            return {
                "drift_detected": True,
                "drift_description": f"Drift: {matched[0]} detected",
                "matched_terms": matched,
                "description": extracted_text[:200]
            }

    return {
        "drift_detected": False,
        "description": extracted_text[:200]
    }
