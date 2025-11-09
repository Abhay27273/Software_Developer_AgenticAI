"""
Circuit Breaker pattern implementation for pipeline reliability.

Prevents cascading failures by automatically pausing operations
when error rates exceed threshold.

States:
- CLOSED: Normal operation
- OPEN: Errors exceeded threshold, blocking all requests
- HALF_OPEN: Testing if system recovered
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Blocking requests (too many errors)
    HALF_OPEN = "half_open"    # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: float = 0.5  # 50% error rate triggers open
    success_threshold: int = 3      # 3 successes to close from half-open
    timeout_seconds: float = 30.0   # Wait 30s before trying half-open
    window_size: int = 10           # Track last 10 requests
    min_requests: int = 5           # Min requests before evaluating


class CircuitBreaker:
    """
    Circuit Breaker pattern for preventing cascading failures.
    
    Automatically transitions between states:
    1. CLOSED → OPEN: Error rate exceeds threshold
    2. OPEN → HALF_OPEN: After timeout period
    3. HALF_OPEN → CLOSED: Enough successful requests
    4. HALF_OPEN → OPEN: Any failure detected
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Breaker name (for logging)
            config: Configuration (uses defaults if None)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State
        self.state = CircuitState.CLOSED
        self.last_state_change = datetime.now()
        
        # Statistics (sliding window)
        self.recent_results: list[bool] = []  # True = success, False = failure
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        
        # Totals
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.times_opened = 0
        self.times_half_opened = 0
        
        # Callbacks
        self.on_open_callbacks: list[Callable] = []
        self.on_close_callbacks: list[Callable] = []
        self.on_half_open_callbacks: list[Callable] = []
        
        logger.info(
            f"🔌 CircuitBreaker '{name}': Initialized "
            f"(failure_threshold={self.config.failure_threshold}, "
            f"timeout={self.config.timeout_seconds}s)"
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            # Check if timeout elapsed
            if self._should_attempt_reset():
                await self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN"
                )
        
        # Execute function
        self.total_requests += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
            
        except Exception as e:
            await self._record_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt reset.
        
        Returns:
            True if should try transitioning to half-open
        """
        elapsed = datetime.now() - self.last_state_change
        return elapsed.total_seconds() >= self.config.timeout_seconds
    
    async def _record_success(self):
        """Record successful request."""
        self.total_successes += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        
        # Add to sliding window
        self.recent_results.append(True)
        if len(self.recent_results) > self.config.window_size:
            self.recent_results.pop(0)
        
        logger.debug(
            f"✅ {self.name}: Success recorded "
            f"(consecutive: {self.consecutive_successes})"
        )
        
        # State transitions based on success
        if self.state == CircuitState.HALF_OPEN:
            if self.consecutive_successes >= self.config.success_threshold:
                await self._transition_to_closed()
    
    async def _record_failure(self):
        """Record failed request."""
        self.total_failures += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        
        # Add to sliding window
        self.recent_results.append(False)
        if len(self.recent_results) > self.config.window_size:
            self.recent_results.pop(0)
        
        logger.debug(
            f"❌ {self.name}: Failure recorded "
            f"(consecutive: {self.consecutive_failures})"
        )
        
        # State transitions based on failure
        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open → reopen circuit
            await self._transition_to_open()
        
        elif self.state == CircuitState.CLOSED:
            # Check if should open circuit
            if self._should_open():
                await self._transition_to_open()
    
    def _should_open(self) -> bool:
        """
        Check if circuit should open based on error rate.
        
        Returns:
            True if should open circuit
        """
        # Need minimum requests before evaluating
        if len(self.recent_results) < self.config.min_requests:
            return False
        
        # Calculate error rate
        failures = self.recent_results.count(False)
        error_rate = failures / len(self.recent_results)
        
        should_open = error_rate >= self.config.failure_threshold
        
        if should_open:
            logger.warning(
                f"⚠️ {self.name}: Error rate {error_rate:.1%} "
                f"exceeds threshold {self.config.failure_threshold:.1%}"
            )
        
        return should_open
    
    async def _transition_to_open(self):
        """Transition to OPEN state."""
        if self.state == CircuitState.OPEN:
            return  # Already open
        
        old_state = self.state
        self.state = CircuitState.OPEN
        self.last_state_change = datetime.now()
        self.times_opened += 1
        
        logger.error(
            f"🔴 CircuitBreaker '{self.name}': {old_state.value} → OPEN "
            f"(error_rate: {self.get_error_rate():.1%}, "
            f"times_opened: {self.times_opened})"
        )
        
        # Trigger callbacks
        for callback in self.on_open_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self)
                else:
                    callback(self)
            except Exception as e:
                logger.error(f"❌ Open callback error: {e}")
    
    async def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        if self.state != CircuitState.OPEN:
            return  # Only transition from OPEN
        
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = datetime.now()
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.times_half_opened += 1
        
        logger.warning(
            f"🟡 CircuitBreaker '{self.name}': OPEN → HALF_OPEN "
            f"(testing recovery, times: {self.times_half_opened})"
        )
        
        # Trigger callbacks
        for callback in self.on_half_open_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self)
                else:
                    callback(self)
            except Exception as e:
                logger.error(f"❌ Half-open callback error: {e}")
    
    async def _transition_to_closed(self):
        """Transition to CLOSED state."""
        if self.state == CircuitState.CLOSED:
            return  # Already closed
        
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.last_state_change = datetime.now()
        
        logger.info(
            f"🟢 CircuitBreaker '{self.name}': {old_state.value} → CLOSED "
            f"(recovered, success_rate: {self.get_success_rate():.1%})"
        )
        
        # Trigger callbacks
        for callback in self.on_close_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self)
                else:
                    callback(self)
            except Exception as e:
                logger.error(f"❌ Close callback error: {e}")
    
    def get_error_rate(self) -> float:
        """
        Get current error rate.
        
        Returns:
            Error rate as decimal (0.0 to 1.0)
        """
        if not self.recent_results:
            return 0.0
        
        failures = self.recent_results.count(False)
        return failures / len(self.recent_results)
    
    def get_success_rate(self) -> float:
        """
        Get current success rate.
        
        Returns:
            Success rate as decimal (0.0 to 1.0)
        """
        return 1.0 - self.get_error_rate()
    
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == CircuitState.OPEN
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN
    
    async def reset(self):
        """Manually reset circuit to CLOSED state."""
        logger.info(f"🔄 CircuitBreaker '{self.name}': Manual reset")
        self.recent_results.clear()
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        await self._transition_to_closed()
    
    def on_open(self, callback: Callable):
        """Register callback for when circuit opens."""
        self.on_open_callbacks.append(callback)
    
    def on_close(self, callback: Callable):
        """Register callback for when circuit closes."""
        self.on_close_callbacks.append(callback)
    
    def on_half_open(self, callback: Callable):
        """Register callback for when circuit goes half-open."""
        self.on_half_open_callbacks.append(callback)
    
    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics.
        
        Returns:
            Dictionary with breaker metrics
        """
        return {
            'name': self.name,
            'state': self.state.value,
            'error_rate': round(self.get_error_rate() * 100, 2),
            'success_rate': round(self.get_success_rate() * 100, 2),
            'total_requests': self.total_requests,
            'total_successes': self.total_successes,
            'total_failures': self.total_failures,
            'consecutive_successes': self.consecutive_successes,
            'consecutive_failures': self.consecutive_failures,
            'times_opened': self.times_opened,
            'times_half_opened': self.times_half_opened,
            'window_size': len(self.recent_results),
            'last_state_change': self.last_state_change.isoformat()
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"CircuitBreaker("
            f"name='{self.name}', "
            f"state={self.state.value}, "
            f"error_rate={self.get_error_rate():.1%})"
        )


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass
