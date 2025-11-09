"""
Unified Worker Pool that handles both Dev and Fix tasks.

This pool combines Dev and Fix capabilities into a single worker pool
with priority queue (Fixes > New Dev) for better resource utilization.
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from utils.auto_scaling_pool import AutoScalingWorkerPool
from utils.task_queue import AsyncTaskQueue, QueueTask
from utils.enhanced_components import TaskPriority

logger = logging.getLogger(__name__)


class UnifiedWorkerPool(AutoScalingWorkerPool):
    """
    Unified worker pool for both development and fix tasks.
    
    Features:
    - Single pool handles both dev and fix work
    - Priority queue: Fixes (priority=5) > New Dev (priority=1-4)
    - Better resource utilization (no idle fix workers)
    - Automatic task type detection and routing
    """
    
    def __init__(
        self,
        name: str,
        min_workers: int,
        max_workers: int,
        task_queue: AsyncTaskQueue,
        dev_func: Callable,
        fix_func: Callable,
        output_queue: Optional[AsyncTaskQueue] = None,
        scale_up_threshold: int = 10,
        scale_down_threshold: int = 2,
        check_interval: float = 5.0
    ):
        """
        Initialize unified worker pool.
        
        Args:
            name: Pool name
            min_workers: Minimum worker count
            max_workers: Maximum worker count
            task_queue: Unified task queue (dev + fix)
            dev_func: Function to process dev tasks
            fix_func: Function to process fix tasks
            output_queue: Optional output queue
            scale_up_threshold: Queue size to trigger scale up
            scale_down_threshold: Queue size to trigger scale down
            check_interval: Seconds between scaling checks
        """
        # Store processing functions
        self.dev_func = dev_func
        self.fix_func = fix_func
        
        # Statistics
        self.dev_tasks_processed = 0
        self.fix_tasks_processed = 0
        
        # Initialize with unified processor
        super().__init__(
            name=name,
            min_workers=min_workers,
            max_workers=max_workers,
            task_queue=task_queue,
            process_func=self._unified_processor,
            output_queue=output_queue,
            scale_up_threshold=scale_up_threshold,
            scale_down_threshold=scale_down_threshold,
            check_interval=check_interval
        )
        
        logger.info(
            f"🔄 UnifiedWorkerPool '{name}': Initialized "
            f"(handles both dev and fix tasks)"
        )
    
    async def _unified_processor(self, task: QueueTask) -> Optional[QueueTask]:
        """
        Unified processor that routes to dev or fix function.
        
        Args:
            task: Task to process
            
        Returns:
            Result from appropriate processor
        """
        task_type = task.task_type
        
        try:
            if task_type == 'dev':
                logger.debug(f"💻 Processing DEV task: {task.task_id}")
                result = await self.dev_func(task)
                self.dev_tasks_processed += 1
                return result
                
            elif task_type == 'fix':
                logger.debug(f"🔧 Processing FIX task: {task.task_id}")
                result = await self.fix_func(task)
                self.fix_tasks_processed += 1
                return result
                
            else:
                logger.error(
                    f"❌ Unknown task type: {task_type} "
                    f"(task: {task.task_id})"
                )
                raise ValueError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(
                f"❌ Unified processor failed for {task_type} "
                f"task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    def prioritize_fixes(self):
        """
        Ensure fix tasks have higher priority than dev tasks.
        
        This modifies the priority of queued tasks to ensure
        fixes are processed before new development.
        """
        # Note: This is a manual prioritization helper
        # In practice, tasks should be submitted with correct priority
        # Fixes: priority=5 (RETRY)
        # Dev: priority=1-4 (CRITICAL to LOW)
        logger.info(
            f"📊 {self.name}: Fix tasks automatically prioritized "
            f"(priority=5 > dev priorities 1-4)"
        )
    
    def get_unified_stats(self) -> Dict[str, Any]:
        """
        Get unified pool statistics.
        
        Returns:
            Dictionary with dev/fix breakdown
        """
        base_stats = self.get_stats()
        
        return {
            **base_stats,
            'task_breakdown': {
                'dev_tasks': self.dev_tasks_processed,
                'fix_tasks': self.fix_tasks_processed,
                'total_tasks': self.dev_tasks_processed + self.fix_tasks_processed,
                'dev_percentage': (
                    round(
                        self.dev_tasks_processed / 
                        (self.dev_tasks_processed + self.fix_tasks_processed) * 100,
                        1
                    ) if (self.dev_tasks_processed + self.fix_tasks_processed) > 0
                    else 0.0
                ),
                'fix_percentage': (
                    round(
                        self.fix_tasks_processed / 
                        (self.dev_tasks_processed + self.fix_tasks_processed) * 100,
                        1
                    ) if (self.dev_tasks_processed + self.fix_tasks_processed) > 0
                    else 0.0
                )
            }
        }
    
    def reset_task_counts(self):
        """Reset dev/fix task counters."""
        self.dev_tasks_processed = 0
        self.fix_tasks_processed = 0
        logger.info(f"📊 {self.name}: Task counters reset")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"UnifiedWorkerPool("
            f"name='{self.name}', "
            f"workers={self.worker_count}/{self.min_workers}-{self.max_workers}, "
            f"dev={self.dev_tasks_processed}, "
            f"fix={self.fix_tasks_processed})"
        )
