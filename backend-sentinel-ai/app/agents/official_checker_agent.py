import logging
import re
import asyncio
import ssl
import random
import warnings
from typing import List, Set, Dict, Tuple, Any
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS 

# --- Log Cleanup ---
# Suppress the noisy RuntimeWarning from duckduckgo_search about package renaming
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

# Setup logging
logger = logging.getLogger(__name__)

# --- Configuration: Authority Anchors ---
# 1. Direct Portals: We poll these homepages for "Breaking News" tickers/banners.
DIRECT_OFFICIAL_PORTALS = [
    # Disaster & Safety
    "https://ndrf.gov.in/",                         # National Disaster Response Force
    "https://ndma.gov.in/",                         # National Disaster Management Authority
    "https://sachet.ndma.gov.in/",                  # Sachet Early Warning System
    "https://cwc.gov.in/",                          # Central Water Commission (Floods)
    
    # Weather & Geo
    "https://mausam.imd.gov.in/",                   # India Meteorological Department
    "https://incois.gov.in/portal/osf/osf.jsp",     # Tsunami Early Warning
    
    # Major City Police/Civic (Expandable)
    "https://mumbaipolice.gov.in/",
    "https://delhipolice.gov.in/",
    "https://portal.mcgm.gov.in/",                  # BMC Mumbai
    
    # Health
    "https://mohfw.gov.in/",                        # Ministry of Health
    "https://ncdc.gov.in/",                         # Disease Control
]

# 2. Trusted Domains: We use Search Engines to deep-scan these TLDs.
TRUSTED_TLDS = [
    "gov.in", "nic.in", "police.gov.in", "org.in", # India Govt
    "who.int", "un.org", "gdacs.org"               # Global Bodies
]

# 3. Official Social Media Handles (For Search Operator Targeting)
# We search these specific profiles via web search to bypass API limits.
OFFICIAL_HANDLES = [
    "twitter.com/MumbaiPolice",
    "twitter.com/NDRFHQ",
    "twitter.com/Indiametdept",
    "twitter.com/ndmaindia",
    "twitter.com/CMOMaharashtra",
    "twitter.com/MoHFW_INDIA",
    "facebook.com/BrihanmumbaiMunicipalCorporation"
]

# --- Advanced Scraping Config ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

def get_random_header() -> Dict[str, str]:
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        # CRITICAL FIX: Force close connection to prevent ResourceWarnings about unclosed transports
        'Connection': 'close', 
        'Upgrade-Insecure-Requests': '1',
    }

def extract_keywords(text: str) -> str:
    """
    Extracts a clean search query string from the claim.
    Removes stop words but keeps numbers and key entities.
    """
    stop_words = {
        "is", "are", "was", "were", "the", "a", "an", "in", "on", "at", "to", "for", 
        "of", "with", "by", "has", "have", "had", "been", "it", "this", "that", "i", 
        "official", "confirmed", "news", "report", "fake", "real", "check"
    }
    clean_text = re.sub(r'[^\w\s]', '', text.lower())
    words = [w for w in clean_text.split() if w not in stop_words and len(w) > 2]
    
    # Return top 6 keywords to prevent search query bloat
    return " ".join(words[:6])

# --- HELPER: Sync Wrapper for DDGS ---
def _perform_sync_ddg_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Executes the synchronous DDGS search safely within a thread wrapper.
    Returns a list of dictionaries with 'title', 'href', 'body'.
    """
    try:
        with DDGS() as ddgs:
            # [CHANGE] Added timelimit="w" (Past Week) to ensure official info is CURRENT.
            # This stops the agent from verifying 2015 flood relief notices as current 2025 news.
            return list(ddgs.text(query, timelimit="w", max_results=max_results))
    except Exception as e:
        logger.error(f"[Official Agent] DDGS Internal Error: {e}")
        return []

# --- COMPONENT 1: Direct Portal Scraper (Async) ---
async def scrape_portal(session: aiohttp.ClientSession, url: str, keywords: List[str], ssl_context: ssl.SSLContext) -> str:
    """
    Scrapes a single portal using a shared session and SSL context.
    """
    try:
        # Use the passed ssl_context to avoid creating new ones for every request (Memory/CPU optimization)
        async with session.get(url, headers=get_random_header(), timeout=10, ssl=ssl_context) as response:
            if response.status == 200:
                html = await response.text(errors='ignore')
                soup = BeautifulSoup(html, 'html.parser')
                
                # Cleanup
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                
                text = soup.get_text(separator=' ').lower()
                
                # Check for matches
                found = [k for k in keywords if k in text]
                if len(found) >= 2: # At least 2 keywords to match
                    # Extract context (150 chars around match)
                    idx = text.find(found[0])
                    start = max(0, idx - 50)
                    end = min(len(text), idx + 100)
                    snippet = text[start:end].replace("\n", " ").strip()
                    return f"Direct Match on {url}: \"...{snippet}...\""
    except Exception:
        pass # Fail silently for individual sites to keep speed up
    return ""

# --- COMPONENT 2: Deep Web Search (DuckDuckGo) ---
async def search_official_web(query: str) -> List[str]:
    """
    Uses DuckDuckGo to search ONLY trusted government domains.
    Query format: "Mumbai Bridge Collapse site:gov.in OR site:nic.in"
    """
    evidence = []
    # Construct strictly limited query
    site_operators = " OR ".join([f"site:{tld}" for tld in TRUSTED_TLDS])
    final_query = f"{query} ({site_operators})"
    
    logger.info(f"[Official Agent] Executing Deep Web Search: {final_query}")

    try:
        # Run synchronous DDGS in a separate thread
        results = await asyncio.to_thread(_perform_sync_ddg_search, final_query, 5)
        
        for res in results:
            title = res.get('title', '')
            link = res.get('href', '')
            body = res.get('body', '')
            evidence.append(f"Govt Web Search Result: [{title}]({link}) - {body}")
                
    except Exception as e:
        logger.error(f"[Official Agent] Web Search Failed: {e}")
        
    return evidence

# --- COMPONENT 3: Official Social Media Search ---
async def search_official_social(query: str) -> List[str]:
    """
    Searches specific official social media handles for the claim.
    Query format: "Mumbai Rain site:twitter.com/MumbaiPolice"
    """
    evidence = []
    # Construct handle-specific query
    handle_operators = " OR ".join([f"site:{handle}" for handle in OFFICIAL_HANDLES])
    final_query = f"{query} ({handle_operators})"
    
    logger.info(f"[Official Agent] Scanning Official Social Channels: {final_query}")

    try:
        # Run synchronous DDGS in a separate thread
        results = await asyncio.to_thread(_perform_sync_ddg_search, final_query, 5)
        
        for res in results:
            title = res.get('title', '')
            link = res.get('href', '')
            body = res.get('body', '')
            # Filter out low quality hits
            if "twitter.com" in link or "facebook.com" in link:
                evidence.append(f"Official Social Media Update: [{title}]({link}) - {body}")

    except Exception as e:
        logger.error(f"[Official Agent] Social Search Failed: {e}")
        
    return evidence

# --- MAIN ORCHESTRATOR ---
async def check_sources(claim_text: str) -> List[str]:
    """
    Master function called by the Verification Orchestrator.
    Runs all 3 intelligence components in parallel.
    """
    logger.info(f"[Official Agent] 🔍 Initiating Multi-Vector Scan for: '{claim_text}'")
    
    # 1. Prepare Query
    search_query = extract_keywords(claim_text)
    keywords_list = search_query.split()
    
    if not search_query or len(keywords_list) < 2:
        return ["Claim text too vague for official verification."]

    evidence_pool = []

    # 2. Setup Shared SSL Context (Optimized)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # 3. Execute Parallel Tasks
    async with aiohttp.ClientSession() as session:
        tasks = [
            # Task A: Search Gov Web
            search_official_web(search_query),
            # Task B: Search Official Socials
            search_official_social(search_query),
            # Task C: Direct Portal Polling (Using shared session & SSL)
            *[scrape_portal(session, url, keywords_list, ssl_ctx) for url in DIRECT_OFFICIAL_PORTALS]
        ]
        
        # Gather all results
        results = await asyncio.gather(*tasks)
        
        # Optional: Small sleep to allow underlying transports to close gracefully
        await asyncio.sleep(0.1)

    # 4. Flatten and Filter Results
    for res in results:
        if isinstance(res, list): # From search functions
            evidence_pool.extend(res)
        elif isinstance(res, str) and res: # From scraper
            evidence_pool.append(res)

    # 5. Final Verdict Generation
    if not evidence_pool:
        logger.info("[Official Agent] ❌ No official confirmation found across Portals, Web, or Socials.")
        return ["No direct confirmation found on monitored government portals or official social media channels."]
    
    logger.info(f"[Official Agent] ✅ Found {len(evidence_pool)} pieces of official evidence.")
    return evidence_pool