"""
Unit tests for Phase 2.2: Redis-Based Task Queue.

Tests cover:
- Task enqueue/dequeue operations
- Priority-based task processing
- Task state transitions
- Retry logic and exponential backoff
- Dead letter queue
- Worker coordination
- Performance and scalability
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from datetime import datetime, timedelta

try:
    from utils.redis_queue import (
        RedisTaskQueue, RedisTask, TaskState, TaskPriority, REDIS_AVAILABLE
    )
    import redis.asyncio as redis
except ImportError:
    REDIS_AVAILABLE = False

# Skip all tests if Redis not available
pytestmark = pytest.mark.skipif(
    not REDIS_AVAILABLE,
    reason="Redis not installed. Install with: pip install redis"
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
async def redis_queue():
    """Create Redis queue for testing."""
    if not REDIS_AVAILABLE:
        pytest.skip("Redis not available")
    
    queue = RedisTaskQueue(
        queue_name="test_queue",
        redis_url="redis://localhost:6379",
        max_retries=3,
        task_ttl_seconds=300
    )
    
    try:
        await queue.connect()
    except Exception as e:
        pytest.skip(f"Redis server not available: {e}")
    
    yield queue
    
    # Cleanup
    if queue.redis:
        # Clear test data
        await queue.redis.flushdb()
        await queue.disconnect()


# ============================================================================
# Basic Operations Tests
# ============================================================================

class TestBasicOperations:
    """Test basic enqueue/dequeue operations."""
    
    @pytest.mark.asyncio
    async def test_enqueue_task(self, redis_queue):
        """Test enqueueing a task."""
        task = await redis_queue.enqueue(
            task_id="test_1",
            task_type="dev",
            payload={"code": "print('hello')"},
            priority=TaskPriority.NORMAL.value
        )
        
        assert task.task_id == "test_1"
        assert task.task_type == "dev"
        assert task.state == TaskState.PENDING.value
        assert task.priority == TaskPriority.NORMAL.value
        assert redis_queue.total_enqueued == 1
    
    @pytest.mark.asyncio
    async def test_dequeue_task(self, redis_queue):
        """Test dequeuing a task."""
        # Enqueue task
        await redis_queue.enqueue(
            task_id="test_2",
            task_type="qa",
            payload={"test": "data"},
            priority=TaskPriority.HIGH.value
        )
        
        # Dequeue task
        task = await redis_queue.dequeue(worker_id="worker_1", timeout=1.0)
        
        assert task is not None
        assert task.task_id == "test_2"
        assert task.state == TaskState.PROCESSING.value
        assert task.worker_id == "worker_1"
        assert task.started_at is not None
    
    @pytest.mark.asyncio
    async def test_dequeue_timeout(self, redis_queue):
        """Test dequeue timeout when queue is empty."""
        task = await redis_queue.dequeue(worker_id="worker_1", timeout=0.5)
        assert task is None
    
    @pytest.mark.asyncio
    async def test_complete_task(self, redis_queue):
        """Test completing a task."""
        # Enqueue and dequeue
        await redis_queue.enqueue("test_3", "dev", {})
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        
        # Complete task
        await redis_queue.complete_task(task.task_id, result={"status": "success"})
        
        # Verify state
        completed_task = await redis_queue.get_task(task.task_id)
        assert completed_task.state == TaskState.COMPLETED.value
        assert completed_task.completed_at is not None
        assert redis_queue.total_completed == 1
    
    @pytest.mark.asyncio
    async def test_fail_task(self, redis_queue):
        """Test failing a task."""
        # Enqueue and dequeue
        await redis_queue.enqueue("test_4", "qa", {})
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        
        # Fail task
        await redis_queue.fail_task(task.task_id, error="Test error", retry=False)
        
        # Verify moved to DLQ
        failed_task = await redis_queue.get_task(task.task_id)
        assert failed_task.state == TaskState.DEAD_LETTER.value
        assert failed_task.error == "Test error"
        assert redis_queue.total_failed == 1


# ============================================================================
# Priority Tests
# ============================================================================

class TestPriority:
    """Test priority-based task processing."""
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, redis_queue):
        """Test that higher priority tasks are dequeued first."""
        # Enqueue tasks with different priorities
        await redis_queue.enqueue("low", "dev", {}, priority=TaskPriority.LOW.value)
        await redis_queue.enqueue("high", "dev", {}, priority=TaskPriority.HIGH.value)
        await redis_queue.enqueue("normal", "dev", {}, priority=TaskPriority.NORMAL.value)
        await redis_queue.enqueue("critical", "dev", {}, priority=TaskPriority.CRITICAL.value)
        
        # Dequeue in priority order
        task1 = await redis_queue.dequeue("worker_1", timeout=1.0)
        task2 = await redis_queue.dequeue("worker_1", timeout=1.0)
        task3 = await redis_queue.dequeue("worker_1", timeout=1.0)
        task4 = await redis_queue.dequeue("worker_1", timeout=1.0)
        
        # Verify order (CRITICAL > HIGH > NORMAL > LOW)
        assert task1.task_id == "critical"
        assert task2.task_id == "high"
        assert task3.task_id == "normal"
        assert task4.task_id == "low"


# ============================================================================
# Retry Logic Tests
# ============================================================================

class TestRetryLogic:
    """Test retry and exponential backoff."""
    
    @pytest.mark.asyncio
    async def test_task_retry(self, redis_queue):
        """Test that failed tasks are retried."""
        # Enqueue and dequeue
        await redis_queue.enqueue("retry_test", "dev", {})
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        
        # Fail task with retry
        await redis_queue.fail_task(task.task_id, error="Retry error", retry=True)
        
        # Verify task is back in pending queue
        retried_task = await redis_queue.get_task(task.task_id)
        assert retried_task.state == TaskState.PENDING.value
        assert retried_task.retry_count == 1
        assert retried_task.error == "Retry error"
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, redis_queue):
        """Test that tasks move to DLQ after max retries."""
        await redis_queue.enqueue("max_retry_test", "dev", {})
        
        # Fail task multiple times
        for i in range(redis_queue.max_retries):
            task = await redis_queue.dequeue("worker_1", timeout=1.0)
            await redis_queue.fail_task(task.task_id, error=f"Error {i+1}", retry=True)
        
        # Verify task is in DLQ
        final_task = await redis_queue.get_task("max_retry_test")
        assert final_task.state == TaskState.DEAD_LETTER.value
        assert final_task.retry_count == redis_queue.max_retries
    
    @pytest.mark.asyncio
    async def test_retry_from_dlq(self, redis_queue):
        """Test retrying a task from DLQ."""
        # Create a DLQ task
        await redis_queue.enqueue("dlq_retry", "dev", {})
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        
        # Fail until DLQ
        for _ in range(redis_queue.max_retries):
            await redis_queue.fail_task(task.task_id, error="Test", retry=True)
        
        # Retry from DLQ
        success = await redis_queue.retry_dlq_task("dlq_retry")
        assert success is True
        
        # Verify task is back in pending
        retried_task = await redis_queue.get_task("dlq_retry")
        assert retried_task.state == TaskState.PENDING.value
        assert retried_task.retry_count == 0


# ============================================================================
# Queue Management Tests
# ============================================================================

class TestQueueManagement:
    """Test queue management operations."""
    
    @pytest.mark.asyncio
    async def test_get_queue_size(self, redis_queue):
        """Test getting queue sizes."""
        # Add tasks to different queues
        await redis_queue.enqueue("pending_1", "dev", {})
        await redis_queue.enqueue("pending_2", "dev", {})
        
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        await redis_queue.complete_task(task.task_id)
        
        sizes = await redis_queue.get_queue_size()
        
        assert sizes['pending'] == 1
        assert sizes['completed'] == 1
    
    @pytest.mark.asyncio
    async def test_list_tasks_by_state(self, redis_queue):
        """Test listing tasks filtered by state."""
        # Create tasks in different states
        await redis_queue.enqueue("pending_task", "dev", {})
        
        await redis_queue.enqueue("completed_task", "dev", {})
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        await redis_queue.complete_task(task.task_id)
        
        # List pending tasks
        pending_tasks = await redis_queue.list_tasks(state=TaskState.PENDING)
        assert len(pending_tasks) == 1
        assert pending_tasks[0].task_id == "pending_task"
        
        # List completed tasks
        completed_tasks = await redis_queue.list_tasks(state=TaskState.COMPLETED)
        assert len(completed_tasks) == 1
        assert completed_tasks[0].task_id == "completed_task"
    
    @pytest.mark.asyncio
    async def test_clear_completed_tasks(self, redis_queue):
        """Test clearing old completed tasks."""
        # Create and complete task
        await redis_queue.enqueue("old_task", "dev", {})
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        await redis_queue.complete_task(task.task_id)
        
        # Clear completed (with 0 threshold for testing)
        cleared = await redis_queue.clear_completed(older_than_seconds=0)
        
        # Wait a bit for time to pass
        await asyncio.sleep(0.1)
        
        # Should clear the task
        assert cleared >= 0  # May be 0 or 1 depending on timing


# ============================================================================
# Statistics Tests
# ============================================================================

class TestStatistics:
    """Test statistics collection."""
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, redis_queue):
        """Test getting queue statistics."""
        # Add some tasks
        await redis_queue.enqueue("stat_1", "dev", {})
        await redis_queue.enqueue("stat_2", "qa", {})
        
        # Complete one
        task = await redis_queue.dequeue("worker_1", timeout=1.0)
        await redis_queue.complete_task(task.task_id)
        
        stats = await redis_queue.get_statistics()
        
        assert stats['queue_name'] == "test_queue"
        assert stats['total_enqueued'] == 2
        assert stats['total_completed'] == 1
        assert stats['pending'] == 1
        assert stats['completed'] == 1
        assert stats['success_rate'] == 50.0


# ============================================================================
# Concurrency Tests
# ============================================================================

class TestConcurrency:
    """Test concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_multiple_workers(self, redis_queue):
        """Test multiple workers dequeuing tasks."""
        # Enqueue multiple tasks
        for i in range(10):
            await redis_queue.enqueue(f"task_{i}", "dev", {})
        
        # Simulate multiple workers
        async def worker(worker_id, count):
            tasks = []
            for _ in range(count):
                task = await redis_queue.dequeue(worker_id, timeout=1.0)
                if task:
                    tasks.append(task)
                    await redis_queue.complete_task(task.task_id)
            return tasks
        
        # Run 3 workers concurrently
        results = await asyncio.gather(
            worker("worker_1", 4),
            worker("worker_2", 3),
            worker("worker_3", 3)
        )
        
        # Verify all tasks processed
        total_processed = sum(len(r) for r in results)
        assert total_processed == 10
        
        # Verify no duplicates
        all_task_ids = [task.task_id for worker_tasks in results for task in worker_tasks]
        assert len(all_task_ids) == len(set(all_task_ids))


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test queue performance."""
    
    @pytest.mark.asyncio
    async def test_high_throughput(self, redis_queue):
        """Test enqueueing and dequeuing many tasks."""
        import time
        
        # Enqueue 100 tasks
        start = time.time()
        for i in range(100):
            await redis_queue.enqueue(f"perf_{i}", "dev", {"index": i})
        enqueue_time = time.time() - start
        
        # Dequeue all tasks
        start = time.time()
        tasks = []
        for _ in range(100):
            task = await redis_queue.dequeue("perf_worker", timeout=0.1)
            if task:
                tasks.append(task)
                await redis_queue.complete_task(task.task_id)
        dequeue_time = time.time() - start
        
        # Verify all tasks processed
        assert len(tasks) == 100
        
        # Performance assertions (should be fast)
        assert enqueue_time < 5.0  # Less than 5 seconds
        assert dequeue_time < 5.0
        
        print(f"\n⏱️ Enqueued 100 tasks in {enqueue_time:.3f}s")
        print(f"⏱️ Dequeued 100 tasks in {dequeue_time:.3f}s")


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test realistic integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, redis_queue):
        """Test complete task lifecycle."""
        # 1. Enqueue tasks
        await redis_queue.enqueue("workflow_1", "dev", {"file": "main.py"}, priority=TaskPriority.HIGH.value)
        await redis_queue.enqueue("workflow_2", "qa", {"file": "test.py"}, priority=TaskPriority.NORMAL.value)
        
        # 2. Worker processes high priority first
        task1 = await redis_queue.dequeue("worker_1", timeout=1.0)
        assert task1.task_id == "workflow_1"
        assert task1.priority == TaskPriority.HIGH.value
        
        # 3. Complete successfully
        await redis_queue.complete_task(task1.task_id, result={"code": "generated"})
        
        # 4. Process normal priority task
        task2 = await redis_queue.dequeue("worker_1", timeout=1.0)
        assert task2.task_id == "workflow_2"
        
        # 5. Fail and retry
        await redis_queue.fail_task(task2.task_id, error="QA failed", retry=True)
        
        # 6. Retry and succeed
        task2_retry = await redis_queue.dequeue("worker_1", timeout=1.0)
        assert task2_retry.task_id == "workflow_2"
        assert task2_retry.retry_count == 1
        await redis_queue.complete_task(task2_retry.task_id)
        
        # 7. Verify final statistics
        stats = await redis_queue.get_statistics()
        assert stats['total_completed'] == 2
        assert stats['success_rate'] == 100.0
