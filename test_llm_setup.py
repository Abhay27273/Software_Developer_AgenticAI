import asyncio
import pytest
from utils.llm_setup import ask_llm, ask_llm_streaming

# Configure pytest-asyncio to use function scope
pytestmark = pytest.mark.asyncio

async def test_basic_llm_response():
    user_prompt = "What's the capital of France?"
    response = await ask_llm(user_prompt=user_prompt)
    
    assert isinstance(response, str)
    assert "Paris" in response or "paris" in response.lower()
    print("\n✅ test_basic_llm_response passed.")

async def test_llm_streaming():
    user_prompt = "List three programming languages"
    system_prompt = "You are an expert software developer"
    
    chunks = []
    error = None
    
    try:
        async with asyncio.timeout(30):  # Set timeout for streaming
            async for chunk in ask_llm_streaming(user_prompt=user_prompt, system_prompt=system_prompt):
                if chunk and isinstance(chunk, str):
                    print(chunk, end='', flush=True)
                    chunks.append(chunk)
    except asyncio.TimeoutError:
        error = "Streaming timed out"
    except Exception as e:
        error = str(e)
    
    # Handle any errors
    if error:
        pytest.fail(f"Streaming failed: {error}")
    
    final_output = ''.join(chunks)
    assert len(final_output) > 0, "Expected non-empty response"
    
    # More flexible language detection
    programming_languages = [
        "python", "java", "javascript", "c++", "ruby", 
        "typescript", "go", "rust", "php", "swift"
    ]
    found_languages = [lang for lang in programming_languages if lang in final_output.lower()]
    assert len(found_languages) > 0, f"No programming languages found in: {final_output}"
    
    print("\n✅ test_llm_streaming passed with languages: {found_languages}")
