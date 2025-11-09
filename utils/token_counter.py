"""
Token usage tracking for cost optimization and monitoring.
"""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Track token usage for a single LLM call."""
    agent: str
    prompt_name: str
    prompt_tokens: int = 0
    response_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used in this call."""
        return self.prompt_tokens + self.response_tokens
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "agent": self.agent,
            "prompt_name": self.prompt_name,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "total_tokens": self.total_tokens,
            "timestamp": self.timestamp.isoformat()
        }


class TokenCounter:
    """Global token usage tracker."""
    
    def __init__(self):
        self.usages: List[TokenUsage] = []
        self._total_prompt_tokens = 0
        self._total_response_tokens = 0
    
    def add_usage(self, usage: TokenUsage):
        """Record a token usage entry."""
        self.usages.append(usage)
        self._total_prompt_tokens += usage.prompt_tokens
        self._total_response_tokens += usage.response_tokens
        
        logger.info(
            f"📊 Token Usage | {usage.agent}/{usage.prompt_name}: "
            f"Prompt={usage.prompt_tokens}, Response={usage.response_tokens}, "
            f"Total={usage.total_tokens}"
        )
    
    def add_from_metadata(self, agent: str, prompt_name: str, prompt_chars: int, response_chars: int):
        """
        Add usage from character counts (approximate token estimation).
        Rule of thumb: 1 token ≈ 4 characters for English text.
        """
        prompt_tokens = prompt_chars // 4
        response_tokens = response_chars // 4
        
        usage = TokenUsage(
            agent=agent,
            prompt_name=prompt_name,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens
        )
        self.add_usage(usage)
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used across all calls."""
        return self._total_prompt_tokens + self._total_response_tokens
    
    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens used."""
        return self._total_prompt_tokens
    
    @property
    def total_response_tokens(self) -> int:
        """Total response tokens used."""
        return self._total_response_tokens
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        agent_stats = {}
        for usage in self.usages:
            if usage.agent not in agent_stats:
                agent_stats[usage.agent] = {"prompt": 0, "response": 0, "total": 0, "calls": 0}
            agent_stats[usage.agent]["prompt"] += usage.prompt_tokens
            agent_stats[usage.agent]["response"] += usage.response_tokens
            agent_stats[usage.agent]["total"] += usage.total_tokens
            agent_stats[usage.agent]["calls"] += 1
        
        return {
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_response_tokens": self._total_response_tokens,
            "total_tokens": self.total_tokens,
            "agent_breakdown": agent_stats,
            "total_calls": len(self.usages)
        }
    
    def print_summary(self):
        """Print a formatted summary of token usage."""
        stats = self.get_stats()
        
        logger.info("=" * 60)
        logger.info("📊 TOKEN USAGE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Calls: {stats['total_calls']}")
        logger.info(f"Total Tokens: {stats['total_tokens']:,}")
        logger.info(f"  - Prompt: {stats['total_prompt_tokens']:,}")
        logger.info(f"  - Response: {stats['total_response_tokens']:,}")
        logger.info("-" * 60)
        
        for agent, data in stats['agent_breakdown'].items():
            logger.info(f"{agent}:")
            logger.info(f"  Calls: {data['calls']}")
            logger.info(f"  Tokens: {data['total']:,} (prompt: {data['prompt']:,}, response: {data['response']:,})")
        
        logger.info("=" * 60)
    
    def reset(self):
        """Reset all counters."""
        self.usages.clear()
        self._total_prompt_tokens = 0
        self._total_response_tokens = 0
        logger.info("🔄 Token counter reset")


# Global singleton
_token_counter: Optional[TokenCounter] = None


def get_token_counter() -> TokenCounter:
    """Get or create global token counter."""
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
        logger.info("✨ Token counter initialized")
    return _token_counter


def reset_token_counter():
    """Reset the global token counter."""
    global _token_counter
    if _token_counter is not None:
        _token_counter.reset()
