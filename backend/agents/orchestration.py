"""
Hr 6-14 Build: Agent Modules for Orchestration

This layer sits above individual Claude calls and coordinates the full logic flow:
1. commitment_agent - orchestrates extraction + confidence scoring
2. decision_agent - handles decision extraction + watch_terms prep
3. gap_agent - detects when commitments aren't being executed
4. drift_agent - orchestrates drift detection on screen observations
5. retrospective_agent - generates accountability narratives + receipts
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId

from database.db import get_db
from services.claude_service import (
    extract_commitments,
    score_commitment_confidence,
    extract_decisions,
    verify_decision_drift,
    assess_commitment_gap
)

logger = logging.getLogger(__name__)


class CommitmentAgent:
    """Orchestrates commitment extraction and confidence scoring."""
    
    @staticmethod
    async def process_transcript(transcript: str, session_id: str, end_user_id: str) -> List[Dict[str, Any]]:
        """
        Extract commitments from transcript with confidence scores.
        
        Returns:
            List of commitment dicts with full metadata
        """
        db = get_db()
        
        logger.info(f"CommitmentAgent: Processing transcript from session {session_id}")
        
        # Extract commitments
        extract_result = await extract_commitments(transcript)
        commitments_list = extract_result.get("commitments", [])
        
        processed_commitments = []
        
        for commitment in commitments_list:
            try:
                # Score confidence
                confidence_result = await score_commitment_confidence(
                    commitment["text"],
                    transcript
                )
                
                commitment_doc = {
                    "session_id": session_id,
                    "end_user_id": end_user_id,
                    "text": commitment["text"],
                    "confidence_score": confidence_result.get("confidence_score", 0.5),
                    "flagged_for_drift": False,
                    "risk_factors": confidence_result.get("risk_factors", []),
                    "created_at": datetime.utcnow()
                }
                
                # Store in database
                result = await db.commitments.insert_one(commitment_doc)
                commitment_doc["_id"] = str(result.inserted_id)
                commitment_doc["commitment_id"] = str(result.inserted_id)
                
                processed_commitments.append(commitment_doc)
                
                logger.info(f"CommitmentAgent: Stored commitment {result.inserted_id} with confidence {confidence_result.get('confidence_score', 0)}")
            
            except Exception as e:
                logger.error(f"CommitmentAgent: Failed to process commitment: {e}")
                continue
        
        return processed_commitments


class DecisionAgent:
    """Orchestrates decision extraction and watch_terms preparation."""
    
    @staticmethod
    async def extract_from_commitment(
        commitment_id: str,
        commitment_text: str,
        session_id: str,
        end_user_id: str,
        transcript_context: str
    ) -> List[Dict[str, Any]]:
        """
        Extract decisions from a commitment.
        
        Returns:
            List of decision dicts with watch_terms
        """
        db = get_db()
        
        logger.info(f"DecisionAgent: Extracting decisions for commitment {commitment_id}")
        
        # Extract decisions
        decisions_result = await extract_decisions(commitment_text, transcript_context)
        decisions_list = decisions_result.get("decisions", [])
        
        stored_decisions = []
        
        for decision in decisions_list:
            try:
                decision_doc = {
                    "session_id": session_id,
                    "commitment_id": commitment_id,
                    "end_user_id": end_user_id,
                    "text": decision["text"],
                    "watch_terms": decision.get("watch_terms", []),
                    "category": decision.get("category", "general"),
                    "created_at": datetime.utcnow()
                }
                
                # Store in database
                result = await db.decisions.insert_one(decision_doc)
                decision_doc["_id"] = str(result.inserted_id)
                decision_doc["decision_id"] = str(result.inserted_id)
                
                stored_decisions.append(decision_doc)
                
                logger.info(f"DecisionAgent: Stored decision {result.inserted_id} with watch_terms {decision.get('watch_terms', [])}")
            
            except Exception as e:
                logger.error(f"DecisionAgent: Failed to store decision: {e}")
                continue
        
        return stored_decisions


class GapDetector:
    """Detects when commitments aren't being executed (gaps)."""
    
    @staticmethod
    async def check_commitment_gaps(
        end_user_id: str,
        current_date: str,
        commitment_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for commitment execution gaps.
        
        Returns:
            List of alerts for detected gaps
        """
        db = get_db()
        
        logger.info(f"GapDetector: Checking gaps for user {end_user_id}")
        
        # Get commitments to check
        query = {"end_user_id": end_user_id}
        if commitment_ids:
            try:
                query["_id"] = {"$in": [ObjectId(cid) for cid in commitment_ids]}
            except:
                # If commitment_ids are not valid ObjectIds, skip filtering
                pass
        
        commitments = await db.commitments.find(query).to_list(None)
        
        gap_alerts = []
        
        for commitment in commitments:
            try:
                # Assess gap
                gap_result = await assess_commitment_gap(
                    commitment["text"],
                    "from commitment creation time",
                    current_date,
                    ""
                )
                
                if gap_result.get("gap_exists"):
                    # Create alert
                    alert_doc = {
                        "alert_type": "gap",
                        "commitment_id": str(commitment["_id"]),
                        "end_user_id": end_user_id,
                        "gap_description": gap_result.get("gap_description"),
                        "severity": gap_result.get("severity", "medium"),
                        "created_at": datetime.utcnow(),
                        "resolved": False
                    }
                    
                    result = await db.alerts.insert_one(alert_doc)
                    alert_doc["_id"] = str(result.inserted_id)
                    alert_doc["alert_id"] = str(result.inserted_id)
                    
                    gap_alerts.append(alert_doc)
                    
                    logger.info(f"GapDetector: Created gap alert {result.inserted_id} for commitment {commitment['_id']}")
            
            except Exception as e:
                logger.error(f"GapDetector: Failed to check commitment {commitment['_id']}: {e}")
                continue
        
        return gap_alerts


class DriftDetector:
    """Detects when implemented decisions drift from stated decisions."""
    
    @staticmethod
    async def check_for_drifts(
        end_user_id: str,
        indexed_visuals: List[Dict[str, Any]],
        rtstream_session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Monitor screen observations for decision drift.
        
        Args:
            end_user_id: User to check
            indexed_visuals: List of visual observations from screen recording
            rtstream_session_id: Session ID with RTStream data
        
        Returns:
            List of drift alerts created
        """
        db = get_db()
        
        logger.info(f"DriftDetector: Checking drifts for user {end_user_id} across {len(indexed_visuals)} visuals")
        
        # Get all flagged decisions for user
        decisions = await db.decisions.find({
            "end_user_id": end_user_id
        }).to_list(None)
        
        drift_alerts = []
        
        for decision in decisions:
            watch_terms = decision.get("watch_terms", [])
            if not watch_terms:
                continue
            
            # Check each visual against watch_terms
            for visual in indexed_visuals:
                visual_description = visual.get("description", "")
                visual_index = visual.get("visual_index")
                
                try:
                    # Verify drift
                    drift_result = await verify_decision_drift(
                        decision_text=decision["text"],
                        watch_terms=watch_terms,
                        screen_observation=visual_description
                    )
                    
                    if drift_result.get("drift_detected"):
                        # Create alert
                        alert_doc = {
                            "alert_type": "drift",
                            "commitment_id": decision.get("commitment_id"),
                            "decision_id": str(decision["_id"]),
                            "end_user_id": end_user_id,
                            "drift_description": drift_result.get("drift_description"),
                            "drift_evidence": drift_result.get("evidence"),
                            "visual_index": visual_index,
                            "severity": drift_result.get("severity", "medium"),
                            "created_at": datetime.utcnow(),
                            "resolved": False
                        }
                        
                        result = await db.alerts.insert_one(alert_doc)
                        alert_doc["_id"] = str(result.inserted_id)
                        alert_doc["alert_id"] = str(result.inserted_id)
                        
                        drift_alerts.append(alert_doc)
                        
                        logger.info(f"DriftDetector: Created drift alert {result.inserted_id} for decision {decision['_id']}")
                        break  # Move to next decision after finding first drift
                
                except Exception as e:
                    logger.error(f"DriftDetector: Failed to check visual {visual_index}: {e}")
                    continue
        
        return drift_alerts


class RetrospectiveAgent:
    """Generates accountability narratives and receipt videos."""
    
    @staticmethod
    async def generate_receipt(alert_id: str) -> Dict[str, Any]:
        """
        Generate accountability receipt for an alert.
        
        Returns:
            Receipt metadata with narrative and video details
        """
        from services.videodb_service import get_videodb
        from services.claude_service import generate_receipt_narrative
        
        db = get_db()
        videodb = get_videodb()
        
        logger.info(f"RetrospectiveAgent: Generating receipt for alert {alert_id}")
        
        try:
            # Get alert with linked data
            from bson import ObjectId
            alert = await db.alerts.find_one({"_id": ObjectId(alert_id)})
            if not alert:
                logger.error(f"RetrospectiveAgent: Alert not found {alert_id}")
                return None
            
            commitment = None
            if alert.get("commitment_id"):
                commitment = await db.commitments.find_one(
                    {"_id": ObjectId(alert["commitment_id"])}
                )
            
            decision = None
            if alert.get("decision_id"):
                decision = await db.decisions.find_one(
                    {"_id": ObjectId(alert["decision_id"])}
                )
            
            # Generate narrative
            narrative = await generate_receipt_narrative(
                commitment_text=commitment["text"] if commitment else "Unknown",
                decision_text=decision["text"] if decision else "Unknown",
                gap_or_drift=alert["alert_type"],
                evidence=alert.get("drift_evidence") or alert.get("gap_description", "")
            )
            
            # Try to build video if we have screen recording reference
            video_id = None
            video_url = None
            
            if alert.get("visual_index") and decision and decision.get("watch_terms"):
                # Look up session by session_id or _id
                session = await db.sessions.find_one({
                    "$or": [
                        {"session_id": decision.get("session_id")},
                        {"_id": ObjectId(decision["session_id"])} if isinstance(decision.get("session_id"), str) and len(decision.get("session_id", "")) == 24 else None
                    ]
                })
                
                if not session:
                    # Try with session_id field
                    session = await db.sessions.find_one({"session_id": decision.get("session_id")})
                
                if session and session.get("rtstream_id"):
                    try:
                        clip_specs = [{
                            "rtstream_id": session["rtstream_id"],
                            "start_time": alert.get("visual_index", 0) * 5,
                            "end_time": (alert.get("visual_index", 0) + 1) * 5,
                            "annotation": (alert.get("drift_evidence") or "Evidence")[:100]
                        }]
                        
                        video_id = await videodb.build_receipt_video(
                            clip_specs=clip_specs,
                            title=narrative.get("title", "Accountability Receipt")
                        )
                        
                        video_url = await videodb.get_video_url(video_id)
                        
                        logger.info(f"RetrospectiveAgent: Generated video {video_id}")
                    
                    except Exception as e:
                        logger.warning(f"RetrospectiveAgent: Video generation failed, continuing with narrative only: {e}")
            
            # Update alert with receipt metadata
            receipt = {
                "video_id": video_id,
                "video_url": video_url,
                "narrative": narrative,
                "generated_at": datetime.utcnow()
            }
            
            await db.alerts.update_one(
                {"_id": ObjectId(alert_id)},
                {"$set": {"receipt": receipt}}
            )
            
            logger.info(f"RetrospectiveAgent: Receipt generated for alert {alert_id}")
            
            return receipt
        
        except Exception as e:
            logger.error(f"RetrospectiveAgent: Failed to generate receipt: {e}", exc_info=True)
            raise


# Utility for bulk operations
class AgentOrchestrator:
    """Top-level orchestrator coordinating all agents."""
    
    @staticmethod
    async def process_complete_session(session_id: str, end_user_id: str):
        """
        Complete end-to-end session processing:
        1. Extract commitments with confidence
        2. Extract decisions with watch_terms
        3. Check for gaps
        4. Check for drifts (if screen recording)
        5. Generate receipts for alerts
        """
        db = get_db()
        
        logger.info(f"AgentOrchestrator: Processing complete session {session_id}")
        
        try:
            # Get session
            session = await db.sessions.find_one({"session_id": session_id})
            if not session:
                logger.error(f"AgentOrchestrator: Session not found {session_id}")
                return
            
            # Step 1: Extract commitments (transcript-based)
            if session.get("transcript_chunks"):
                transcript = " ".join([
                    chunk.get("text", "") 
                    for chunk in session.get("transcript_chunks", [])
                ])
                
                commitments = await CommitmentAgent.process_transcript(
                    transcript, session_id, end_user_id
                )
                
                logger.info(f"AgentOrchestrator: Extracted {len(commitments)} commitments")
                
                # Step 2: Extract decisions for each commitment
                for commitment in commitments:
                    await DecisionAgent.extract_from_commitment(
                        commitment_id=str(commitment["_id"]),
                        commitment_text=commitment["text"],
                        session_id=session_id,
                        end_user_id=end_user_id,
                        transcript_context=transcript
                    )
            
            # Step 3: Check for drifts (screen recording-based)
            if session.get("indexed_visuals") and session.get("rtstream_id"):
                drifts = await DriftDetector.check_for_drifts(
                    end_user_id=end_user_id,
                    indexed_visuals=session["indexed_visuals"],
                    rtstream_session_id=session_id
                )
                
                logger.info(f"AgentOrchestrator: Detected {len(drifts)} drifts")
                
                # Generate receipts for drift alerts
                for drift_alert in drifts:
                    try:
                        await RetrospectiveAgent.generate_receipt(drift_alert["alert_id"])
                    except Exception as e:
                        logger.error(f"AgentOrchestrator: Failed to generate receipt: {e}")
            
            logger.info(f"AgentOrchestrator: Completed processing for session {session_id}")
        
        except Exception as e:
            logger.error(f"AgentOrchestrator: Processing failed: {e}", exc_info=True)
