import logging
import re
import asyncio
import warnings
from typing import List, Set, Dict, Any

# REPLACED: Paid APIs with DuckDuckGo
from duckduckgo_search import DDGS

from app.core.config import settings

# --- Log Cleanup ---
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

logger = logging.getLogger(__name__)

# --- Trusted Domain Configuration ---
# Sites that verify before publishing.
TRUSTED_DOMAINS = [
    "reuters.com", "apnews.com", "bloomberg.com", "bbc.com", "cnn.com", 
    "aljazeera.com", "dw.com", "nytimes.com", "washingtonpost.com",
    "ndtv.com", "indiatoday.in", "indianexpress.com", "thehindu.com", 
    "timesofindia.indiatimes.com", "hindustantimes.com", "livemint.com", 
    "business-standard.com", "theprint.in", "scroll.in", "newindianexpress.com",
    "deccanherald.com", "telegraphindia.com", "lokmat.com", "news18.com"
]

def extract_search_query(claim_text: str) -> str:
    """
    Constructs a clean, keyword-focused query string from the claim text.
    """
    stop_words = {
        "is", "are", "was", "were", "the", "a", "an", "in", "on", "at", "to", 
        "has", "have", "had", "been", "it", "that", "this", "from", "by", "of",
        "near", "about", "some", "few", "reportedly", "allegedly", "breaking",
        "viral", "video", "fake", "rumor" # Remove these to find the actual event
    }
    clean_text = re.sub(r'[^\w\s]', '', claim_text.lower())
    words = [w for w in clean_text.split() if w not in stop_words and len(w) > 2]
    
    if not words:
        return ""
    
    return " ".join(words[:7])

def _perform_sync_ddg_text(query: str, max_results: int = 5) -> List[Dict]:
    """Sync wrapper for DDGS Web Search"""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, region="wt-wt", timelimit="m", max_results=max_results))
    except Exception as e:
        logger.error(f"[Media Agent] DDGS Web Error: {e}")
        return []

# --- ASYNC WORKERS ---

async def task_trusted_web_search(query: str) -> List[str]:
    """
    Worker 1: Site-specific search on trusted domains.
    If this returns 0 results, it is a strong indicator the event is NOT real.
    """
    evidence = []
    # Prioritize top 6 trusted sites
    site_ops = " OR ".join([f"site:{d}" for d in TRUSTED_DOMAINS[:8]])
    final_query = f"{query} ({site_ops})"
    
    try:
        results = await asyncio.to_thread(_perform_sync_ddg_text, final_query, 5)
        for res in results:
            title = res.get('title', 'No Title')
            link = res.get('href', '#')
            body = res.get('body', '')[:150] + "..."
            evidence.append(f"Trusted Media Report: [{title}]({link}) - {body}")
    except Exception as e:
        logger.error(f"[Media Agent] Trusted Web Error: {e}")
    return evidence

async def task_social_context_search(query: str) -> List[str]:
    """
    Worker 2: Check if this is being discussed as a 'Viral Video' or 'Hoax'.
    """
    evidence = []
    # Look for the claim alongside "viral" keywords
    final_query = f"{query} (viral OR whatsapp OR fake OR hoax)"
    try:
        results = await asyncio.to_thread(_perform_sync_ddg_text, final_query, 4)
        for res in results:
            title = res.get('title', 'Discussion')
            link = res.get('href', '#')
            evidence.append(f"Social/Viral Context: [{title}]({link})")
    except Exception as e:
        logger.error(f"[Media Agent] Social Error: {e}")
    return evidence

# --- MAIN ORCHESTRATOR ---

async def check_media(claim_text: str) -> List[str]:
    """
    Master Orchestrator for Media Verification.
    """
    logger.info(f"[Media Agent] 🚀 Scanning Mainstream Media for: '{claim_text}'")
    
    search_query = extract_search_query(claim_text)
    if not search_query:
        return ["Claim text insufficient for media extraction."]
    
    results = await asyncio.gather(
        task_trusted_web_search(search_query),
        task_social_context_search(search_query)
    )
    
    combined_evidence = []
    for res_list in results:
        combined_evidence.extend(res_list)
    
    unique_evidence = []
    seen_urls = set()
    for item in combined_evidence:
        try:
            if "](" in item and ")" in item:
                url = item.split("](")[1].split(")")[0]
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_evidence.append(item)
            else:
                 unique_evidence.append(item)
        except:
            unique_evidence.append(item)
            
    if not unique_evidence:
        logger.info(f"[Media Agent] ❌ No mainstream reports found (Suspicious).")
        return ["No confirmation found in trusted mainstream media outlets (This often indicates a rumor)."]
        
    logger.info(f"[Media Agent] ✅ Found {len(unique_evidence)} media reports.")
    return unique_evidence