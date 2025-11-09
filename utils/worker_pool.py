"""
Worker pool for parallel task processing.

This module provides a configurable worker pool that processes tasks
from an AsyncTaskQueue, with graceful lifecycle management and error handling.
"""

import asyncio
from typing import Callable, Optional, Any
import logging
from datetime import datetime
from utils.task_queue import AsyncTaskQueue, QueueTask

logger = logging.getLogger(__name__)


class WorkerPool:
    """
    Manages a pool of async workers processing tasks from a queue.
    
    Each worker runs independently, pulling tasks from the queue and
    processing them with the provided callback function.
    """
    
    def __init__(
        self,
        name: str,
        worker_count: int,
        task_queue: AsyncTaskQueue,
        process_func: Callable,
        output_queue: Optional[AsyncTaskQueue] = None
    ):
        """
        Initialize worker pool.
        
        Args:
            name: Pool name for logging
            worker_count: Number of concurrent workers
            task_queue: Input queue to pull tasks from
            process_func: Async function to process tasks
                         Signature: async def process(task: QueueTask) -> Any
            output_queue: Optional queue to push results to
        """
        self.name = name
        self.worker_count = worker_count
        self.task_queue = task_queue
        self.process_func = process_func
        self.output_queue = output_queue
        
        # Worker management
        self.workers = []
        self.is_running = False
        self.stop_event = asyncio.Event()
        
        # Metrics
        self.start_time = None
        self.total_processed = 0
        self.total_failed = 0
        self.total_processing_time = 0.0
        
        logger.info(
            f"🏗️ {self.name}: Initialized worker pool with {worker_count} workers"
        )
    
    async def _worker(self, worker_id: int):
        """
        Individual worker coroutine.
        
        Continuously pulls tasks from queue and processes them until stopped.
        
        Args:
            worker_id: Unique ID for this worker
        """
        logger.info(f"👷 {self.name} Worker-{worker_id}: Started")
        
        while not self.stop_event.is_set():
            try:
                # Get task with timeout so we can check stop_event periodically
                try:
                    task = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # No task available, check if we should stop
                    continue
                
                logger.debug(
                    f"👷 {self.name} Worker-{worker_id}: Processing task {task.task_id}"
                )
                
                # Process the task
                processing_start = datetime.now()
                success = False
                result = None
                
                try:
                    result = await self.process_func(task)
                    success = True
                    self.total_processed += 1
                    
                    logger.info(
                        f"✅ {self.name} Worker-{worker_id}: "
                        f"Completed task {task.task_id}"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"❌ {self.name} Worker-{worker_id}: "
                        f"Failed processing task {task.task_id}: {e}",
                        exc_info=True
                    )
                    
                    # Attempt retry if available
                    if self.task_queue.task_retry(task):
                        logger.info(
                            f"🔄 {self.name} Worker-{worker_id}: "
                            f"Task {task.task_id} re-queued for retry"
                        )
                    else:
                        self.total_failed += 1
                
                # Calculate processing time
                processing_time = (datetime.now() - processing_start).total_seconds()
                self.total_processing_time += processing_time
                
                # Mark task as done in queue
                self.task_queue.task_done(
                    task.task_id,
                    success=success,
                    processing_time=processing_time
                )
                
                # If successful and output queue exists, enqueue result
                if success and result is not None and self.output_queue:
                    try:
                        await self.output_queue.put(result)
                        logger.debug(
                            f"📤 {self.name} Worker-{worker_id}: "
                            f"Sent result to output queue"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ {self.name} Worker-{worker_id}: "
                            f"Failed to enqueue result: {e}"
                        )
                
            except asyncio.CancelledError:
                # Worker is being cancelled (graceful shutdown)
                logger.info(
                    f"🛑 {self.name} Worker-{worker_id}: Cancelled"
                )
                break
                
            except Exception as e:
                # Unexpected error in worker loop
                logger.error(
                    f"❌ {self.name} Worker-{worker_id}: "
                    f"Unexpected error in worker loop: {e}",
                    exc_info=True
                )
                # Continue running despite error
                await asyncio.sleep(1)
        
        logger.info(
            f"👋 {self.name} Worker-{worker_id}: Stopped "
            f"(processed: {self.total_processed}, failed: {self.total_failed})"
        )
    
    async def start(self):
        """
        Start all workers in the pool.
        
        Workers will begin processing tasks from the queue immediately.
        """
        if self.is_running:
            logger.warning(f"⚠️ {self.name}: Worker pool already running")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        self.stop_event.clear()
        
        # Create worker tasks
        self.workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.worker_count)
        ]
        
        logger.info(
            f"🚀 {self.name}: Started {self.worker_count} workers"
        )
    
    async def stop(self, graceful: bool = True, timeout: float = 30.0):
        """
        Stop all workers in the pool.
        
        Args:
            graceful: If True, wait for current tasks to complete
                     If False, cancel workers immediately
            timeout: Maximum time to wait for graceful shutdown (seconds)
        """
        if not self.is_running:
            logger.warning(f"⚠️ {self.name}: Worker pool not running")
            return
        
        logger.info(
            f"🛑 {self.name}: Stopping worker pool "
            f"(graceful={graceful}, timeout={timeout}s)"
        )
        
        # Signal workers to stop
        self.stop_event.set()
        
        if graceful:
            # Wait for workers to finish current tasks
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.workers, return_exceptions=True),
                    timeout=timeout
                )
                logger.info(f"✅ {self.name}: All workers stopped gracefully")
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏱️ {self.name}: Graceful shutdown timeout, "
                    f"cancelling remaining workers"
                )
                # Cancel any remaining workers
                for worker in self.workers:
                    if not worker.done():
                        worker.cancel()
                # Wait for cancellations
                await asyncio.gather(*self.workers, return_exceptions=True)
        else:
            # Cancel all workers immediately
            for worker in self.workers:
                worker.cancel()
            await asyncio.gather(*self.workers, return_exceptions=True)
            logger.info(f"✅ {self.name}: All workers cancelled")
        
        self.is_running = False
        self.workers = []
        
        # Log final statistics
        stats = self.get_stats()
        logger.info(
            f"📊 {self.name}: Final stats - "
            f"processed: {stats['total_processed']}, "
            f"failed: {stats['total_failed']}, "
            f"avg_time: {stats['avg_processing_time']}s, "
            f"uptime: {stats['uptime']}s"
        )
    
    async def wait_until_complete(self):
        """
        Wait until all queued tasks are processed and workers are idle.
        
        This does NOT stop the workers - they will continue running.
        """
        logger.info(
            f"⏳ {self.name}: Waiting for all tasks to complete..."
        )
        
        await self.task_queue.wait_until_empty()
        
        logger.info(
            f"✅ {self.name}: All tasks completed"
        )
    
    def get_stats(self) -> dict:
        """
        Get worker pool statistics.
        
        Returns:
            dict: Statistics including processed counts, times, and rates
        """
        uptime = (
            (datetime.now() - self.start_time).total_seconds()
            if self.start_time
            else 0.0
        )
        
        avg_processing_time = (
            self.total_processing_time / self.total_processed
            if self.total_processed > 0
            else 0.0
        )
        
        throughput = (
            self.total_processed / uptime
            if uptime > 0
            else 0.0
        )
        
        total_tasks = self.total_processed + self.total_failed
        success_rate = (
            (self.total_processed / total_tasks * 100)
            if total_tasks > 0
            else 0.0
        )
        
        return {
            "name": self.name,
            "is_running": self.is_running,
            "worker_count": self.worker_count,
            "total_processed": self.total_processed,
            "total_failed": self.total_failed,
            "success_rate": round(success_rate, 2),
            "avg_processing_time": round(avg_processing_time, 2),
            "total_processing_time": round(self.total_processing_time, 2),
            "uptime": round(uptime, 2),
            "throughput": round(throughput, 2)  # tasks per second
        }
    
    def is_healthy(self) -> bool:
        """
        Check if worker pool is healthy.
        
        Returns:
            bool: True if all workers are running, False otherwise
        """
        if not self.is_running:
            return False
        
        # Check if all workers are still alive
        alive_workers = sum(1 for w in self.workers if not w.done())
        
        if alive_workers < self.worker_count:
            logger.warning(
                f"⚠️ {self.name}: Only {alive_workers}/{self.worker_count} "
                f"workers are alive"
            )
            return False
        
        return True
    
    async def scale(self, new_worker_count: int):
        """
        Dynamically scale worker pool (add or remove workers).
        
        Args:
            new_worker_count: Target number of workers
        """
        if not self.is_running:
            logger.error(f"❌ {self.name}: Cannot scale - pool not running")
            return
        
        current_count = len(self.workers)
        
        if new_worker_count == current_count:
            logger.info(f"ℹ️ {self.name}: Already at target worker count")
            return
        
        if new_worker_count > current_count:
            # Scale up - add workers
            new_workers = new_worker_count - current_count
            for i in range(current_count, new_worker_count):
                worker = asyncio.create_task(self._worker(i))
                self.workers.append(worker)
            
            self.worker_count = new_worker_count
            logger.info(
                f"📈 {self.name}: Scaled up by {new_workers} workers "
                f"(total: {new_worker_count})"
            )
        else:
            # Scale down - cancel excess workers
            workers_to_remove = current_count - new_worker_count
            for i in range(workers_to_remove):
                worker = self.workers.pop()
                worker.cancel()
            
            self.worker_count = new_worker_count
            logger.info(
                f"📉 {self.name}: Scaled down by {workers_to_remove} workers "
                f"(total: {new_worker_count})"
            )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"WorkerPool(name='{self.name}', "
            f"workers={self.worker_count}, "
            f"running={self.is_running}, "
            f"processed={self.total_processed}, "
            f"failed={self.total_failed})"
        )
