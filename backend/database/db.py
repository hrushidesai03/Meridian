import logging
from typing import Any
from motor.motor_asyncio import AsyncIOMotorClient
from config import get_settings

logger = logging.getLogger(__name__)

# Global database instance
_db_instance: Any | None = None


async def connect_db() -> Any:
    """Initialize MongoDB connection."""
    global _db_instance
    
    if _db_instance is not None:
        return _db_instance
    
    settings = get_settings()
    
    try:
        client = AsyncIOMotorClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)
        # Verify connection
        await client.admin.command("ping")
        _db_instance = client[settings.mongodb_db]
        
        logger.info(f"Connected to MongoDB: {settings.mongodb_db}")
        
        # Ensure indexes
        await _setup_indexes(_db_instance)
        
        return _db_instance
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}. Using in-memory mock database for testing.")
        # Return a mock in-memory database for testing/demo
        _db_instance = _create_mock_db()
        return _db_instance


async def disconnect_db():
    """Close MongoDB connection."""
    global _db_instance
    
    if _db_instance is not None:
        client = _db_instance.client
        client.close()
        _db_instance = None
        logger.info("Disconnected from MongoDB")


async def _setup_indexes(db: Any):
    """Set up database indexes."""
    try:
        # Sessions indexes
        await db.sessions.create_index("session_id", unique=True)
        await db.sessions.create_index("end_user_id")
        await db.sessions.create_index("created_at")
        
        # Commitments indexes
        await db.commitments.create_index("session_id")
        await db.commitments.create_index("end_user_id")
        await db.commitments.create_index("created_at")
        
        # Decisions indexes
        await db.decisions.create_index("session_id")
        await db.decisions.create_index("commitment_id")
        await db.decisions.create_index("end_user_id")
        
        # Alerts indexes
        await db.alerts.create_index("commitment_id")
        await db.alerts.create_index("decision_id")
        await db.alerts.create_index("end_user_id")
        await db.alerts.create_index("created_at")
        
        logger.info("Database indexes created")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


def get_db() -> Any:
    """Get database instance."""
    if _db_instance is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db_instance
