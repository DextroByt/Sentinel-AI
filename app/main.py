import asyncio
from app.services.synthesizer_service import synthesize_verdict


# --- MOCK AGENTS (For testing flow without external scraping) ---
async def mock_official_check(claim):
    if "flood" in claim.lower():
        return ["Gov Report: No floods detected."]
    return []

async def mock_media_check(claim):
    return [] # Simulate no media coverage

async def mock_debunk_check(claim):
    if "alien" in claim.lower():
        return ["FactCheck.org: No aliens found."]
    return []
# ----------------------------------------------------------------

async def run_verification_pipeline(claim_text: str):
    """
    Orchestrates the 3-agent check and synthesis.
    Ref: Blueprint Section 3.2 (Parallel Execution)
    """
    print(f"Orchestrator: Verifying '{claim_text}'...")
