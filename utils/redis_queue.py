"""
Redis-Based Distributed Task Queue for Phase 2.2.

This module provides:
- Distributed task queue with Redis backend
- Priority-based task processing (HIGH/MEDIUM/LOW)
- Persistent task state across restarts
- Worker coordination and load balancing
- Dead letter queue for failed tasks
- Task TTL and expiration handling
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import redis.asyncio as redis
    from redis.asyncio import Redis, ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    Redis = None
    ConnectionPool = None

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Task states in the queue."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class RedisTask:
    """
    Task stored in Redis queue.
    
    Attributes:
        task_id: Unique task identifier
        task_type: Type of task (dev, qa, fix, deploy)
        payload: Task data
        priority: Task priority (0-3)
        state: Current task state
        retry_count: Number of retry attempts
        max_retries: Maximum retry attempts
        created_at: Task creation timestamp
        started_at: Task start timestamp
        completed_at: Task completion timestamp
        worker_id: ID of worker processing task
        error: Error message if failed
    """
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = TaskPriority.NORMAL.value
    state: str = TaskState.PENDING.value
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    worker_id: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        """Set creation timestamp if not provided."""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RedisTask':
        """Create task from dictionary."""
        return cls(**data)


class RedisTaskQueue:
    """
    Distributed task queue using Redis backend.
    
    Features:
    - Priority-based queuing (4 priority levels)
    - Persistent task state
    - Automatic retry with exponential backoff
    - Dead letter queue for failed tasks
    - Worker coordination
    - Task TTL and cleanup
    """
    
    def __init__(
        self,
        queue_name: str = "agentic_ai",
        redis_url: str = "redis://localhost:6379",
        max_retries: int = 3,
        task_ttl_seconds: int = 3600,
        enable_dlq: bool = True
    ):
        """
        Initialize Redis task queue.
        
        Args:
            queue_name: Base name for queue keys
            redis_url: Redis connection URL
            max_retries: Maximum retry attempts per task
            task_ttl_seconds: Task TTL in seconds (default: 1 hour)
            enable_dlq: Enable dead letter queue
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package not installed. "
                "Install with: pip install redis"
            )
        
        self.queue_name = queue_name
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.task_ttl = task_ttl_seconds
        self.enable_dlq = enable_dlq
        
        # Redis client and connection pool
        self.redis: Optional[Redis] = None
        self.pool: Optional[ConnectionPool] = None
        
        # Queue key patterns
        self.pending_key = f"{queue_name}:pending"
        self.processing_key = f"{queue_name}:processing"
        self.completed_key = f"{queue_name}:completed"
        self.failed_key = f"{queue_name}:failed"
        self.dlq_key = f"{queue_name}:dlq"
        self.task_key_prefix = f"{queue_name}:task:"
        self.worker_key_prefix = f"{queue_name}:worker:"
        
        # Statistics
        self.total_enqueued = 0
        self.total_completed = 0
        self.total_failed = 0
        
        logger.info(
            f"🔴 RedisTaskQueue: Initialized "
            f"(queue={queue_name}, max_retries={max_retries}, "
            f"ttl={task_ttl}s, dlq={enable_dlq})"
        )
    
    async def connect(self):
        """Establish Redis connection."""
        try:
            self.pool = ConnectionPool.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
            )
            self.redis = Redis(connection_pool=self.pool)
            
            # Test connection
            await self.redis.ping()
            
            logger.info(f"✅ Redis connected: {self.redis_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("🔴 Redis disconnected")
        if self.pool:
            await self.pool.disconnect()
    
    # ========================================================================
    # Task Enqueue/Dequeue
    # ========================================================================
    
    async def enqueue(
        self,
        task_id: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = TaskPriority.NORMAL.value
    ) -> RedisTask:
        """
        Add task to queue.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task
            payload: Task data
            priority: Task priority (0-3)
            
        Returns:
            Created RedisTask
        """
        task = RedisTask(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            max_retries=self.max_retries
        )
        
        # Store task data
        task_key = f"{self.task_key_prefix}{task_id}"
        await self.redis.setex(
            task_key,
            self.task_ttl,
            json.dumps(task.to_dict())
        )
        
        # Add to priority queue (sorted set by priority + timestamp)
        score = self._calculate_score(priority)
        await self.redis.zadd(self.pending_key, {task_id: score})
        
        self.total_enqueued += 1
        
        logger.info(
            f"📥 Task enqueued: {task_id} "
            f"(type={task_type}, priority={priority})"
        )
        
        return task
    
    async def dequeue(
        self,
        worker_id: str,
        timeout: float = 5.0
    ) -> Optional[RedisTask]:
        """
        Get next task from queue (blocking with timeout).
        
        Args:
            worker_id: Worker identifier
            timeout: Blocking timeout in seconds
            
        Returns:
            RedisTask or None if timeout
        """
        try:
            # Blocking pop from priority queue (highest priority first)
            result = await self.redis.bzpopmax(self.pending_key, timeout=timeout)
            
            if not result:
                return None
            
            _, task_id, _ = result
            
            # Get task data
            task_key = f"{self.task_key_prefix}{task_id}"
            task_data = await self.redis.get(task_key)
            
            if not task_data:
                logger.warning(f"⚠️ Task {task_id} not found in Redis")
                return None
            
            task = RedisTask.from_dict(json.loads(task_data))
            
            # Update task state
            task.state = TaskState.PROCESSING.value
            task.started_at = datetime.now().isoformat()
            task.worker_id = worker_id
            
            # Save updated task
            await self.redis.setex(
                task_key,
                self.task_ttl,
                json.dumps(task.to_dict())
            )
            
            # Move to processing set
            await self.redis.sadd(self.processing_key, task_id)
            
            logger.info(f"📤 Task dequeued: {task_id} (worker={worker_id})")
            
            return task
            
        except Exception as e:
            logger.error(f"❌ Error dequeuing task: {e}")
            return None
    
    async def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None):
        """
        Mark task as completed.
        
        Args:
            task_id: Task identifier
            result: Optional result data
        """
        task_key = f"{self.task_key_prefix}{task_id}"
        task_data = await self.redis.get(task_key)
        
        if not task_data:
            logger.warning(f"⚠️ Task {task_id} not found")
            return
        
        task = RedisTask.from_dict(json.loads(task_data))
        task.state = TaskState.COMPLETED.value
        task.completed_at = datetime.now().isoformat()
        
        if result:
            task.payload['result'] = result
        
        # Save updated task
        await self.redis.setex(
            task_key,
            self.task_ttl,
            json.dumps(task.to_dict())
        )
        
        # Move to completed set
        await self.redis.srem(self.processing_key, task_id)
        await self.redis.sadd(self.completed_key, task_id)
        
        self.total_completed += 1
        
        logger.info(f"✅ Task completed: {task_id}")
    
    async def fail_task(
        self,
        task_id: str,
        error: str,
        retry: bool = True
    ):
        """
        Mark task as failed and optionally retry.
        
        Args:
            task_id: Task identifier
            error: Error message
            retry: Whether to retry task
        """
        task_key = f"{self.task_key_prefix}{task_id}"
        task_data = await self.redis.get(task_key)
        
        if not task_data:
            logger.warning(f"⚠️ Task {task_id} not found")
            return
        
        task = RedisTask.from_dict(json.loads(task_data))
        task.retry_count += 1
        task.error = error
        
        # Remove from processing
        await self.redis.srem(self.processing_key, task_id)
        
        # Retry if under limit
        if retry and task.retry_count < task.max_retries:
            task.state = TaskState.PENDING.value
            task.started_at = None
            task.worker_id = None
            
            # Save updated task
            await self.redis.setex(
                task_key,
                self.task_ttl,
                json.dumps(task.to_dict())
            )
            
            # Re-enqueue with exponential backoff
            delay = 2 ** task.retry_count  # 2, 4, 8 seconds
            score = self._calculate_score(task.priority) + delay
            await self.redis.zadd(self.pending_key, {task_id: score})
            
            logger.warning(
                f"⚠️ Task failed, retrying: {task_id} "
                f"(attempt {task.retry_count}/{task.max_retries})"
            )
        else:
            # Move to DLQ or failed set
            task.state = TaskState.DEAD_LETTER.value if self.enable_dlq else TaskState.FAILED.value
            
            await self.redis.setex(
                task_key,
                self.task_ttl,
                json.dumps(task.to_dict())
            )
            
            if self.enable_dlq:
                await self.redis.sadd(self.dlq_key, task_id)
                logger.error(f"❌ Task moved to DLQ: {task_id}")
            else:
                await self.redis.sadd(self.failed_key, task_id)
                logger.error(f"❌ Task failed permanently: {task_id}")
            
            self.total_failed += 1
    
    # ========================================================================
    # Queue Management
    # ========================================================================
    
    async def get_queue_size(self) -> Dict[str, int]:
        """
        Get size of each queue.
        
        Returns:
            Dictionary with queue sizes
        """
        return {
            'pending': await self.redis.zcard(self.pending_key),
            'processing': await self.redis.scard(self.processing_key),
            'completed': await self.redis.scard(self.completed_key),
            'failed': await self.redis.scard(self.failed_key),
            'dlq': await self.redis.scard(self.dlq_key) if self.enable_dlq else 0
        }
    
    async def get_task(self, task_id: str) -> Optional[RedisTask]:
        """
        Get task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            RedisTask or None
        """
        task_key = f"{self.task_key_prefix}{task_id}"
        task_data = await self.redis.get(task_key)
        
        if not task_data:
            return None
        
        return RedisTask.from_dict(json.loads(task_data))
    
    async def list_tasks(
        self,
        state: Optional[TaskState] = None,
        limit: int = 100
    ) -> List[RedisTask]:
        """
        List tasks by state.
        
        Args:
            state: Filter by state (None = all)
            limit: Maximum number of tasks
            
        Returns:
            List of RedisTask
        """
        if state == TaskState.PENDING:
            task_ids = await self.redis.zrange(self.pending_key, 0, limit - 1)
        elif state == TaskState.PROCESSING:
            task_ids = await self.redis.smembers(self.processing_key)
        elif state == TaskState.COMPLETED:
            task_ids = await self.redis.smembers(self.completed_key)
        elif state == TaskState.FAILED:
            task_ids = await self.redis.smembers(self.failed_key)
        elif state == TaskState.DEAD_LETTER:
            task_ids = await self.redis.smembers(self.dlq_key)
        else:
            # Get all tasks (expensive!)
            pattern = f"{self.task_key_prefix}*"
            task_ids = []
            async for key in self.redis.scan_iter(match=pattern, count=limit):
                task_id = key.replace(self.task_key_prefix, "")
                task_ids.append(task_id)
        
        tasks = []
        for task_id in task_ids[:limit]:
            task = await self.get_task(task_id)
            if task:
                tasks.append(task)
        
        return tasks
    
    async def retry_dlq_task(self, task_id: str) -> bool:
        """
        Retry a task from DLQ.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was retried
        """
        task = await self.get_task(task_id)
        if not task:
            return False
        
        # Reset task state
        task.state = TaskState.PENDING.value
        task.retry_count = 0
        task.error = None
        task.started_at = None
        task.completed_at = None
        task.worker_id = None
        
        # Save updated task
        task_key = f"{self.task_key_prefix}{task_id}"
        await self.redis.setex(
            task_key,
            self.task_ttl,
            json.dumps(task.to_dict())
        )
        
        # Remove from DLQ and re-enqueue
        await self.redis.srem(self.dlq_key, task_id)
        score = self._calculate_score(task.priority)
        await self.redis.zadd(self.pending_key, {task_id: score})
        
        logger.info(f"🔄 Task retried from DLQ: {task_id}")
        return True
    
    async def clear_completed(self, older_than_seconds: int = 3600):
        """
        Clear completed tasks older than threshold.
        
        Args:
            older_than_seconds: Age threshold in seconds
        """
        task_ids = await self.redis.smembers(self.completed_key)
        threshold = datetime.now() - timedelta(seconds=older_than_seconds)
        
        cleared = 0
        for task_id in task_ids:
            task = await self.get_task(task_id)
            if task and task.completed_at:
                completed_at = datetime.fromisoformat(task.completed_at)
                if completed_at < threshold:
                    # Delete task
                    task_key = f"{self.task_key_prefix}{task_id}"
                    await self.redis.delete(task_key)
                    await self.redis.srem(self.completed_key, task_id)
                    cleared += 1
        
        logger.info(f"🗑️ Cleared {cleared} completed tasks")
        return cleared
    
    # ========================================================================
    # Utilities
    # ========================================================================
    
    def _calculate_score(self, priority: int) -> float:
        """
        Calculate Redis sorted set score for priority + timestamp.
        
        Higher priority = lower score (processed first)
        """
        timestamp = datetime.now().timestamp()
        # Priority weight (higher priority = lower score)
        priority_weight = (3 - priority) * 1000000
        return priority_weight + timestamp
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with stats
        """
        sizes = await self.get_queue_size()
        
        return {
            'queue_name': self.queue_name,
            'total_enqueued': self.total_enqueued,
            'total_completed': self.total_completed,
            'total_failed': self.total_failed,
            'pending': sizes['pending'],
            'processing': sizes['processing'],
            'completed': sizes['completed'],
            'failed': sizes['failed'],
            'dlq': sizes['dlq'],
            'success_rate': (
                self.total_completed / max(self.total_enqueued, 1) * 100
            )
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RedisTaskQueue("
            f"queue={self.queue_name}, "
            f"enqueued={self.total_enqueued}, "
            f"completed={self.total_completed}, "
            f"failed={self.total_failed})"
        )
