import asyncio
import logging
import json
import time
import re
import warnings
from datetime import datetime, timezone
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from duckduckgo_search import DDGS 

from app.core.config import settings
from app.db import database, crud
from app.services import claim_extraction_service 
from app.services import verification_orchestrator
from app.services import rss_service
from app.services import synthesizer_service 
from app.schemas.schemas import VerificationStatus
# [NEW] Import the rotation manager
from app.core.gemini_client import gemini_client

# Suppress annoying "package renamed" warnings from DDGS
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

logger = logging.getLogger(__name__)

# --- Configuration ---
DISCOVERY_KEYWORDS_REGEX = r"(disaster|accident|emergency|collapse|explosion|riot|earthquake|flood|tsunami|virus|outbreak|leak|bioweapon|conspiracy|coverup|censored|exposed|fake|hoax|rumor|forwarded|viral|whatsapp|audio|warning|alert|death|killed|lethal|radioactive|poison)"

# --- Cycle Timings ---
CYCLE_TOTAL_DURATION = 60 * 60        
DISCOVERY_WINDOW = 2 * 60             

# --- Concurrency ---
MAX_CONCURRENT_SCANS = 5 
HIGH_RISK_SCAN_INTERVAL = 120 

# [REMOVED] genai.configure() is handled by the manager now.


# --- UTILS: Robust Search Wrapper ---

def _safe_ddg_text_search(query: str, max_results: int = 5, retries: int = 3) -> List[Dict]:
    """
    Wraps DDGS text search with retries and exponential backoff.
    Prevents 'Operation Timed Out' from crashing the scanner.
    """
    for attempt in range(retries):
        try:
            with DDGS() as ddgs:
                # safesearch='off' is needed to find raw rumors/uncensored news
                return list(ddgs.text(query, region="wt-wt", safesearch="off", timelimit="d", max_results=max_results))
        except Exception as e:
            wait_time = 2 ** attempt # 1s, 2s, 4s...
            logger.warning(f"[Scanner] DDGS Search Warning (Attempt {attempt+1}/{retries}): {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            
    logger.error(f"[Scanner] DDGS Search FAILED after {retries} attempts for query: '{query[:20]}...'")
    return []

# --- PHASE 1: THREAT DISCOVERY ---

def filter_relevant_headlines(articles: List[Dict]) -> List[Dict]:
    relevant = []
    pattern = re.compile(DISCOVERY_KEYWORDS_REGEX, re.IGNORECASE)
    for art in articles:
        text_blob = f"{art.get('title', '')} {art.get('description', '')}"
        if pattern.search(text_blob):
            relevant.append(art)
    return relevant

def _perform_social_listening() -> List[Dict]:
    """
    Aggressive social scanning to fill the pipeline immediately.
    """
    social_queries = [
        '"forwarded as received" site:twitter.com',
        '"forward this message" site:whatsapp.com',
        '"media wont tell you" site:twitter.com',
        '"viral video" "shocking" site:facebook.com',
        '"leaked audio" warning site:youtube.com',
        '"government hiding" disaster site:reddit.com',
        '"urgent alert" site:instagram.com',
        '"don\'t go there" site:twitter.com',
        '"rumor has it" site:twitter.com',
        '"fake news" alert site:twitter.com'
    ]
    results = []
    
    # We loop through queries sequentially here, but the search itself is robust now.
    for q in social_queries:
        hits = _safe_ddg_text_search(q, max_results=5)
        for h in hits:
            results.append({
                "title": h.get('title', 'Social Rumor'),
                "description": h.get('body', ''),
                "url": h.get('href', ''),
                "source": {"name": "Social Signal", "type": "SOCIAL"},
                "published_at": "Just Now"
            })
            
    return results

async def analyze_and_assess_threats(db: AsyncSession, articles: List[Dict]):
    """
    Analyzes headlines and creates Crisis entries.
    RETURNS: A list of newly created Crisis objects.
    """
    new_crises = [] 
    
    if not articles: return []
    # Deduplicate by URL before processing
    seen_urls = set()
    unique_articles = []
    for a in articles:
        if a['url'] not in seen_urls:
            seen_urls.add(a['url'])
            unique_articles.append(a)
            
    articles = unique_articles[:60] # Limit input to avoid token overflow

    headlines = []
    for a in articles:
        raw_desc = a.get('description', '')
        clean_desc = re.sub(r'<[^>]+>', '', raw_desc)
        source = a.get('source', {}).get('name', 'Unknown')
        headlines.append(f"- {a['title']} ({source}): {clean_desc[:100]}...")
        
    digest = "\n".join(headlines)
    current_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    prompt = f"""
    You are a Misinformation Threat Intelligence Agent.
    CURRENT DATE: {current_utc}
    
    Analyze these headlines. Identify POTENTIAL RUMORS AND CRISES.
    
    OUTPUT JSON FORMAT:
    [
      {{
        "name": "Short Title (e.g. 'Rumor: Bio-Leak in Hyderabad')",
        "description": "Summary of what the rumor/claim says.",
        "keywords": "viral, video, leak, virus",
        "severity": 85,
        "location": "City, Country"
      }}
    ]
    
    SEVERITY SCORING:
    - 90-100: LETHAL (Medical advice, riots, nuclear panic).
    - 70-89: DANGEROUS (Fake accidents, collapse rumors).
    - 50-69: DISRUPTIVE.
    
    HEADLINES:
    {digest}
    """

    try:
        # [UPDATED] Use gemini_client for rotation
        response = await gemini_client.generate_content_async(
            model_name=settings.GEMINI_EXTRACTION_MODEL,
            prompt=prompt
        )
        
        if not response.text: return []

        raw_text = response.text.strip().replace("```json", "").replace("```", "")
        try:
            crises_data = json.loads(raw_text)
        except json.JSONDecodeError:
            return []

        for c_data in crises_data:
            name = c_data.get("name")
            if not name: continue
            
            existing = await crud.get_crisis_by_fuzzy_name(db, name)
            if existing: continue 
            
            severity = int(c_data.get("severity", 50))
            loc = c_data.get("location", "Unknown Location")
            
            print(f"🚨 [SCANNER] New Threat Detected: {name} ({loc})")
            logger.info(f"[Discovery] 🚨 NEW CANDIDATE: {name} ({loc})")
            
            new_crisis = await crud.create_crisis(
                db, name=name, description=c_data.get("description", ""),
                keywords=c_data.get("keywords", name), severity=severity, location=loc 
            )
            
            new_crises.append(new_crisis)

            await crud.create_timeline_item(
                db,
                crisis_id=new_crisis.id,
                claim_text=f"Signal Detected: {name}",
                summary=f"Sentinel AI picked up this signal from web chatter. Automated verification agents have been deployed.",
                status=VerificationStatus.UNCONFIRMED,
                sources=[{"title": "Sentinel Watchdog", "url": "#"}],
                location=loc,
                confidence_score=10, # Initial low confidence
                reasoning_trace="Automated signal detection. Awaiting deep scan."
            )

            asyncio.create_task(
                _background_seed_timeline(new_crisis.id, c_data.get("description", name), loc)
            )
            
        return new_crises

    except Exception as e:
        logger.error(f"[Discovery] Threat analysis failed: {e}")
        return []

async def _background_seed_timeline(crisis_id, text, location):
    """Helper to run verification without blocking the main discovery loop."""
    async with database.AsyncSessionLocal() as db:
        await verification_orchestrator.run_verification_pipeline(
            db_session=db, 
            claim_text=text, 
            crisis_id=crisis_id, 
            location=location 
        )

async def perform_agentic_selection(db: AsyncSession):
    """
    THE BRAIN: Agent reviews ALL candidates and picks the Strategic Top 10.
    """
    logger.info("[Agent Selection] 🧠 Reviewing all candidates for prioritization...")
    
    all_crises = await crud.get_crises(db, limit=100)
    if not all_crises: return

    candidates_text = "\n".join([f"ID: {c.id} | Name: {c.name} | Sev: {c.severity} | Loc: {c.location}" for c in all_crises])
    
    prompt = f"""
    You are the Crisis Supervisor for Sentinel AI.
    We have detected {len(all_crises)} potential threats.
    
    YOUR MISSION: Select exactly 10 items to track for the next hour.
    
    SELECTION CRITERIA:
    1. Select TOP 3 "CATASTROPHIC/REAL" events (Real disasters, verified attacks).
    2. Select TOP 7 "VIRAL RUMORS/MISINFORMATION" (Hoaxes, fake news, panic triggers).
    
    PRIORITIZE UNIQUE LOCATIONS AND HIGH SEVERITY.
    
    CANDIDATES:
    {candidates_text}
    
    OUTPUT JSON:
    {{
      "selected_ids": ["uuid-1", "uuid-2", ...]
    }}
    """
    
    try:
        # [UPDATED] Use gemini_client for rotation
        response = await gemini_client.generate_content_async(
            model_name=settings.GEMINI_EXTRACTION_MODEL,
            prompt=prompt
        )
        clean_json = response.text.strip().replace("```json", "").replace("```", "")
        selection = json.loads(clean_json)
        
        keep_ids = selection.get("selected_ids", [])
        
        if not keep_ids:
            await _fallback_pruning(db)
            return

        count_kept = 0
        count_del = 0
        for c in all_crises:
            if str(c.id) not in keep_ids:
                await db.delete(c)
                count_del += 1
            else:
                count_kept += 1
        
        await db.commit()
        logger.info(f"[Agent Selection] ✅ Brain Decision: Kept {count_kept} items. Deleted {count_del} irrelevant ones.")

    except Exception as e:
        logger.error(f"[Agent Selection] Failed: {e}. Using fallback.")
        await _fallback_pruning(db)

async def _fallback_pruning(db: AsyncSession):
    all_crises = await crud.get_crises(db, limit=100)
    all_crises.sort(key=lambda x: x.severity, reverse=True)
    keep = all_crises[:10]
    keep_ids = {c.id for c in keep}
    for c in all_crises:
        if c.id not in keep_ids: await db.delete(c)
    await db.commit()

async def run_discovery_phase(db: AsyncSession):
    logger.info(">>> PHASE 1: THREAT DISCOVERY (High Throughput) <<<")
    
    # Run RSS Fetch (Already Async)
    rss_coro = rss_service.fetch_all_rss_feeds()
    
    # Run Social Listening (Sync wrapped in Thread)
    social_task = asyncio.to_thread(_perform_social_listening)
    
    # Run concurrently
    results = await asyncio.gather(rss_coro, social_task)
    
    all_items = results[0] + results[1] 
    
    print(f"🔍 [SCANNER] Scanned {len(all_items)} raw signals.")
    
    relevant = filter_relevant_headlines(all_items)
    
    if relevant:
        logger.info(f"[Discovery] Processing {len(relevant)} items...")
        return await analyze_and_assess_threats(db, relevant)
    else:
        logger.info("[Discovery] No signals found.")
        return []

# --- PHASE 2: DEEP GATHERING ---

def _perform_hybrid_search(keywords: str) -> List[Dict]:
    results = []
    # Try getting news
    try:
        with DDGS() as ddgs:
             news = list(ddgs.news(keywords, region="wt-wt", safesearch="off", timelimit="w", max_results=3))
             results.extend(news)
    except Exception: pass
    
    # Try getting web text
    if len(results) < 2:
        try:
             results.extend(_safe_ddg_text_search(keywords, max_results=3))
        except Exception: pass
        
    # Standardize
    final = []
    for r in results:
        final.append({
            "title": r.get('title', 'Unknown'), 
            "body": r.get('body', r.get('description', '')), 
            "url": r.get('href', r.get('url', ''))
        })
    return final

async def process_single_crisis_task(crisis_id: str):
    async with database.AsyncSessionLocal() as db:
        try:
            crisis = await crud.get_crisis(db, crisis_id)
            if not crisis: return

            logger.info(f"[Deep Scan] 🚀 Worker: {crisis.name}")
            queries = [crisis.keywords, f"{crisis.keywords} viral hoax"]

            for q in queries:
                articles = await asyncio.to_thread(_perform_hybrid_search, q)
                if not articles: continue

                for art in articles:
                    text = f"{art.get('title','')} {art.get('body','')}"
                    claims_data = await claim_extraction_service.extract_claims(text)
                    
                    for claim_obj in claims_data:
                        claim_text = claim_obj["text"]
                        # Check duplicates
                        if await crud.get_timeline_item_by_claim_text(db, claim_text): continue
                        
                        await verification_orchestrator.run_verification_pipeline(
                            db_session=db, claim_text=claim_text, 
                            crisis_id=crisis.id, location=claim_obj["location"] 
                        )
            
            # Synthesize verdict after deep scan
            await synthesizer_service.synthesize_crisis_conclusion(db, crisis.id)
        except Exception as e: logger.error(f"Worker Error: {e}")

async def run_deep_gathering_phase(db: AsyncSession, duration_seconds: int):
    logger.info(f">>> PHASE 2: DEEP GATHERING ({duration_seconds/60:.1f}m) <<<")
    start_time = time.time()
    normal_queue_ptr = 0
    last_scan_times = {} 

    while time.time() < (start_time + duration_seconds):
        all_crises = await crud.get_crises(db, limit=20)
        if not all_crises:
            await asyncio.sleep(10); continue

        high_risk = [c for c in all_crises if c.severity >= 90]
        normal_risk = [c for c in all_crises if c.severity < 90]
        
        batch = []
        now = time.time()

        for c in high_risk:
            if (now - last_scan_times.get(c.id, 0)) > HIGH_RISK_SCAN_INTERVAL:
                batch.append(c)
        
        slots = MAX_CONCURRENT_SCANS - len(batch)
        if slots > 0 and normal_risk:
            for _ in range(slots):
                c = normal_risk[normal_queue_ptr % len(normal_risk)]
                if c not in batch: batch.append(c)
                normal_queue_ptr += 1

        if not batch:
            await asyncio.sleep(5); continue

        logger.info(f"[Deep Scan] ⚡ Batch: {len(batch)} items")
        tasks = [process_single_crisis_task(c.id) for c in batch]
        for c in batch: last_scan_times[c.id] = now
        
        await asyncio.gather(*tasks)
        await asyncio.sleep(2)

# --- MAIN LOOP ---

async def start_monitoring():
    logger.info("--- Sentinel AI Supervisor Started (Autonomous Mode) ---")
    
    is_first_run = True
    
    while True:
        cycle_start = time.time()
        
        # 1. DISCOVERY
        logger.info(">>> STARTING DISCOVERY PHASE (2 Mins) <<<")
        
        new_threats = []
        
        async with database.AsyncSessionLocal() as db:
            try:
                new_threats = await run_discovery_phase(db)
                
                # --- NOTIFICATION LOGIC ---
                if new_threats:
                    high_sev_crises = [c for c in new_threats if c.severity >= 75]
                    
                    if high_sev_crises:
                        if is_first_run:
                            high_sev_crises.sort(key=lambda x: x.severity, reverse=True)
                            top_picks = high_sev_crises[:3]
                            names = ", ".join([c.name for c in top_picks])
                            
                            msg = f"⚠ SYSTEM ONLINE: Initial Scan Complete. Detected {len(high_sev_crises)} Active Threats. Top Priority: {names}."
                            await crud.create_notification(db, content=msg, type="CATASTROPHIC_ALERT")
                        else:
                            for c in high_sev_crises:
                                msg = f"🚨 NEW THREAT DETECTED: {c.name} (Severity: {c.severity}) detected in {c.location}."
                                await crud.create_notification(db, content=msg, type="CATASTROPHIC_ALERT", crisis_id=c.id)

            except Exception as e: 
                logger.error(f"Discovery Error: {e}")
        
        is_first_run = False
        
        elapsed = time.time() - cycle_start
        if elapsed < DISCOVERY_WINDOW:
            await asyncio.sleep(DISCOVERY_WINDOW - elapsed)

        # 2. AGENTIC SELECTION
        async with database.AsyncSessionLocal() as db:
            await perform_agentic_selection(db)

        # 3. DEEP GATHERING
        gather_len = CYCLE_TOTAL_DURATION - DISCOVERY_WINDOW - 30
        async with database.AsyncSessionLocal() as db:
             await run_deep_gathering_phase(db, duration_seconds=gather_len)
             await crud.delete_old_crises(db) 

        logger.info("[Cycle] Resetting...")
        await asyncio.sleep(5)