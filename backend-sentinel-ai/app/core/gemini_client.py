import logging
import asyncio
import google.generativeai as genai
from google.api_core import exceptions
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiRotationManager:
    """
    Singleton manager that handles API Key rotation on Rate Limit (429) errors.
    It wraps the standard Gemini calls with a retry mechanism that switches identities
    when one key is exhausted.
    """
    def __init__(self):
        # Parse keys from CSV string or single value
        # Example: "key1,key2,key3" -> ['key1', 'key2', 'key3']
        raw_keys = settings.GEMINI_API_KEYS
        self.keys = [k.strip() for k in raw_keys.split(',') if k.strip()]
        
        if not self.keys:
            raise ValueError("No Gemini API keys found in configuration. Please check your .env file.")

        self.current_index = 0
        self._lock = asyncio.Lock() # Prevents race conditions during rotation
        self._configure_current_key()

    def _configure_current_key(self):
        """Configures the global genai object with the active key."""
        current_key = self.keys[self.current_index]
        # Mask key for secure logging
        masked_key = f"{current_key[:4]}...{current_key[-4:]}"
        logger.info(f"[Gemini Manager] 🔑 Active Identity: Key #{self.current_index + 1} ({masked_key})")
        genai.configure(api_key=current_key)

    async def _rotate_key(self):
        """Rotates to the next key in the pool thread-safely."""
        async with self._lock:
            # Move to next index (Loop back to 0 if at end)
            prev_index = self.current_index
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            logger.warning(
                f"[Gemini Manager] ⚠️ Rate Limit Hit on Key #{prev_index + 1}. "
                f"Rotating to Key #{self.current_index + 1}..."
            )
            self._configure_current_key()

    async def generate_content_async(self, model_name: str, prompt: str, **kwargs):
        """
        Wrapper for model.generate_content_async that handles retries and rotation.
        Args:
            model_name (str): The model to use (e.g. settings.GEMINI_EXTRACTION_MODEL)
            prompt (str): The prompt string
            **kwargs: Additional args like generation_config, safety_settings, etc.
        """
        # We try as many times as we have keys to ensure we find a working one.
        # We add +1 just to be safe in case of a race condition, effectively allowing one full loop.
        max_retries = len(self.keys)
        
        for attempt in range(max_retries + 1):
            try:
                # Instantiate model (it uses the globally configured key)
                model = genai.GenerativeModel(model_name)
                
                # Execute Request
                response = await model.generate_content_async(prompt, **kwargs)
                return response

            except exceptions.ResourceExhausted:
                # 429 Error caught - Trigger Rotation
                if attempt < max_retries:
                    await self._rotate_key()
                    # Small backoff to allow config to propagate and prevent rapid-fire loops
                    await asyncio.sleep(0.5) 
                else:
                    # All keys exhausted
                    logger.critical("[Gemini Manager] ❌ FATAL: All API keys in the pool are rate-limited.")
                    raise

            except Exception as e:
                # Non-rate-limit errors (e.g. Bad Request, Safety Block) are raised immediately
                logger.error(f"[Gemini Manager] API Error: {e}")
                raise e

# Initialize Singleton to be imported by services
gemini_client = GeminiRotationManager()