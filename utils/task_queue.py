"""
Async task queue for parallel processing pipeline.

This module provides a priority-based async queue with metrics tracking,
designed for managing Dev/QA/Fix tasks in a parallel pipeline.
"""

import asyncio
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueueTask:
    """
    Wrapper for tasks in the queue.
    
    Attributes:
        task_id: Unique identifier for the task
        task_type: Type of task ("dev", "qa", "fix", "deploy")
        payload: Task data (dict with task info, websocket, etc.)
        priority: Priority level (1=highest, 10=lowest)
        created_at: Timestamp when task was created
        started_at: Timestamp when processing started
        retries: Number of retry attempts
    """
    task_id: str
    task_type: str
    payload: Any
    priority: int = 5
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    retries: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """
        Comparison for priority queue: lower priority number = higher priority.
        If priorities are equal, compare by creation time (FIFO).
        """
        if self.priority == other.priority:
            return self.created_at < other.created_at
        return self.priority < other.priority
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "retries": self.retries
        }


class AsyncTaskQueue:
    """
    Async queue with priority support and comprehensive metrics.
    
    This queue manages tasks for parallel processing, tracking metrics
    like pending tasks, completed tasks, failed tasks, and processing times.
    """
    
    def __init__(self, name: str, max_size: int = 0):
        """
        Initialize async task queue.
        
        Args:
            name: Queue name for logging and identification
            max_size: Maximum queue size (0 = unlimited)
        """
        self.name = name
        self.queue = asyncio.PriorityQueue(maxsize=max_size)
        
        # Metrics
        self.processed_count = 0
        self.failed_count = 0
        self.retry_count = 0
        self.total_processing_time = 0.0
        
        # Track in-progress tasks
        self.in_progress = {}  # task_id -> QueueTask
        
        # Track task history for debugging
        self.completed_tasks = []
        self.failed_tasks = []
        
        logger.info(f"✨ {self.name}: Initialized (max_size={max_size})")
    
    async def put(self, task: QueueTask, timeout: Optional[float] = None):
        """
        Add task to queue.
        
        Args:
            task: QueueTask to enqueue
            timeout: Optional timeout in seconds
            
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
            asyncio.QueueFull: If queue is full and no timeout specified
        """
        try:
            if timeout:
                await asyncio.wait_for(
                    self.queue.put((task.priority, task)),
                    timeout=timeout
                )
            else:
                await self.queue.put((task.priority, task))
            
            logger.info(
                f"📥 {self.name}: Enqueued task {task.task_id} "
                f"(type: {task.task_type}, priority: {task.priority}, "
                f"queue_size: {self.queue.qsize()})"
            )
            
        except asyncio.TimeoutError:
            logger.error(
                f"⏱️ {self.name}: Timeout enqueueing task {task.task_id}"
            )
            raise
        except Exception as e:
            logger.error(
                f"❌ {self.name}: Failed to enqueue task {task.task_id}: {e}"
            )
            raise
    
    async def get(self, timeout: Optional[float] = None) -> QueueTask:
        """
        Get next task from queue.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            QueueTask: Next task to process
            
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        try:
            if timeout:
                priority, task = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=timeout
                )
            else:
                priority, task = await self.queue.get()
            
            # Mark as in progress
            task.started_at = datetime.now()
            self.in_progress[task.task_id] = task
            
            logger.debug(
                f"📤 {self.name}: Dequeued task {task.task_id} "
                f"(type: {task.task_type}, in_progress: {len(self.in_progress)})"
            )
            
            return task
            
        except asyncio.TimeoutError:
            logger.debug(f"⏱️ {self.name}: Get timeout (no tasks available)")
            raise
        except Exception as e:
            logger.error(f"❌ {self.name}: Failed to get task: {e}")
            raise
    
    def task_done(self, task_id: str, success: bool = True, processing_time: Optional[float] = None):
        """
        Mark task as completed.
        
        Args:
            task_id: ID of completed task
            success: Whether task completed successfully
            processing_time: Time taken to process (seconds)
        """
        task = self.in_progress.pop(task_id, None)
        
        if task is None:
            logger.warning(
                f"⚠️ {self.name}: task_done called for unknown task {task_id}"
            )
            return
        
        # Update metrics
        if success:
            self.processed_count += 1
            self.completed_tasks.append(task)
            logger.info(
                f"✅ {self.name}: Task {task_id} completed "
                f"(total_completed: {self.processed_count})"
            )
        else:
            self.failed_count += 1
            self.failed_tasks.append(task)
            logger.warning(
                f"❌ {self.name}: Task {task_id} failed "
                f"(total_failed: {self.failed_count})"
            )
        
        if processing_time:
            self.total_processing_time += processing_time
        
        # Mark queue task as done
        self.queue.task_done()
    
    def task_retry(self, task: QueueTask) -> bool:
        """
        Retry a failed task if retries available.
        
        Args:
            task: Task to retry
            
        Returns:
            bool: True if task was re-enqueued, False if max retries exceeded
        """
        task.retries += 1
        
        if task.retries <= task.max_retries:
            self.retry_count += 1
            self.in_progress.pop(task.task_id, None)
            
            # Re-enqueue with lower priority
            task.priority += 1
            asyncio.create_task(self.put(task))
            
            logger.info(
                f"🔄 {self.name}: Retrying task {task.task_id} "
                f"(attempt {task.retries}/{task.max_retries})"
            )
            return True
        else:
            logger.error(
                f"❌ {self.name}: Task {task.task_id} exceeded max retries "
                f"({task.max_retries})"
            )
            return False
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self.queue.empty()
    
    def size(self) -> int:
        """Get current queue size (pending tasks)."""
        return self.queue.qsize()
    
    def in_progress_count(self) -> int:
        """Get number of tasks currently being processed."""
        return len(self.in_progress)
    
    def get_stats(self) -> dict:
        """
        Get comprehensive queue statistics.
        
        Returns:
            dict: Queue statistics including counts, times, and rates
        """
        avg_processing_time = (
            self.total_processing_time / self.processed_count
            if self.processed_count > 0
            else 0.0
        )
        
        total_tasks = self.processed_count + self.failed_count
        success_rate = (
            (self.processed_count / total_tasks * 100)
            if total_tasks > 0
            else 0.0
        )
        
        return {
            "name": self.name,
            "pending": self.queue.qsize(),
            "in_progress": len(self.in_progress),
            "processed": self.processed_count,
            "failed": self.failed_count,
            "retries": self.retry_count,
            "total_processed": total_tasks,
            "success_rate": round(success_rate, 2),
            "avg_processing_time": round(avg_processing_time, 2),
            "total_processing_time": round(self.total_processing_time, 2)
        }
    
    def get_in_progress_tasks(self) -> list:
        """Get list of currently processing tasks."""
        return [task.to_dict() for task in self.in_progress.values()]
    
    def get_failed_tasks(self, limit: int = 10) -> list:
        """Get recent failed tasks for debugging."""
        return [task.to_dict() for task in self.failed_tasks[-limit:]]
    
    async def wait_until_empty(self, check_interval: float = 0.5):
        """
        Wait until queue is empty and no tasks are in progress.
        
        Args:
            check_interval: How often to check (seconds)
        """
        logger.info(f"⏳ {self.name}: Waiting for queue to empty...")
        
        while not self.is_empty() or self.in_progress_count() > 0:
            await asyncio.sleep(check_interval)
            logger.debug(
                f"⏳ {self.name}: Still waiting... "
                f"(pending: {self.size()}, in_progress: {self.in_progress_count()})"
            )
        
        logger.info(f"✅ {self.name}: Queue is now empty")
    
    def clear(self):
        """Clear all pending tasks (does not affect in-progress tasks)."""
        count = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                count += 1
            except asyncio.QueueEmpty:
                break
        
        logger.warning(f"🗑️ {self.name}: Cleared {count} pending tasks")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"AsyncTaskQueue(name='{self.name}', "
            f"pending={self.size()}, "
            f"in_progress={self.in_progress_count()}, "
            f"processed={self.processed_count}, "
            f"failed={self.failed_count})"
        )
