import logging
import re
import asyncio
import warnings
from typing import List, Dict, Any

# External Libraries
from duckduckgo_search import DDGS

# --- Log Cleanup ---
# Suppress the noisy RuntimeWarning from duckduckgo_search about package renaming
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

# Setup logging
logger = logging.getLogger(__name__)

# --- Configuration: The "Truth Squad" ---
# A curated list of IFCN-certified domains and specialized OSINT outlets.
# We use search operators to deep-scan these specific repositories.
FACT_CHECK_DOMAINS = [
    # --- India Specific (High Priority) ---
    "altnews.in",
    "boomlive.in",
    "newschecker.in",
    "factly.in",
    "vishvasnews.com",
    "thequint.com/news/webqoof",
    "indiatoday.in/fact-check",
    
    # --- Global/International ---
    "snopes.com",
    "reuters.com/fact-check",
    "afp.com/en/fact-check",
    "politifact.com",
    "checkyourfact.com",
    "fullfact.org",       # UK/Global Verification
    "factcheck.org",      # US/Global Sci/Pol
    "leadstories.com",    # Viral Hoaxes (Facebook Partner)
    
    # --- Specialized (War/Health/Propaganda) ---
    "bellingcat.com",     # Geopolitical/OSINT (War Crimes)
    "polygraph.info",     # State Propaganda
    "healthfeedback.org", # Medical Misinformation
    "climatefeedback.org" # Climate Hoaxes
]

# --- Helper Functions ---

def clean_text(text: str) -> str:
    """
    Normalizes text for comparison:
    - Lowercase
    - Remove punctuation
    - Remove extra whitespace
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculates Jaccard Similarity between the User's Claim and a Fact-Check Headline.
    Use Jaccard (Bag of Words) to match "Video of bridge collapse" with "Fact Check: Old bridge video viral".
    """
    set1 = set(clean_text(text1).split())
    set2 = set(clean_text(text2).split())
    
    if not set1 or not set2:
        return 0.0
        
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    
    return len(intersection) / len(union)

def extract_keywords(claim_text: str) -> str:
    """
    Extracts the core subject from the claim to ensure broad search coverage.
    Removes common stop words but keeps 'misinformation indicators'.
    """
    stop_words = {
        "is", "are", "was", "were", "the", "a", "an", "in", "on", "at", 
        "to", "for", "of", "with", "by", "i", "it", "this", "that"
    }
    # We intentionally KEEP words like: fake, viral, video, old, leaked, bioweapon
    
    clean_tokens = clean_text(claim_text).split()
    words = [w for w in clean_tokens if w not in stop_words and len(w) > 2]
    
    # Return top 6 keywords to prevent search query overflow
    return " ".join(words[:6])

def _perform_sync_ddg_search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Executes the synchronous DDGS search safely within a thread wrapper.
    
    CRITICAL STRATEGY FOR MISINFORMATION:
    We do NOT set a 'timelimit'. 
    Reason: 'Zombie Rumors' (e.g., a 2018 riot video shared as 2025) are common.
    We need the agent to find the fact-check from 3 years ago to prove the current claim is a recycle.
    """
    try:
        with DDGS() as ddgs:
            # Region 'wt-wt' (World) ensures we catch the original debunk source globally
            return list(ddgs.text(query, region="wt-wt", safesearch="off", max_results=max_results))
    except Exception as e:
        logger.error(f"[Debunker Agent] DDGS Internal Error: {e}")
        return []

# --- ASYNC WORKERS ---

async def search_fact_check_database(query: str, threshold: float) -> List[str]:
    """
    Uses Advanced Search Operators to scan multiple fact-check databases simultaneously.
    Query Format: "Bio Lab Leak (site:snopes.com OR site:altnews.in ...)"
    """
    evidence = []
    
    # Construct the OR operator string for all trusted domains
    # DuckDuckGo has a query length limit, so we batch if necessary, 
    # but usually 15-20 domains in OR works if keywords are short.
    site_operators = " OR ".join([f"site:{domain}" for domain in FACT_CHECK_DOMAINS])
    final_query = f"{query} ({site_operators})"
    
    logger.info(f"[Debunker Agent] Scanning Truth Squad Databases: {final_query[:100]}...")

    try:
        # Run synchronous DDGS in a separate thread
        results = await asyncio.to_thread(_perform_sync_ddg_search, final_query, 8)
        
        for res in results:
            title = res.get('title', '')
            url = res.get('href', '')
            snippet = res.get('body', '')
            
            # Deduce Source from URL for citation
            source = "Unknown"
            for domain in FACT_CHECK_DOMAINS:
                if domain in url:
                    source = domain.split('.')[0].title() 
                    break
            
            # Relevance Check
            similarity = calculate_similarity(query, title)
            
            # Context Check: Does the snippet explicitly mention it's false?
            # This helps boost confidence even if similarity is moderate.
            is_explicit_debunk = any(x in title.lower() or x in snippet.lower() for x in ["false", "fake", "hoax", "misleading", "old video", "doctored"])
            
            if similarity >= threshold or is_explicit_debunk:
                evidence.append(
                    f"Existing Fact-Check ({source}): \"{title}\" - {snippet[:200]}... [Link]({url})"
                )
            else:
                logger.debug(f"[Debunker] Skipped low relevance: {title}")
                    
    except Exception as e:
        logger.error(f"[Debunker Agent] Search Engine Error: {e}")
        
    return evidence

# --- MAIN ENTRY POINT ---

async def find_debunks(claim_text: str, threshold: float = 0.20) -> List[str]:
    """
    Orchestrates the search across the Global Fact-Checking Network.
    
    Args:
        claim_text: The user's query or rumor.
        threshold: Strictness (0.0 to 1.0). Lowered to 0.20 because debunk headlines 
                   often rephrase the rumor significantly (e.g. "No, aliens didn't land" vs "Aliens landed").
    """
    logger.info(f"[Debunker Agent] 🕵️‍♂️ Hunting for previous debunks on: '{claim_text}'")
    
    keywords = extract_keywords(claim_text)
    if not keywords or len(keywords) < 3:
        # Fallback: try searching exactly as is if keywords extraction failed
        keywords = claim_text

    # Execute Search
    findings = await search_fact_check_database(keywords, threshold)

    if not findings:
        logger.info("[Debunker Agent] ✅ No existing fact-checks found (Rumor might be new or true).")
        return ["No prior fact-checks found for this specific rumor on monitored IFCN databases."]

    logger.info(f"[Debunker Agent] ⚠️ Found {len(findings)} matching fact-checks. This is likely a recycled/known hoax.")
    return findings