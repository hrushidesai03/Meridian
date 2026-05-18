"""
Scheduler for periodic commitment gap and drift detection.
Runs background tasks to check for new gaps/drifts at regular intervals.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from database.db import get_db
from agents.orchestration import GapDetector, DriftDetector

logger = logging.getLogger(__name__)

# Global scheduler state
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None


async def start_scheduler():
    """Start the background scheduler."""
    global _scheduler_running, _scheduler_task
    
    if _scheduler_running:
        logger.warning("Scheduler is already running")
        return
    
    _scheduler_running = True
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    
    logger.info("Scheduler started")


async def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running, _scheduler_task
    
    _scheduler_running = False
    
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
    
    logger.info("Scheduler stopped")


async def _scheduler_loop():
    """Main scheduler loop."""
    db = get_db()
    
    while _scheduler_running:
        try:
            logger.info("Scheduler: Running periodic checks")
            
            # Get all active users (with recent activity)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            recent_users = await db.commitments.distinct(
                "end_user_id",
                {"created_at": {"$gte": thirty_days_ago}}
            )
            
            logger.info(f"Scheduler: Checking {len(recent_users)} active users")
            
            # Check each user for gaps
            for user_id in recent_users:
                try:
                    await GapDetector.check_commitment_gaps(
                        end_user_id=user_id,
                        current_date=datetime.utcnow().isoformat()
                    )
                
                except Exception as e:
                    logger.error(f"Scheduler: Gap detection failed for user {user_id}: {e}")
            
            logger.info("Scheduler: Completed periodic checks")
            
            # Sleep for 1 hour before next check
            await asyncio.sleep(3600)
        
        except asyncio.CancelledError:
            logger.info("Scheduler: Task cancelled")
            break
        
        except Exception as e:
            logger.error(f"Scheduler: Error in main loop: {e}", exc_info=True)
            # Sleep 1 minute before retrying
            await asyncio.sleep(60)


async def trigger_manual_gap_check(end_user_id: str):
    """Manually trigger gap detection for a user."""
    logger.info(f"Scheduler: Triggering manual gap check for {end_user_id}")
    
    try:
        await GapDetector.check_commitment_gaps(
            end_user_id=end_user_id,
            current_date=datetime.utcnow().isoformat()
        )
        logger.info(f"Scheduler: Manual gap check completed for {end_user_id}")
    
    except Exception as e:
        logger.error(f"Scheduler: Manual gap check failed: {e}")
        raise


async def trigger_manual_drift_check(end_user_id: str, session_id: str):
    """Manually trigger drift detection for a user's screen session."""
    db = get_db()
    
    logger.info(f"Scheduler: Triggering manual drift check for {end_user_id}, session {session_id}")
    
    try:
        session = await db.sessions.find_one({"session_id": session_id})
        
        if not session or not session.get("indexed_visuals"):
            logger.warning(f"Scheduler: Session {session_id} not found or has no indexed visuals")
            return
        
        await DriftDetector.check_for_drifts(
            end_user_id=end_user_id,
            indexed_visuals=session["indexed_visuals"],
            rtstream_session_id=session_id
        )
        
        logger.info(f"Scheduler: Manual drift check completed")
    
    except Exception as e:
        logger.error(f"Scheduler: Manual drift check failed: {e}")
        raise
