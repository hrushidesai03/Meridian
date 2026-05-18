from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class CaptureType(str, Enum):
    """Type of capture session."""
    TRANSCRIPT = "transcript"
    SCREEN_RECORDING = "screen_recording"


class Session(BaseModel):
    """Represents a VideoDB capture session (transcript or screen recording)."""
    
    session_id: str = Field(..., description="Unique session ID from VideoDB")
    capture_session_id: str = Field(..., description="VideoDB capture_session_id")
    capture_type: CaptureType
    end_user_id: str = Field(..., description="End user identifier")
    
    # Transcript data (for TRANSCRIPT type)
    transcript: Optional[str] = None
    transcript_chunks: Optional[List[Dict[str, Any]]] = None  # List of {timestamp, text, speaker}
    
    # Screen data (for SCREEN_RECORDING type)
    rtstream_id: Optional[str] = None
    visual_index_url: Optional[str] = None
    indexed_visuals: Optional[List[Dict[str, Any]]] = None  # List of {visual_index, timestamp, description}
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    # Processing state
    processed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_123abc",
                "capture_session_id": "cap_456def",
                "capture_type": "transcript",
                "end_user_id": "user_789",
                "transcript": "We committed to launching by Friday...",
                "transcript_chunks": [
                    {"timestamp": 0, "text": "We committed to launching by Friday", "speaker": "Alice"}
                ],
                "processed": False
            }
        }


class Commitment(BaseModel):
    """Extracted commitment with confidence score."""
    
    commitment_id: str = Field(default_factory=lambda: f"com_{datetime.utcnow().timestamp()}", description="Unique commitment ID")
    session_id: str = Field(..., description="Source session")
    end_user_id: str
    
    text: str = Field(..., description="The commitment statement")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    
    # Flag for drift detection
    flagged_for_drift: bool = False
    
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "commitment_id": "com_1234567890",
                "session_id": "sess_123abc",
                "end_user_id": "user_789",
                "text": "Launch the product by Friday EOD",
                "confidence_score": 0.95,
                "flagged_for_drift": False
            }
        }


class Decision(BaseModel):
    """Extracted decision with watch_terms for drift detection."""
    
    decision_id: str = Field(default_factory=lambda: f"dec_{datetime.utcnow().timestamp()}", description="Unique decision ID")
    session_id: str = Field(..., description="Source session")
    commitment_id: str = Field(..., description="Linked commitment")
    end_user_id: str
    
    text: str = Field(..., description="The decision statement")
    watch_terms: List[str] = Field(..., description="Terms to monitor for drift")
    
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec_1234567890",
                "session_id": "sess_123abc",
                "commitment_id": "com_1234567890",
                "end_user_id": "user_789",
                "text": "We'll use React for the frontend and FastAPI for the backend",
                "watch_terms": ["React", "frontend", "FastAPI", "backend"]
            }
        }


class AlertType(str, Enum):
    """Type of alert."""
    GAP = "gap"
    DRIFT = "drift"


class Alert(BaseModel):
    """Alert for gap (commitment not executed) or drift (decision not followed)."""
    
    alert_id: str = Field(default_factory=lambda: f"alr_{datetime.utcnow().timestamp()}", description="Unique alert ID")
    alert_type: AlertType
    commitment_id: Optional[str] = None
    decision_id: Optional[str] = None
    end_user_id: str
    
    # Gap alert
    gap_description: Optional[str] = None
    
    # Drift alert
    drift_description: Optional[str] = None
    drift_evidence: Optional[str] = None  # Screen observation that contradicts decision
    visual_index: Optional[int] = None  # Reference to indexed visual
    
    # Receipt
    receipt_video_id: Optional[str] = None
    receipt_video_url: Optional[str] = None
    
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "alr_1234567890",
                "alert_type": "drift",
                "commitment_id": "com_1234567890",
                "decision_id": "dec_1234567890",
                "end_user_id": "user_789",
                "drift_description": "Decision stated React would be used, but Vue was imported",
                "drift_evidence": "import Vue from 'vue'",
                "visual_index": 42,
                "receipt_video_id": "vid_abc123"
            }
        }
