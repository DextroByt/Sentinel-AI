import json
import logging
import re
from typing import List, Dict, Any
from datetime import datetime, timezone
# [UPDATED] We only import types now, not the main library for configuration
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.core.config import settings
# [NEW] Import the rotation manager
from app.core.gemini_client import gemini_client

logger = logging.getLogger(__name__)

# [REMOVED] The global genai.configure() block is no longer needed here.
# The GeminiRotationManager handles this internally.

# --- Cognitive Architecture: Rumor Extraction Prompt ---
# [UPDATED] Tuned for "Rumor Decomposition" - Separating Signal from Noise
EXTRACTION_PROMPT = """
You are an expert Intelligence Analyst for Sentinel AI.
Your task is to process raw user reports or news snippets and extract STRUCTURED INTELLIGENCE.

CURRENT DATE: {current_date}

INPUT TEXT:
"{article_text}"

OBJECTIVES:
1. **SEPARATE SIGNAL FROM NOISE:** Users often add context like "My uncle forwarded this" or "Is this true?". Ignore that. Focus on the EVENT or CLAIM.
2. **EXTRACT THE CORE RUMOR:** What exactly is being alleged? (e.g., "Dam burst", "Virus leak", "Riot started").
3. **PINPOINT LOCATION:** Identify the specific City, District, or Region. If vague, use "Unknown".
4. **DETECT URGENCY:** If the text implies immediate danger (death, fire, mob), ensure the claim reflects that.

OUTPUT REQUIREMENT:
Return a single, valid JSON object with this exact structure:
{{
  "claims": [
    {{ "text": "Specific rumor text...", "location": "City, Country" }}
  ]
}}
"""

def _clean_json_text(raw_text: str) -> str:
    """Sanitizes LLM output to ensure valid JSON."""
    cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()

async def extract_claims(article_text: str) -> List[Dict[str, str]]:
    """
    Uses Gemini 2.5 Flash via the Rotation Manager to parse unstructured text.
    Returns: [{'text': '...', 'location': '...'}]
    """
    # Basic validation
    if not article_text or len(article_text.strip()) < 5:
        return []

    logger.info(f"Extracting structured intelligence from: '{article_text[:30]}...'")
    
    try:
        # [UPDATED] Replaced direct model instantiation with client call
        safe_text = article_text[:30000] # Truncate to safe limit
        current_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        response = await gemini_client.generate_content_async(
            model_name=settings.GEMINI_EXTRACTION_MODEL,
            prompt=EXTRACTION_PROMPT.format(
                article_text=safe_text,
                current_date=current_date_str
            ),
            generation_config={
                "response_mime_type": "application/json", 
                "temperature": 0.1 # Low temp for precision
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }
        )

        raw_output = response.text
        cleaned_json = _clean_json_text(raw_output)
        
        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError:
            logger.warning("Gemini returned invalid JSON during extraction.")
            return []

        raw_claims = data.get("claims", [])
        valid_claims = []
        
        for c in raw_claims:
            if isinstance(c, dict) and "text" in c:
                # Post-processing cleanup
                clean_text = c["text"].strip()
                clean_loc = c.get("location", "Unknown").strip()
                
                # Filter out empty results
                if len(clean_text) > 5:
                    valid_claims.append({
                        "text": clean_text,
                        "location": clean_loc
                    })
        
        if valid_claims:
            logger.info(f"✅ Extracted {len(valid_claims)} claim(s). Top: {valid_claims[0]['text']} ({valid_claims[0]['location']})")
        else:
            logger.warning("❌ No valid claims could be extracted.")

        return valid_claims

    except Exception as e:
        logger.error(f"Gemini Extraction Critical Failure: {e}")
        return []