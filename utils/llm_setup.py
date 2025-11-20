"""
Async LLM Setup Utility for Agentic AI System
Integrates Gemini API for use by planner, dev, qa agents.
"""

import os
import json
import logging
import asyncio
import time
from typing import Optional, Callable, Dict, Any, AsyncGenerator
from dotenv import load_dotenv
import google.generativeai as genai
from asyncio import Lock, Semaphore
from google.api_core.exceptions import GoogleAPICallError

# Load .env variables
load_dotenv()
MODEL = os.getenv("MODEL", "gemini-2.5-flash")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LLMError(Exception):
    """Custom error for LLM issues."""
    pass

class LLMClient:
    """Manages Gemini LLM async usage across all agents with rate limiting."""

    def __init__(self):
        """Initializes the client and its own instance-specific model cache."""
        # Check all required environment variables
        required_vars = {
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
            "MODEL": os.getenv("MODEL", "gemini-2.5-pro")
        }
        
        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            raise LLMError(f"⚠️ Missing environment variables: {', '.join(missing)}")
        
        self.api_key = required_vars["GEMINI_API_KEY"]
        genai.configure(api_key=self.api_key)
        self.default_model = required_vars["MODEL"]
        
        self._model_cache: Dict[str, Any] = {}
        self._model_lock = Lock()
        
        # Rate limiting to prevent "too_many_pings" errors
        self._request_semaphore = Semaphore(1)  # Max 1 concurrent request (reduced for API stability)
        self._min_request_interval = 5.0  # 5 seconds between requests (increased for API stability)
        self._last_request_time = 0.0
        self._rate_limit_lock = Lock()
        
        logger.info(f"✅ LLMClient initialized with default model: {self.default_model}")
        logger.info(f"🚦 Rate limiting: Max 1 concurrent request, 5.0s interval")

    async def _get_model(self, model_name: str, temperature: Optional[float] = None):
        """Load/reuse model instance from the client's private cache."""
        cache_key = f"{model_name}_{temperature}"
        async with self._model_lock:
            if cache_key not in self._model_cache:
                logger.info(f"📦 Loading model {model_name} with temp={temperature}")
                config = genai.GenerationConfig(temperature=temperature) if temperature else None
                self._model_cache[cache_key] = genai.GenerativeModel(model_name, generation_config=config)
            return self._model_cache[cache_key]

    async def ask_llm(self, user_prompt: str,
                      system_prompt: Optional[str] = None,
                      model: Optional[str] = None,
                      temperature: Optional[float] = None,
                      callback: Optional[Callable[[str], None]] = None,
                      max_retries: int = 3,
                      validate_json: bool = False,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """Single-shot async response for all agents."""
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        model_to_use = model or self.default_model
        call_meta = metadata or {}
        prompt_chars = len(full_prompt)
        logger.info(
            "LLM request initiated",
            extra={
                "agent": call_meta.get("agent"),
                "prompt_name": call_meta.get("prompt_name"),
                "model": model_to_use,
                "prompt_chars": prompt_chars,
                "temperature": temperature,
                "streaming": False
            }
        )

        for attempt in range(max_retries):
            try:
                if callback:
                    # support sync or async callback
                    if asyncio.iscoroutinefunction(callback):
                        await callback(f"🚀 Requesting from {model_to_use} (attempt {attempt+1})")
                    else:
                        callback(f"🚀 Requesting from {model_to_use} (attempt {attempt+1})")

                model_instance = await self._get_model(model_to_use, temperature)
                response = await model_instance.generate_content_async(full_prompt)

                if not response or not getattr(response, "text", None):
                    raise LLMError("Empty response from LLM")

                text = response.text.strip()

                # Optional JSON validation for callers that require strict JSON output
                if validate_json:
                    try:
                        json.loads(text)
                    except json.JSONDecodeError as je:
                        raise LLMError(f"Invalid JSON: {je}")

                response_chars = len(text)

                if callback:
                    if asyncio.iscoroutinefunction(callback):
                        await callback("✅ LLM response received.")
                    else:
                        callback("✅ LLM response received.")
                logger.info(
                    "LLM request completed",
                    extra={
                        "agent": call_meta.get("agent"),
                        "prompt_name": call_meta.get("prompt_name"),
                        "model": model_to_use,
                        "prompt_chars": prompt_chars,
                        "response_chars": response_chars,
                        "temperature": temperature,
                        "streaming": False
                    }
                )
                return text

            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"❌ Attempt {attempt+1} failed: {e}")
                if callback:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(f"⚠️ Retry {attempt+1} failed: {str(e)}")
                    else:
                        callback(f"⚠️ Retry {attempt+1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    # Use fallback only for non-streaming failures
                    fallback = self.get_fallback_response(user_prompt, expects_json=validate_json)
                    logger.warning(
                        "LLM request fell back after retries",
                        extra={
                            "agent": call_meta.get("agent"),
                            "prompt_name": call_meta.get("prompt_name"),
                            "model": model_to_use,
                            "prompt_chars": prompt_chars,
                            "response_chars": len(fallback),
                            "temperature": temperature,
                            "streaming": False
                        }
                    )
                    return fallback

        # Should theoretically not be reached if max_retries is > 0 and handles failure
        fallback = self.get_fallback_response(user_prompt, expects_json=validate_json)
        logger.warning(
            "LLM request hit unexpected fallback",
            extra={
                "agent": call_meta.get("agent"),
                "prompt_name": call_meta.get("prompt_name"),
                "model": model_to_use,
                "prompt_chars": prompt_chars,
                "response_chars": len(fallback),
                "temperature": temperature,
                "streaming": False
            }
        )
        return fallback

    async def ask_llm_streaming(self, user_prompt: str,
                          system_prompt: Optional[str] = None,
                          model: Optional[str] = None,
                          temperature: Optional[float] = None,
                          callback: Optional[Callable[[str], None]] = None,
                          max_retries: int = 3,
                          metadata: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """Stream output from Gemini API with real-time callbacks and rate limiting.

        Notes:
        - This implementation is defensive: chunk.text can raise ValueError if the response part is missing.
          We skip such chunks and continue streaming instead of crashing the whole generator.
        - The function supports sync and async callbacks.
        - Rate limiting prevents "too_many_pings" errors from Gemini API.
        """
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        model_to_use = model or self.default_model
        call_meta = metadata or {}
        prompt_chars = len(full_prompt)
        logger.info(
            "LLM streaming request initiated",
            extra={
                "agent": call_meta.get("agent"),
                "prompt_name": call_meta.get("prompt_name"),
                "model": model_to_use,
                "prompt_chars": prompt_chars,
                "temperature": temperature,
                "streaming": True
            }
        )

        # Apply rate limiting
        async with self._request_semaphore:
            async with self._rate_limit_lock:
                now = time.time()
                elapsed = now - self._last_request_time
                if elapsed < self._min_request_interval:
                    wait_time = self._min_request_interval - elapsed
                    logger.debug(f"🚦 Rate limit: waiting {wait_time:.2f}s before request")
                    await asyncio.sleep(wait_time)
                self._last_request_time = time.time()

            for attempt in range(max_retries):
                try:
                    total_response_chars = 0
                    model_instance = await self._get_model(model_to_use, temperature)
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(f"🌊 Starting stream from {model_to_use}...")
                        else:
                            callback(f"🌊 Starting stream from {model_to_use}...")

                    # request streaming response
                    stream = await model_instance.generate_content_async(full_prompt, stream=True)

                    async for chunk in stream:
                        # Defensive access: chunk.text may raise ValueError if no valid Part is present.
                        try:
                            text = getattr(chunk, "text", None)
                            if text is None:
                                # attempt to access other fallback fields (best-effort)
                                text = getattr(chunk, "candidate", None)
                                if text is None:
                                    # No usable text in this chunk; skip it.
                                    continue
                        except ValueError as ve:
                            # Known gemini SDK behavior: skip invalid/empty chunk
                            logger.warning("LLM streaming returned a chunk without a valid text Part: %s", ve)
                            continue
                        except Exception as e:
                            logger.exception("Unexpected error accessing chunk.text: %s", e)
                            continue

                        # deliver chunk to caller via callback and generator
                        try:
                            if callback:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(text)
                                else:
                                    callback(text)
                        except Exception:
                            logger.exception("Callback raised while handling stream chunk; continuing.")

                        total_response_chars += len(text)
                        yield text

                    # stream completed successfully
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback("\n✅ Streaming completed.")
                        else:
                            callback("\n✅ Streaming completed.")
                    logger.info(
                        "LLM streaming request completed",
                        extra={
                            "agent": call_meta.get("agent"),
                            "prompt_name": call_meta.get("prompt_name"),
                            "model": model_to_use,
                            "prompt_chars": prompt_chars,
                            "response_chars": total_response_chars,
                            "temperature": temperature,
                            "streaming": True
                        }
                    )
                    return  # successful completion

                except (GoogleAPICallError, ValueError) as e:
                    error_str = str(e)
                    is_503_error = "503" in error_str or "Connection reset" in error_str or "IOCP" in error_str
                    backoff_time = (2 ** attempt) * (3 if is_503_error else 1)  # 3x backoff for 503 errors
                    
                    logger.exception("Streaming attempt %d failed with API/ValueError: %s", attempt + 1, e)
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(f"\n❌ Streaming attempt {attempt + 1} failed: {e}")
                        else:
                            callback(f"\n❌ Streaming attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        logger.warning(f"🔄 Retrying in {backoff_time}s (attempt {attempt + 2}/{max_retries})...")
                        await asyncio.sleep(backoff_time)
                    else:
                        logger.warning(
                            "LLM streaming request failed after retries",
                            extra={
                                "agent": call_meta.get("agent"),
                                "prompt_name": call_meta.get("prompt_name"),
                                "model": model_to_use,
                                "prompt_chars": prompt_chars,
                                "temperature": temperature,
                                "streaming": True,
                                "error": str(e)
                            }
                        )
                        raise LLMError(f"LLM streaming failed after {max_retries} attempts: {e}")
                except Exception as e:
                    error_str = str(e)
                    is_503_error = "503" in error_str or "Connection reset" in error_str or "IOCP" in error_str
                    backoff_time = (2 ** attempt) * (3 if is_503_error else 1)  # 3x backoff for 503 errors
                    
                    logger.exception("Streaming attempt %d failed unexpectedly: %s", attempt + 1, e)
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(f"\n❌ Streaming attempt {attempt + 1} failed: {e}")
                        else:
                            callback(f"\n❌ Streaming attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        logger.warning(f"🔄 Retrying in {backoff_time}s (attempt {attempt + 2}/{max_retries})...")
                        await asyncio.sleep(backoff_time)
                    else:
                        raise LLMError(f"LLM streaming failed after {max_retries} attempts: {e}")

    def get_fallback_response(self, prompt: str, expects_json: bool = False) -> str:
        """Fallback response in case LLM fails to generate content for non-streaming calls."""
        logger.warning("⚠️ Using fallback due to LLM failure.")
        
        if expects_json or "json" in prompt.lower():
            return json.dumps({
                "message": "Fallback response",
                "error": "LLM generation failed"
            }, indent=2)
        
        return "I apologize, but I encountered an error. Please try again."

# --- Singleton LLM Client for Global Access ---

_llm_client: Optional[LLMClient] = None
_client_lock = Lock()
_last_loop: Optional[asyncio.AbstractEventLoop] = None

async def get_client() -> LLMClient:
    """
    Get the LLM client, creating a new one if the event loop has changed.
    This makes the client safe to use with test runners like pytest-asyncio.
    """
    global _llm_client, _last_loop
    
    current_loop = asyncio.get_running_loop()
    
    if _llm_client is None or _last_loop != current_loop:
        async with _client_lock:
            # Double-check inside the lock to prevent race conditions
            if _llm_client is None or _last_loop != current_loop:
                logger.info("🌀 Initializing new LLMClient for the current event loop.")
                _llm_client = LLMClient()
                _last_loop = current_loop
                
    return _llm_client

async def ask_llm(*args, **kwargs) -> str:
    """Convenience wrapper for the LLMClient's ask_llm method."""
    client = await get_client()
    return await client.ask_llm(*args, **kwargs)

async def ask_llm_streaming(*args, **kwargs) -> AsyncGenerator[str, None]:
    """Convenience wrapper for the LLMClient's ask_llm_streaming method."""
    client = await get_client()
    async for chunk in client.ask_llm_streaming(*args, **kwargs):
        yield chunk