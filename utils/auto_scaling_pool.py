"""
Auto-scaling worker pool that adjusts workers based on queue depth.

This module extends WorkerPool with dynamic scaling capabilities:
- Scales up when queue is deep (high load)
- Scales down when queue is shallow (low load)
- Respects min/max worker limits
- Background monitoring task
"""

import asyncio
import logging
from typing import Optional
from utils.worker_pool import WorkerPool
from utils.task_queue import AsyncTaskQueue

logger = logging.getLogger(__name__)


class AutoScalingWorkerPool(WorkerPool):
    """
    Worker pool with auto-scaling based on queue depth.
    
    Automatically adjusts worker count between min and max based on
    queue size, improving resource utilization and responsiveness.
    """
    
    def __init__(
        self,
        name: str,
        min_workers: int,
        max_workers: int,
        task_queue: AsyncTaskQueue,
        process_func: callable,
        output_queue: Optional[AsyncTaskQueue] = None,
        scale_up_threshold: int = 10,      # Scale up if queue > 10
        scale_down_threshold: int = 2,     # Scale down if queue < 2
        check_interval: float = 5.0,       # Check every 5 seconds
        scale_up_step: int = 1,            # Add 1 worker at a time
        scale_down_step: int = 1           # Remove 1 worker at a time
    ):
        """
        Initialize auto-scaling worker pool.
        
        Args:
            name: Pool name
            min_workers: Minimum worker count (never go below)
            max_workers: Maximum worker count (never exceed)
            task_queue: Queue to process
            process_func: Function to process tasks
            output_queue: Optional output queue
            scale_up_threshold: Queue size to trigger scale up
            scale_down_threshold: Queue size to trigger scale down
            check_interval: Seconds between scaling checks
            scale_up_step: Number of workers to add at once
            scale_down_step: Number of workers to remove at once
        """
        # Initialize base pool with min workers
        super().__init__(
            name=name,
            worker_count=min_workers,
            task_queue=task_queue,
            process_func=process_func,
            output_queue=output_queue
        )
        
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.check_interval = check_interval
        self.scale_up_step = scale_up_step
        self.scale_down_step = scale_down_step
        
        # Scaling state
        self.scaling_task = None
        self.scaling_enabled = False
        
        # Scaling statistics
        self.scale_up_count = 0
        self.scale_down_count = 0
        self.total_scaling_actions = 0
        
        logger.info(
            f"📊 AutoScalingWorkerPool '{name}': "
            f"min={min_workers}, max={max_workers}, "
            f"scale_up@{scale_up_threshold}, "
            f"scale_down@{scale_down_threshold}"
        )
    
    async def start(self):
        """Start pool with auto-scaling enabled."""
        await super().start()
        
        # Start scaling monitor
        self.scaling_enabled = True
        self.scaling_task = asyncio.create_task(self._scaling_monitor())
        
        logger.info(f"📊 Auto-scaling enabled for {self.name}")
    
    async def stop(self, graceful: bool = True, timeout: float = 60.0):
        """Stop pool and scaling monitor."""
        # Stop scaling first
        self.scaling_enabled = False
        if self.scaling_task:
            self.scaling_task.cancel()
            try:
                await self.scaling_task
            except asyncio.CancelledError:
                pass
        
        # Stop workers
        await super().stop(graceful, timeout)
        
        logger.info(
            f"📊 Auto-scaling stopped for {self.name} "
            f"(scale_ups: {self.scale_up_count}, "
            f"scale_downs: {self.scale_down_count})"
        )
    
    async def _scaling_monitor(self):
        """
        Background task that monitors queue and scales workers.
        
        Runs continuously while pool is active.
        """
        logger.info(f"👀 Scaling monitor started for {self.name}")
        
        while self.scaling_enabled:
            try:
                await asyncio.sleep(self.check_interval)
                
                # Get current state
                queue_size = self.task_queue.size()
                current_workers = self.worker_count
                in_progress = self.task_queue.in_progress_count()
                
                # Calculate total workload
                total_workload = queue_size + in_progress
                
                logger.debug(
                    f"📊 {self.name} state: "
                    f"queue={queue_size}, "
                    f"in_progress={in_progress}, "
                    f"workers={current_workers}"
                )
                
                # Scale up if queue is large and under max
                if (total_workload > self.scale_up_threshold and 
                    current_workers < self.max_workers):
                    
                    new_count = min(
                        current_workers + self.scale_up_step,
                        self.max_workers
                    )
                    
                    await self.scale(new_count)
                    self.scale_up_count += 1
                    self.total_scaling_actions += 1
                    
                    logger.info(
                        f"📈 Scaled UP {self.name}: "
                        f"{current_workers} → {new_count} workers "
                        f"(workload: {total_workload}, "
                        f"threshold: {self.scale_up_threshold})"
                    )
                
                # Scale down if queue is small and above min
                elif (total_workload < self.scale_down_threshold and 
                      current_workers > self.min_workers):
                    
                    new_count = max(
                        current_workers - self.scale_down_step,
                        self.min_workers
                    )
                    
                    await self.scale(new_count)
                    self.scale_down_count += 1
                    self.total_scaling_actions += 1
                    
                    logger.info(
                        f"📉 Scaled DOWN {self.name}: "
                        f"{current_workers} → {new_count} workers "
                        f"(workload: {total_workload}, "
                        f"threshold: {self.scale_down_threshold})"
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"❌ Scaling monitor error for {self.name}: {e}",
                    exc_info=True
                )
                # Continue monitoring despite errors
        
        logger.info(f"👋 Scaling monitor stopped for {self.name}")
    
    def set_thresholds(
        self,
        scale_up_threshold: Optional[int] = None,
        scale_down_threshold: Optional[int] = None
    ):
        """
        Update scaling thresholds at runtime.
        
        Args:
            scale_up_threshold: New scale up threshold (None = no change)
            scale_down_threshold: New scale down threshold (None = no change)
        """
        if scale_up_threshold is not None:
            old = self.scale_up_threshold
            self.scale_up_threshold = scale_up_threshold
            logger.info(
                f"📊 {self.name}: Updated scale_up_threshold "
                f"{old} → {scale_up_threshold}"
            )
        
        if scale_down_threshold is not None:
            old = self.scale_down_threshold
            self.scale_down_threshold = scale_down_threshold
            logger.info(
                f"📊 {self.name}: Updated scale_down_threshold "
                f"{old} → {scale_down_threshold}"
            )
    
    def set_check_interval(self, interval: float):
        """
        Update scaling check interval.
        
        Args:
            interval: New check interval in seconds
        """
        old = self.check_interval
        self.check_interval = interval
        logger.info(
            f"📊 {self.name}: Updated check_interval "
            f"{old}s → {interval}s"
        )
    
    def get_scaling_stats(self) -> dict:
        """
        Get auto-scaling statistics.
        
        Returns:
            Dictionary with scaling metrics
        """
        return {
            'min_workers': self.min_workers,
            'max_workers': self.max_workers,
            'current_workers': self.worker_count,
            'scale_up_threshold': self.scale_up_threshold,
            'scale_down_threshold': self.scale_down_threshold,
            'scale_up_count': self.scale_up_count,
            'scale_down_count': self.scale_down_count,
            'total_scaling_actions': self.total_scaling_actions,
            'scaling_enabled': self.scaling_enabled
        }
    
    def get_stats(self) -> dict:
        """
        Get comprehensive stats (includes base pool + scaling stats).
        
        Returns:
            Dictionary with all pool and scaling metrics
        """
        base_stats = super().get_stats()
        scaling_stats = self.get_scaling_stats()
        
        return {
            **base_stats,
            'auto_scaling': scaling_stats
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"AutoScalingWorkerPool("
            f"name='{self.name}', "
            f"workers={self.worker_count}/{self.min_workers}-{self.max_workers}, "
            f"scale_ups={self.scale_up_count}, "
            f"scale_downs={self.scale_down_count})"
        )
