"""
Async LLM Setup Utility for Agentic AI System
Integrates Gemini API for use by planner, dev, qa agents.
"""

import os
import json
import logging
import asyncio
from typing import Optional, Callable, Dict, Any, AsyncGenerator
from dotenv import load_dotenv
import google.generativeai as genai
from asyncio import Lock

# Load .env variables
load_dotenv()
MODEL = os.getenv("MODEL", "gemini-1.5-pro-latest")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LLMError(Exception):
    """Custom error for LLM issues."""
    pass

class LLMClient:
    """Manages Gemini LLM async usage across all agents."""

    def __init__(self):
        """Initializes the client and its own instance-specific model cache."""
        # Check all required environment variables
        required_vars = {
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
            "MODEL": os.getenv("MODEL", "gemini-1.5-pro-latest")
        }
        
        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            raise LLMError(f"⚠️ Missing environment variables: {', '.join(missing)}")
        
        self.api_key = required_vars["GEMINI_API_KEY"]
        genai.configure(api_key=self.api_key)
        self.default_model = required_vars["MODEL"]
        
        # ✅ **FIX:** Model cache and lock are now instance variables.
        self._model_cache: Dict[str, Any] = {}
        self._model_lock = Lock()
        
        logger.info(f"✅ LLMClient initialized with default model: {self.default_model}")

    async def _get_model(self, model_name: str, temperature: Optional[float] = None):
        """Load/reuse model instance from the client's private cache."""
        cache_key = f"{model_name}_{temperature}"
        # ✅ **FIX:** Use the instance's lock and cache.
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
                      max_retries: int = 3) -> str:
        """Single-shot async response for all agents."""
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        model_to_use = model or self.default_model

        for attempt in range(max_retries):
            try:
                if callback:
                    callback(f"🚀 Requesting from {model_to_use} (attempt {attempt+1})")

                model_instance = await self._get_model(model_to_use, temperature)
                response = await model_instance.generate_content_async(full_prompt)

                if not response or not response.text:
                    raise LLMError("Empty response from LLM")

                text = response.text.strip()

                if "json" in user_prompt.lower():
                    import json
                    try:
                        json.loads(text)
                    except json.JSONDecodeError as je:
                        raise LLMError(f"Invalid JSON: {je}")

                if callback:
                    callback("✅ LLM response received.")
                return text

            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"❌ Attempt {attempt+1} failed: {e}")
                if callback:
                    callback(f"⚠️ Retry {attempt+1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    return self.get_fallback_code_response(user_prompt)

        return self.get_fallback_code_response(user_prompt)

    async def ask_llm_streaming(self, user_prompt: str,
                          system_prompt: Optional[str] = None,
                          model: Optional[str] = None,
                          temperature: Optional[float] = None,
                          callback: Optional[Callable[[str], None]] = None,
                          max_retries: int = 3) -> AsyncGenerator[str, None]:
        """Stream output from Gemini API with real-time callbacks."""
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        model_to_use = model or self.default_model

        for attempt in range(max_retries):
            try:
                model_instance = await self._get_model(model_to_use, temperature)
                if callback:
                    callback(f"🌊 Starting stream from {model_to_use}...")

                stream = await model_instance.generate_content_async(full_prompt, stream=True)
                buffer = []

                async for chunk in stream:
                    if chunk.text:
                        buffer.append(chunk.text)
                        if callback:
                            callback(chunk.text)
                        yield chunk.text

                if "json" in user_prompt.lower():
                    try:
                        json.loads("".join(buffer))
                    except json.JSONDecodeError as je:
                        yield f"\n❌ JSON Error: {je}"
                        continue

                if callback:
                    callback("\n✅ Streaming completed.")
                return

            except Exception as e:
                logger.error(f"Streaming attempt {attempt + 1} failed: {e}")
                if callback:
                    callback(f"\n❌ Streaming attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    yield self.get_fallback_code_response(user_prompt)

    def get_fallback_code_response(self, prompt: str) -> str:
        """Fallback in case LLM fails to generate content."""
        logger.warning("⚠️ Using fallback due to LLM failure.")
        
        if "json" in prompt.lower():
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