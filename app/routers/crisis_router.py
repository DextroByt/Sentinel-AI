from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db import database, crud
from app.schemas import schemas
from app.services import verification_orchestrator, claim_extraction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Rumor Intel & Crises"])

async def get_db():
    async with database.AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise

# --- Background Wrapper ---

async def run_adhoc_background_wrapper(analysis_id: UUID, raw_query_text: str):
    """
    Background Task: Smartly parses the user's raw input into a structured claim 
    before launching the Agentic Pipeline.
    """
    async with database.AsyncSessionLocal() as db:
        try:
            logger.info(f"[AdHoc] 🧠 Analyzing user report: '{raw_query_text[:50]}...'")
            
            # 1. INTELLIGENT EXTRACTION
            # Users often type vague things like "Is the video about the Mumbai bridge true?"
            # We need to extract: Claim="Bridge Collapse", Location="Mumbai"
            extracted_data = await claim_extraction_service.extract_claims(raw_query_text)
            
            target_claim = raw_query_text
            target_location = "Unknown"

            # Pick the most relevant claim found by the LLM
            if extracted_data:
                best_match = extracted_data[0]
                target_claim = best_match.get("text", raw_query_text)
                target_location = best_match.get("location", "Unknown")
                logger.info(f"[AdHoc] 🎯 Structured Intent: Claim='{target_claim}' | Loc='{target_location}'")
            else:
                logger.warning("[AdHoc] Extraction failed, falling back to raw query.")

            # 2. UPDATE RECORD WITH STRUCTURED DATA
            # (Optional: You could update the DB record here to show the 'Refined Query' to the user)

            # 3. LAUNCH AGENTIC PIPELINE
            # We pass the *Cleaned* claim and location to the agents for higher accuracy.
            await verification_orchestrator.run_verification_pipeline(
                db_session=db,
                claim_text=target_claim,
                location=target_location, 
                adhoc_analysis_id=analysis_id,
                crisis_id=None # This is an isolated user query, not linked to a main crisis yet
            )

        except Exception as e:
            logger.error(f"[AdHoc] Background task crashed: {e}")
            await crud.update_adhoc_analysis(db, analysis_id, status="FAILED")

# --- Endpoints ---

@router.get("/crises/", response_model=List[schemas.Crisis])
async def read_crises(db: AsyncSession = Depends(get_db)):
    """
    Get the live dashboard of Active Threats and Lethal Rumors.
    """
    return await crud.get_crises(db)

@router.get("/crises/{crisis_id}", response_model=schemas.Crisis)
async def read_crisis(crisis_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get deep-dive details for a specific threat (Master Verdict, etc.).
    """
    crisis = await crud.get_crisis(db, crisis_id)
    if not crisis:
        raise HTTPException(status_code=404, detail="Crisis entry not found")
    return crisis

@router.get("/crises/{crisis_id}/timeline", response_model=List[schemas.TimelineItem])
async def read_crisis_timeline(crisis_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get the 'War Room' timeline: Verified Facts vs. Debunked Lies for this crisis.
    """
    crisis = await crud.get_crisis(db, crisis_id)
    if not crisis:
        raise HTTPException(status_code=404, detail="Crisis entry not found")
    return await crud.get_timeline_items(db, crisis_id)

# --- User Defined Crisis / Ad Hoc Analysis Endpoints ---

@router.post("/analyze", response_model=schemas.AdHocAnalysisResponse)
async def start_analysis(
    req: schemas.AdHocAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    **The 'Rumor Verification' Endpoint.**
    User submits a suspicious claim. We return an ID immediately.
    The Background Agents then:
    1. Parse the claim (Extract Location/Topic).
    2. Hunt for evidence (News, Govt, Fact-Checks).
    3. Synthesize a Verdict.
    """
    # 1. Create initial record (Status: PENDING)
    analysis = await crud.create_adhoc_analysis(db, req.query_text)
    
    # 2. Trigger the Smart Background Wrapper
    background_tasks.add_task(
        run_adhoc_background_wrapper,
        analysis_id=analysis.id,
        raw_query_text=analysis.query_text
    )
    
    return analysis

@router.get("/analyze/{analysis_id}", response_model=schemas.AdHocAnalysisResponse)
async def check_analysis_status(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Poll this endpoint to check if the Agents have finished the investigation.
    """
    analysis = await crud.get_adhoc_analysis(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis ID not found")
    return analysis

# --- Notification Endpoints ---

@router.get("/notifications/latest", response_model=Optional[schemas.SystemNotification])
async def get_latest_notification(db: AsyncSession = Depends(get_db)):
    """
    Frontend polls this for 'Red Alerts' (e.g., 'STOP SHARING - HOAX DETECTED').
    """
    return await crud.get_latest_notification(db)