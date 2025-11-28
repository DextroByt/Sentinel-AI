from pydantic import BaseModel, Field, UUID4, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# --- 1. Enums ---

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    DEBUNKED = "DEBUNKED"
    UNCONFIRMED = "UNCONFIRMED"

class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# --- 2. Crisis Schemas ---

class CrisisBase(BaseModel):
    name: str
    description: Optional[str] = None
    keywords: str
    severity: int = 50 
    location: Optional[str] = "Unknown Location"

class Crisis(CrisisBase):
    id: UUID4
    verdict_status: Optional[str] = "PENDING" 
    verdict_summary: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# --- 3. Timeline Schemas ---

class TimelineItem(BaseModel):
    id: UUID4
    crisis_id: UUID4
    claim_text: str
    summary: str
    status: VerificationStatus
    location: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = []
    
    # [NEW] Trust Architecture: AI Confidence & Logic
    confidence_score: int = 0
    reasoning_trace: Optional[str] = "Analysis pending..."
    
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# --- 4. User Defined Crisis / Ad Hoc Analysis Schemas ---

class AdHocAnalysisRequest(BaseModel):
    query_text: str = Field(..., min_length=5, description="The user defined crisis topic or claim to verify.")

class AdHocAnalysisResponse(BaseModel):
    id: UUID4
    query_text: str
    status: AnalysisStatus
    verdict_status: Optional[str] = None
    verdict_summary: Optional[str] = None
    verdict_sources: Optional[List[Dict[str, Any]]] = None
    
    # [NEW] Trust Architecture for User Reports
    confidence_score: int = 0
    reasoning_trace: Optional[str] = "Analysis pending..."

    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- 5. Notification Schemas ---

class SystemNotification(BaseModel):
    id: UUID4
    content: str
    notification_type: str 
    crisis_id: Optional[UUID4] = None 
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)