"""
Pipeline manager for orchestrating Dev/QA/Fix parallel processing.

This module provides the high-level orchestrator that manages queues,
worker pools, and coordinates the entire parallel processing pipeline.
"""

import asyncio
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from utils.task_queue import AsyncTaskQueue, QueueTask
from utils.worker_pool import WorkerPool

logger = logging.getLogger(__name__)


class PipelineManager:
    """
    Orchestrates parallel processing pipeline with multiple stages.
    
    Pipeline flow:
        PM Plan → Dev Queue → Dev Workers → QA Queue → QA Workers → Fix Queue → Fix Workers → Deploy Queue
    
    Each stage has its own queue and worker pool, processing tasks in parallel.
    """
    
    def __init__(
        self,
        dev_workers: int = 3,
        qa_workers: int = 2,
        fix_workers: int = 2,
        deploy_workers: int = 1
    ):
        """
        Initialize pipeline manager.
        
        Args:
            dev_workers: Number of concurrent dev workers
            qa_workers: Number of concurrent QA workers
            fix_workers: Number of concurrent fix workers
            deploy_workers: Number of concurrent deploy workers
        """
        self.dev_workers_count = dev_workers
        self.qa_workers_count = qa_workers
        self.fix_workers_count = fix_workers
        self.deploy_workers_count = deploy_workers
        
        # Initialize queues
        self.dev_queue = AsyncTaskQueue("DevQueue")
        self.qa_queue = AsyncTaskQueue("QAQueue")
        self.fix_queue = AsyncTaskQueue("FixQueue")
        self.deploy_queue = AsyncTaskQueue("DeployQueue")
        
        # Worker pools (initialized in start())
        self.dev_pool = None
        self.qa_pool = None
        self.fix_pool = None
        self.deploy_pool = None
        
        # Pipeline state
        self.is_running = False
        self.start_time = None
        
        # Metrics
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        
        # Store agent references (set by dependency injection)
        self.dev_agent = None
        self.qa_agent = None
        self.ops_agent = None
        
        logger.info(
            f"🏭 PipelineManager: Initialized "
            f"(dev:{dev_workers}, qa:{qa_workers}, "
            f"fix:{fix_workers}, deploy:{deploy_workers})"
        )
    
    def set_agents(self, dev_agent, qa_agent, ops_agent):
        """
        Set agent references for processing.
        
        Args:
            dev_agent: DevAgent instance
            qa_agent: QAAgent instance
            ops_agent: OpsAgent instance
        """
        self.dev_agent = dev_agent
        self.qa_agent = qa_agent
        self.ops_agent = ops_agent
        logger.info("🔌 PipelineManager: Agent references set")
    
    async def _process_dev_task(self, task: QueueTask) -> Optional[QueueTask]:
        """
        Process a dev task (code generation).
        
        Args:
            task: Dev task to process
            
        Returns:
            Optional[QueueTask]: QA task if successful, None if failed
        """
        try:
            logger.info(f"💻 Processing dev task: {task.task_id}")
            
            # Extract payload
            payload = task.payload
            subtask = payload.get("subtask")
            websocket = payload.get("websocket")
            project_desc = payload.get("project_desc")
            plan = payload.get("plan")
            
            # Call dev agent (streaming)
            if self.dev_agent:
                result = await self.dev_agent.execute_task(
                    subtask=subtask,
                    websocket=websocket,
                    project_desc=project_desc,
                    plan=plan
                )
                
                # Create QA task
                qa_task = QueueTask(
                    task_id=f"qa_{task.task_id}",
                    task_type="qa",
                    payload={
                        "subtask": subtask,
                        "dev_result": result,
                        "websocket": websocket,
                        "project_desc": project_desc
                    },
                    priority=task.priority  # Maintain priority
                )
                
                logger.info(
                    f"✅ Dev task {task.task_id} completed, "
                    f"created QA task {qa_task.task_id}"
                )
                
                return qa_task
            else:
                logger.error("❌ Dev agent not set")
                return None
                
        except Exception as e:
            logger.error(
                f"❌ Failed processing dev task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _process_qa_task(self, task: QueueTask) -> Optional[QueueTask]:
        """
        Process a QA task (testing & validation).
        
        Args:
            task: QA task to process
            
        Returns:
            Optional[QueueTask]: Fix task if tests fail, Deploy task if tests pass
        """
        try:
            logger.info(f"🧪 Processing QA task: {task.task_id}")
            
            # Extract payload
            payload = task.payload
            subtask = payload.get("subtask")
            dev_result = payload.get("dev_result")
            websocket = payload.get("websocket")
            project_desc = payload.get("project_desc")
            
            # Call QA agent
            if self.qa_agent:
                qa_result = await self.qa_agent.test_code(
                    subtask=subtask,
                    code=dev_result,
                    websocket=websocket,
                    project_desc=project_desc
                )
                
                # Check if tests passed
                if qa_result.get("tests_passed", False):
                    # Create deploy task
                    deploy_task = QueueTask(
                        task_id=f"deploy_{task.task_id}",
                        task_type="deploy",
                        payload={
                            "subtask": subtask,
                            "code": dev_result,
                            "qa_result": qa_result,
                            "websocket": websocket
                        },
                        priority=task.priority
                    )
                    
                    # Enqueue to deploy queue
                    await self.deploy_queue.put(deploy_task)
                    
                    logger.info(
                        f"✅ QA task {task.task_id} passed, "
                        f"enqueued deploy task {deploy_task.task_id}"
                    )
                    
                    return None  # Already enqueued, don't return
                else:
                    # Create fix task
                    fix_task = QueueTask(
                        task_id=f"fix_{task.task_id}",
                        task_type="fix",
                        payload={
                            "subtask": subtask,
                            "code": dev_result,
                            "qa_result": qa_result,
                            "websocket": websocket,
                            "project_desc": project_desc
                        },
                        priority=task.priority + 1  # Slightly lower priority
                    )
                    
                    # Enqueue to fix queue
                    await self.fix_queue.put(fix_task)
                    
                    logger.warning(
                        f"⚠️ QA task {task.task_id} failed, "
                        f"enqueued fix task {fix_task.task_id}"
                    )
                    
                    return None  # Already enqueued, don't return
            else:
                logger.error("❌ QA agent not set")
                return None
                
        except Exception as e:
            logger.error(
                f"❌ Failed processing QA task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _process_fix_task(self, task: QueueTask) -> Optional[QueueTask]:
        """
        Process a fix task (bug fixes based on QA feedback).
        
        Args:
            task: Fix task to process
            
        Returns:
            Optional[QueueTask]: New QA task for re-testing
        """
        try:
            logger.info(f"🔧 Processing fix task: {task.task_id}")
            
            # Extract payload
            payload = task.payload
            subtask = payload.get("subtask")
            code = payload.get("code")
            qa_result = payload.get("qa_result")
            websocket = payload.get("websocket")
            project_desc = payload.get("project_desc")
            
            # Call dev agent with fix context
            if self.dev_agent:
                fixed_code = await self.dev_agent.fix_code(
                    subtask=subtask,
                    original_code=code,
                    qa_feedback=qa_result,
                    websocket=websocket,
                    project_desc=project_desc
                )
                
                # Create new QA task for re-testing
                qa_task = QueueTask(
                    task_id=f"qa_retest_{task.task_id}",
                    task_type="qa",
                    payload={
                        "subtask": subtask,
                        "dev_result": fixed_code,
                        "websocket": websocket,
                        "project_desc": project_desc,
                        "is_retest": True
                    },
                    priority=task.priority
                )
                
                # Enqueue back to QA queue
                await self.qa_queue.put(qa_task)
                
                logger.info(
                    f"✅ Fix task {task.task_id} completed, "
                    f"enqueued re-test QA task {qa_task.task_id}"
                )
                
                return None  # Already enqueued, don't return
            else:
                logger.error("❌ Dev agent not set")
                return None
                
        except Exception as e:
            logger.error(
                f"❌ Failed processing fix task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _process_deploy_task(self, task: QueueTask) -> None:
        """
        Process a deploy task (finalize and save code).
        
        Args:
            task: Deploy task to process
        """
        try:
            logger.info(f"🚀 Processing deploy task: {task.task_id}")
            
            # Extract payload
            payload = task.payload
            subtask = payload.get("subtask")
            code = payload.get("code")
            qa_result = payload.get("qa_result")
            websocket = payload.get("websocket")
            
            # Call ops agent for deployment
            if self.ops_agent:
                await self.ops_agent.deploy_code(
                    subtask=subtask,
                    code=code,
                    qa_result=qa_result,
                    websocket=websocket
                )
                
                self.completed_tasks += 1
                
                logger.info(
                    f"✅ Deploy task {task.task_id} completed "
                    f"(total completed: {self.completed_tasks})"
                )
            else:
                logger.error("❌ Ops agent not set")
                
        except Exception as e:
            logger.error(
                f"❌ Failed processing deploy task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    async def start(self):
        """Start all worker pools in the pipeline."""
        if self.is_running:
            logger.warning("⚠️ PipelineManager: Already running")
            return
        
        logger.info("🚀 PipelineManager: Starting pipeline...")
        
        # Create worker pools
        # Note: QA and Fix pools don't use output_queue because they route conditionally
        self.dev_pool = WorkerPool(
            name="DevPool",
            worker_count=self.dev_workers_count,
            task_queue=self.dev_queue,
            process_func=self._process_dev_task,
            output_queue=self.qa_queue
        )
        
        self.qa_pool = WorkerPool(
            name="QAPool",
            worker_count=self.qa_workers_count,
            task_queue=self.qa_queue,
            process_func=self._process_qa_task,
            output_queue=None  # Routes conditionally to fix or deploy
        )
        
        self.fix_pool = WorkerPool(
            name="FixPool",
            worker_count=self.fix_workers_count,
            task_queue=self.fix_queue,
            process_func=self._process_fix_task,
            output_queue=None  # Routes back to QA queue internally
        )
        
        self.deploy_pool = WorkerPool(
            name="DeployPool",
            worker_count=self.deploy_workers_count,
            task_queue=self.deploy_queue,
            process_func=self._process_deploy_task,
            output_queue=None  # Final stage
        )
        
        # Start all pools
        await self.dev_pool.start()
        await self.qa_pool.start()
        await self.fix_pool.start()
        await self.deploy_pool.start()
        
        self.is_running = True
        self.start_time = datetime.now()
        
        logger.info(
            f"✅ PipelineManager: All worker pools started "
            f"(total workers: {self._total_workers()})"
        )
    
    async def stop(self, graceful: bool = True, timeout: float = 60.0):
        """
        Stop all worker pools.
        
        Args:
            graceful: Wait for tasks to complete
            timeout: Timeout for graceful shutdown
        """
        if not self.is_running:
            logger.warning("⚠️ PipelineManager: Not running")
            return
        
        logger.info(
            f"🛑 PipelineManager: Stopping pipeline "
            f"(graceful={graceful}, timeout={timeout}s)..."
        )
        
        # Stop all pools (in reverse order)
        await asyncio.gather(
            self.deploy_pool.stop(graceful, timeout / 4),
            self.fix_pool.stop(graceful, timeout / 4),
            self.qa_pool.stop(graceful, timeout / 4),
            self.dev_pool.stop(graceful, timeout / 4)
        )
        
        self.is_running = False
        
        # Log final statistics
        stats = self.get_stats()
        logger.info(
            f"📊 PipelineManager: Final stats - "
            f"total: {stats['total_tasks']}, "
            f"completed: {stats['completed_tasks']}, "
            f"failed: {stats['failed_tasks']}, "
            f"uptime: {stats['uptime']}s"
        )
        
        logger.info("✅ PipelineManager: Pipeline stopped")
    
    async def submit_dev_task(
        self,
        task_id: str,
        subtask: Dict[str, Any],
        websocket,
        project_desc: str,
        plan: Dict[str, Any],
        priority: int = 5
    ):
        """
        Submit a new dev task to the pipeline.
        
        Args:
            task_id: Unique task identifier
            subtask: Task data dictionary
            websocket: WebSocket for streaming updates
            project_desc: Project description
            plan: Full plan data
            priority: Task priority (1=highest, 10=lowest)
        """
        task = QueueTask(
            task_id=task_id,
            task_type="dev",
            payload={
                "subtask": subtask,
                "websocket": websocket,
                "project_desc": project_desc,
                "plan": plan
            },
            priority=priority
        )
        
        await self.dev_queue.put(task)
        self.total_tasks += 1
        
        logger.info(
            f"📥 PipelineManager: Submitted dev task {task_id} "
            f"(priority: {priority}, total: {self.total_tasks})"
        )
    
    async def wait_until_complete(self):
        """Wait until all tasks are processed through entire pipeline."""
        logger.info("⏳ PipelineManager: Waiting for pipeline to complete...")
        
        # Wait for each stage to empty
        await self.dev_queue.wait_until_empty()
        await self.qa_queue.wait_until_empty()
        await self.fix_queue.wait_until_empty()
        await self.deploy_queue.wait_until_empty()
        
        logger.info("✅ PipelineManager: Pipeline completed all tasks")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive pipeline statistics.
        
        Returns:
            dict: Pipeline stats including queue sizes, worker stats, metrics
        """
        uptime = (
            (datetime.now() - self.start_time).total_seconds()
            if self.start_time
            else 0.0
        )
        
        throughput = (
            self.completed_tasks / uptime
            if uptime > 0
            else 0.0
        )
        
        return {
            "is_running": self.is_running,
            "uptime": round(uptime, 2),
            "total_workers": self._total_workers(),
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "throughput": round(throughput, 4),
            "queues": {
                "dev": self.dev_queue.get_stats(),
                "qa": self.qa_queue.get_stats(),
                "fix": self.fix_queue.get_stats(),
                "deploy": self.deploy_queue.get_stats()
            },
            "workers": {
                "dev": self.dev_pool.get_stats() if self.dev_pool else {},
                "qa": self.qa_pool.get_stats() if self.qa_pool else {},
                "fix": self.fix_pool.get_stats() if self.fix_pool else {},
                "deploy": self.deploy_pool.get_stats() if self.deploy_pool else {}
            }
        }
    
    def _total_workers(self) -> int:
        """Calculate total number of workers across all pools."""
        return (
            self.dev_workers_count +
            self.qa_workers_count +
            self.fix_workers_count +
            self.deploy_workers_count
        )
    
    def is_healthy(self) -> bool:
        """
        Check if pipeline is healthy.
        
        Returns:
            bool: True if all worker pools are healthy
        """
        if not self.is_running:
            return False
        
        return all([
            self.dev_pool.is_healthy(),
            self.qa_pool.is_healthy(),
            self.fix_pool.is_healthy(),
            self.deploy_pool.is_healthy()
        ])
    
    async def scale_workers(
        self,
        dev: Optional[int] = None,
        qa: Optional[int] = None,
        fix: Optional[int] = None,
        deploy: Optional[int] = None
    ):
        """
        Dynamically scale worker pools.
        
        Args:
            dev: New dev worker count (None = no change)
            qa: New QA worker count (None = no change)
            fix: New fix worker count (None = no change)
            deploy: New deploy worker count (None = no change)
        """
        if not self.is_running:
            logger.error("❌ PipelineManager: Cannot scale - not running")
            return
        
        tasks = []
        
        if dev is not None:
            tasks.append(self.dev_pool.scale(dev))
            self.dev_workers_count = dev
        
        if qa is not None:
            tasks.append(self.qa_pool.scale(qa))
            self.qa_workers_count = qa
        
        if fix is not None:
            tasks.append(self.fix_pool.scale(fix))
            self.fix_workers_count = fix
        
        if deploy is not None:
            tasks.append(self.deploy_pool.scale(deploy))
            self.deploy_workers_count = deploy
        
        await asyncio.gather(*tasks)
        
        logger.info(
            f"📊 PipelineManager: Scaled workers "
            f"(total: {self._total_workers()})"
        )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"PipelineManager(running={self.is_running}, "
            f"workers={self._total_workers()}, "
            f"completed={self.completed_tasks}/{self.total_tasks})"
        )
