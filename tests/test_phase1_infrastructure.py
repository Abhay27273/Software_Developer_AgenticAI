"""
Unit tests for Phase 1 queue infrastructure.

Tests for AsyncTaskQueue, WorkerPool, and PipelineManager.
"""

import asyncio
import pytest
from datetime import datetime
from utils.task_queue import AsyncTaskQueue, QueueTask
from utils.worker_pool import WorkerPool
from utils.pipeline_manager import PipelineManager


# ============================================================================
# AsyncTaskQueue Tests
# ============================================================================

@pytest.mark.asyncio
async def test_queue_task_priority_ordering():
    """Test that tasks are dequeued by priority."""
    queue = AsyncTaskQueue("TestQueue")
    
    # Add tasks with different priorities
    task_low = QueueTask(task_id="low", task_type="test", payload={}, priority=10)
    task_high = QueueTask(task_id="high", task_type="test", payload={}, priority=1)
    task_med = QueueTask(task_id="med", task_type="test", payload={}, priority=5)
    
    await queue.put(task_low)
    await queue.put(task_high)
    await queue.put(task_med)
    
    # Should dequeue in priority order: high, med, low
    first = await queue.get()
    assert first.task_id == "high"
    
    second = await queue.get()
    assert second.task_id == "med"
    
    third = await queue.get()
    assert third.task_id == "low"


@pytest.mark.asyncio
async def test_queue_task_done_metrics():
    """Test that task_done updates metrics correctly."""
    queue = AsyncTaskQueue("TestQueue")
    
    task = QueueTask(task_id="test1", task_type="test", payload={})
    await queue.put(task)
    
    retrieved_task = await queue.get()
    assert retrieved_task.task_id == "test1"
    assert queue.in_progress_count() == 1
    
    # Mark as done successfully
    queue.task_done(task.task_id, success=True, processing_time=1.5)
    
    assert queue.in_progress_count() == 0
    assert queue.processed_count == 1
    assert queue.failed_count == 0
    assert queue.total_processing_time == 1.5


@pytest.mark.asyncio
async def test_queue_task_retry():
    """Test task retry mechanism."""
    queue = AsyncTaskQueue("TestQueue")
    
    task = QueueTask(task_id="retry_test", task_type="test", payload={}, max_retries=3)
    await queue.put(task)
    
    retrieved_task = await queue.get()
    
    # Retry the task
    success = queue.task_retry(retrieved_task)
    assert success is True
    assert queue.retry_count == 1
    assert retrieved_task.retries == 1
    
    # Task should be re-enqueued
    await asyncio.sleep(0.1)  # Give time for re-enqueue
    assert queue.size() == 1


@pytest.mark.asyncio
async def test_queue_wait_until_empty():
    """Test waiting for queue to empty."""
    queue = AsyncTaskQueue("TestQueue")
    
    # Add tasks
    for i in range(3):
        task = QueueTask(task_id=f"task_{i}", task_type="test", payload={})
        await queue.put(task)
    
    # Start consuming tasks in background
    async def consume():
        for _ in range(3):
            task = await queue.get()
            await asyncio.sleep(0.1)
            queue.task_done(task.task_id, success=True)
    
    # Run consumer and wait
    consumer_task = asyncio.create_task(consume())
    await queue.wait_until_empty()
    
    assert queue.size() == 0
    assert queue.in_progress_count() == 0
    assert queue.processed_count == 3
    
    await consumer_task


@pytest.mark.asyncio
async def test_queue_get_stats():
    """Test queue statistics."""
    queue = AsyncTaskQueue("TestQueue")
    
    # Add and process some tasks
    for i in range(5):
        task = QueueTask(task_id=f"task_{i}", task_type="test", payload={})
        await queue.put(task)
        retrieved = await queue.get()
        queue.task_done(retrieved.task_id, success=i < 3, processing_time=0.5)
    
    stats = queue.get_stats()
    
    assert stats["name"] == "TestQueue"
    assert stats["processed"] == 3
    assert stats["failed"] == 2
    assert stats["total_processed"] == 5
    assert stats["success_rate"] == 60.0
    assert stats["total_processing_time"] == 2.5


# ============================================================================
# WorkerPool Tests
# ============================================================================

@pytest.mark.asyncio
async def test_worker_pool_basic_processing():
    """Test basic worker pool task processing."""
    queue = AsyncTaskQueue("TestQueue")
    processed_tasks = []
    
    async def mock_processor(task: QueueTask):
        """Mock task processor."""
        await asyncio.sleep(0.1)
        processed_tasks.append(task.task_id)
        return f"result_{task.task_id}"
    
    pool = WorkerPool(
        name="TestPool",
        worker_count=2,
        task_queue=queue,
        process_func=mock_processor
    )
    
    # Start pool
    await pool.start()
    assert pool.is_running is True
    
    # Add tasks
    for i in range(5):
        task = QueueTask(task_id=f"task_{i}", task_type="test", payload={})
        await queue.put(task)
    
    # Wait for completion
    await queue.wait_until_empty()
    await asyncio.sleep(0.2)  # Let workers finish
    
    # Stop pool
    await pool.stop()
    
    assert len(processed_tasks) == 5
    assert pool.total_processed == 5
    assert pool.total_failed == 0


@pytest.mark.asyncio
async def test_worker_pool_error_handling():
    """Test worker pool handles errors and retries."""
    queue = AsyncTaskQueue("TestQueue")
    attempts = []
    
    async def failing_processor(task: QueueTask):
        """Processor that fails first time."""
        attempts.append(task.task_id)
        if task.retries == 0:
            raise ValueError("Simulated failure")
        return "success"
    
    pool = WorkerPool(
        name="TestPool",
        worker_count=1,
        task_queue=queue,
        process_func=failing_processor
    )
    
    await pool.start()
    
    # Add task
    task = QueueTask(task_id="retry_task", task_type="test", payload={}, max_retries=2)
    await queue.put(task)
    
    # Wait for processing (initial + retry)
    await asyncio.sleep(1.0)
    
    await pool.stop()
    
    # Should have been attempted twice (initial + 1 retry)
    assert len(attempts) >= 2
    assert queue.retry_count >= 1


@pytest.mark.asyncio
async def test_worker_pool_output_queue():
    """Test worker pool can output to another queue."""
    input_queue = AsyncTaskQueue("InputQueue")
    output_queue = AsyncTaskQueue("OutputQueue")
    
    async def processor(task: QueueTask):
        """Processor that returns a new task."""
        return QueueTask(
            task_id=f"output_{task.task_id}",
            task_type="output",
            payload={"parent": task.task_id}
        )
    
    pool = WorkerPool(
        name="TestPool",
        worker_count=1,
        task_queue=input_queue,
        process_func=processor,
        output_queue=output_queue
    )
    
    await pool.start()
    
    # Add input task
    task = QueueTask(task_id="input_1", task_type="input", payload={})
    await input_queue.put(task)
    
    # Wait for processing
    await input_queue.wait_until_empty()
    await asyncio.sleep(0.2)
    
    # Check output queue
    assert output_queue.size() == 1
    output_task = await output_queue.get()
    assert output_task.task_id == "output_input_1"
    
    await pool.stop()


@pytest.mark.asyncio
async def test_worker_pool_graceful_shutdown():
    """Test worker pool graceful shutdown."""
    queue = AsyncTaskQueue("TestQueue")
    
    async def slow_processor(task: QueueTask):
        """Slow processor."""
        await asyncio.sleep(2.0)
        return "done"
    
    pool = WorkerPool(
        name="TestPool",
        worker_count=2,
        task_queue=queue,
        process_func=slow_processor
    )
    
    await pool.start()
    
    # Add tasks
    for i in range(3):
        task = QueueTask(task_id=f"task_{i}", task_type="test", payload={})
        await queue.put(task)
    
    # Let workers pick up tasks
    await asyncio.sleep(0.1)
    
    # Stop with short timeout (should cancel remaining)
    await pool.stop(graceful=True, timeout=1.0)
    
    assert pool.is_running is False


@pytest.mark.asyncio
async def test_worker_pool_scaling():
    """Test dynamic worker pool scaling."""
    queue = AsyncTaskQueue("TestQueue")
    
    async def mock_processor(task: QueueTask):
        await asyncio.sleep(0.1)
        return "done"
    
    pool = WorkerPool(
        name="TestPool",
        worker_count=2,
        task_queue=queue,
        process_func=mock_processor
    )
    
    await pool.start()
    assert pool.worker_count == 2
    assert len(pool.workers) == 2
    
    # Scale up
    await pool.scale(4)
    await asyncio.sleep(0.1)
    assert pool.worker_count == 4
    assert len(pool.workers) == 4
    
    # Scale down
    await pool.scale(1)
    await asyncio.sleep(0.1)
    assert pool.worker_count == 1
    
    await pool.stop()


# ============================================================================
# PipelineManager Tests
# ============================================================================

@pytest.mark.asyncio
async def test_pipeline_manager_initialization():
    """Test pipeline manager initialization."""
    pipeline = PipelineManager(
        dev_workers=2,
        qa_workers=1,
        fix_workers=1,
        deploy_workers=1
    )
    
    assert pipeline.dev_workers_count == 2
    assert pipeline.qa_workers_count == 1
    assert pipeline.dev_queue is not None
    assert pipeline.qa_queue is not None
    assert pipeline.fix_queue is not None
    assert pipeline.deploy_queue is not None


@pytest.mark.asyncio
async def test_pipeline_manager_start_stop():
    """Test pipeline lifecycle."""
    pipeline = PipelineManager(dev_workers=1, qa_workers=1, fix_workers=1, deploy_workers=1)
    
    # Mock agents
    class MockAgent:
        async def execute_task(self, **kwargs):
            await asyncio.sleep(0.1)
            return {"code": "test"}
        
        async def test_code(self, **kwargs):
            await asyncio.sleep(0.1)
            return {"tests_passed": True}
        
        async def deploy_code(self, **kwargs):
            await asyncio.sleep(0.1)
        
        async def fix_code(self, **kwargs):
            await asyncio.sleep(0.1)
            return {"code": "fixed"}
    
    pipeline.set_agents(MockAgent(), MockAgent(), MockAgent())
    
    # Start pipeline
    await pipeline.start()
    assert pipeline.is_running is True
    assert pipeline.dev_pool is not None
    
    # Stop pipeline
    await pipeline.stop(graceful=True, timeout=5.0)
    assert pipeline.is_running is False


@pytest.mark.asyncio
async def test_pipeline_manager_task_submission():
    """Test submitting tasks to pipeline."""
    pipeline = PipelineManager(dev_workers=1, qa_workers=1, fix_workers=1, deploy_workers=1)
    
    # Mock minimal agents
    class MockDevAgent:
        async def execute_task(self, **kwargs):
            return {"code": "print('hello')"}
    
    class MockQAAgent:
        async def test_code(self, **kwargs):
            return {"tests_passed": True}
    
    class MockOpsAgent:
        async def deploy_code(self, **kwargs):
            pass
    
    pipeline.set_agents(MockDevAgent(), MockQAAgent(), MockOpsAgent())
    
    await pipeline.start()
    
    # Submit task
    await pipeline.submit_dev_task(
        task_id="test_task",
        subtask={"id": "1", "title": "Test"},
        websocket=None,
        project_desc="Test project",
        plan={},
        priority=5
    )
    
    assert pipeline.total_tasks == 1
    assert pipeline.dev_queue.size() == 1
    
    await pipeline.stop(graceful=False)


@pytest.mark.asyncio
async def test_pipeline_manager_get_stats():
    """Test pipeline statistics."""
    pipeline = PipelineManager(dev_workers=2, qa_workers=1, fix_workers=1, deploy_workers=1)
    
    stats = pipeline.get_stats()
    
    assert stats["is_running"] is False
    assert stats["total_workers"] == 5
    assert stats["total_tasks"] == 0
    assert "queues" in stats
    assert "workers" in stats


@pytest.mark.asyncio
async def test_pipeline_manager_health_check():
    """Test pipeline health check."""
    pipeline = PipelineManager(dev_workers=1, qa_workers=1, fix_workers=1, deploy_workers=1)
    
    # Not running = not healthy
    assert pipeline.is_healthy() is False
    
    # Mock agents
    class MockAgent:
        async def execute_task(self, **kwargs):
            return {}
        async def test_code(self, **kwargs):
            return {"tests_passed": True}
        async def deploy_code(self, **kwargs):
            pass
    
    pipeline.set_agents(MockAgent(), MockAgent(), MockAgent())
    
    await pipeline.start()
    await asyncio.sleep(0.1)
    
    # Running with all workers = healthy
    assert pipeline.is_healthy() is True
    
    await pipeline.stop(graceful=False)


@pytest.mark.asyncio
async def test_pipeline_manager_scaling():
    """Test pipeline worker scaling."""
    pipeline = PipelineManager(dev_workers=2, qa_workers=1, fix_workers=1, deploy_workers=1)
    
    # Mock agents
    class MockAgent:
        async def execute_task(self, **kwargs):
            return {}
        async def test_code(self, **kwargs):
            return {"tests_passed": True}
        async def deploy_code(self, **kwargs):
            pass
    
    pipeline.set_agents(MockAgent(), MockAgent(), MockAgent())
    
    await pipeline.start()
    
    # Scale dev workers
    await pipeline.scale_workers(dev=4)
    assert pipeline.dev_workers_count == 4
    
    # Scale QA workers
    await pipeline.scale_workers(qa=3)
    assert pipeline.qa_workers_count == 3
    
    await pipeline.stop(graceful=False)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """Test complete pipeline with dev → QA → deploy flow."""
    pipeline = PipelineManager(dev_workers=1, qa_workers=1, fix_workers=1, deploy_workers=1)
    
    deployed_tasks = []
    
    # Mock agents that track execution
    class MockDevAgent:
        async def execute_task(self, subtask, **kwargs):
            await asyncio.sleep(0.1)
            return {"code": f"code_for_{subtask['id']}"}
    
    class MockQAAgent:
        async def test_code(self, subtask, **kwargs):
            await asyncio.sleep(0.1)
            return {"tests_passed": True, "subtask_id": subtask['id']}
    
    class MockOpsAgent:
        async def deploy_code(self, subtask, **kwargs):
            await asyncio.sleep(0.1)
            deployed_tasks.append(subtask['id'])
    
    pipeline.set_agents(MockDevAgent(), MockQAAgent(), MockOpsAgent())
    
    await pipeline.start()
    
    # Submit multiple tasks
    for i in range(3):
        await pipeline.submit_dev_task(
            task_id=f"task_{i}",
            subtask={"id": f"task_{i}", "title": f"Task {i}"},
            websocket=None,
            project_desc="Integration test",
            plan={},
            priority=5
        )
    
    # Wait for completion
    await asyncio.sleep(2.0)  # Give time for tasks to flow through pipeline
    
    await pipeline.stop(graceful=True, timeout=10.0)
    
    # Check that tasks were deployed
    assert len(deployed_tasks) >= 1  # At least some should complete
    assert pipeline.total_tasks == 3


if __name__ == "__main__":
    # Run tests with: pytest test_phase1_infrastructure.py -v
    print("Run tests with: pytest test_phase1_infrastructure.py -v")
