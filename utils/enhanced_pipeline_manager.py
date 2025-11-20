"""
Enhanced Pipeline Manager with production-grade features.

This module extends PipelineManager with:
- ResultCache: Avoid regenerating identical code
- EventRouter: Event-driven architecture with DLQ
- AutoScalingWorkerPool: Dynamic worker scaling
- CircuitBreaker: Error rate protection
- UnifiedWorkerPool: Dev+Fix in one pool
- PriorityAssigner: Critical-path-first processing
- DependencyAnalyzer: Parallel batch execution with dependency resolution
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from utils.pipeline_manager import PipelineManager
from utils.task_queue import AsyncTaskQueue, QueueTask
from utils.auto_scaling_pool import AutoScalingWorkerPool
from utils.unified_worker_pool import UnifiedWorkerPool
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError
from utils.event_router import EventRouter
from utils.enhanced_components import (
    ResultCache, PriorityAssigner, Event, EventType, TaskPriority
)
from utils.dependency_analyzer import DependencyAnalyzer, analyze_plan_dependencies

logger = logging.getLogger(__name__)


class EnhancedPipelineManager(PipelineManager):
    """
    Enhanced pipeline with auto-scaling, caching, circuit breaking, and event routing.
    
    New Features:
    - Auto-scales workers (2-10 for dev, 1-5 for QA)
    - Caches dev results (30-50% fewer LLM calls)
    - Circuit breakers protect against API failures
    - Event-driven routing with Dead Letter Queue
    - Unified dev+fix worker pool (better utilization)
    - Priority-based task scheduling
    """
    
    def __init__(
        self,
        # Worker ranges (min, max)
        dev_workers_min: int = 2,
        dev_workers_max: int = 10,
        qa_workers_min: int = 1,
        qa_workers_max: int = 5,
        deploy_workers: int = 1,
        # Caching
        enable_cache: bool = True,
        cache_ttl_seconds: int = 3600,
        cache_max_size: int = 1000,
        # Circuit breaker
        enable_circuit_breaker: bool = True,
        circuit_failure_threshold: float = 0.5,
        circuit_timeout_seconds: float = 30.0,
        # Auto-scaling
        scale_up_threshold: int = 10,
        scale_down_threshold: int = 2,
        # Event routing
        max_retries: int = 3
    ):
        """
        Initialize enhanced pipeline manager.
        
        Args:
            dev_workers_min: Minimum dev workers (default: 2)
            dev_workers_max: Maximum dev workers (default: 10)
            qa_workers_min: Minimum QA workers (default: 1)
            qa_workers_max: Maximum QA workers (default: 5)
            deploy_workers: Deploy workers (default: 1)
            enable_cache: Enable result caching (default: True)
            cache_ttl_seconds: Cache TTL (default: 1 hour)
            cache_max_size: Max cache entries (default: 1000)
            enable_circuit_breaker: Enable circuit breakers (default: True)
            circuit_failure_threshold: Error rate to open circuit (default: 0.5)
            circuit_timeout_seconds: Wait time before retry (default: 30s)
            scale_up_threshold: Queue size to scale up (default: 10)
            scale_down_threshold: Queue size to scale down (default: 2)
            max_retries: Max retry attempts (default: 3)
        """
        # Store config before calling super().__init__
        self.dev_workers_min = dev_workers_min
        self.dev_workers_max = dev_workers_max
        self.qa_workers_min = qa_workers_min
        self.qa_workers_max = qa_workers_max
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        
        # Initialize base class with minimum workers
        super().__init__(
            dev_workers=dev_workers_min,
            qa_workers=qa_workers_min,
            fix_workers=0,  # Will use unified pool
            deploy_workers=deploy_workers
        )
        
        # Enhanced components
        self.cache_enabled = enable_cache
        self.circuit_breaker_enabled = enable_circuit_breaker
        
        # Result cache
        self.result_cache = ResultCache(
            ttl_seconds=cache_ttl_seconds,
            max_size=cache_max_size
        ) if enable_cache else None
        
        # Priority assigner
        self.priority_assigner = PriorityAssigner()
        
        # Event router with DLQ
        self.event_router = EventRouter()
        EventRouter.MAX_RETRIES = max_retries
        self._register_event_handlers()
        
        # Circuit breakers for each agent type
        breaker_config = CircuitBreakerConfig(
            failure_threshold=circuit_failure_threshold,
            timeout_seconds=circuit_timeout_seconds,
            success_threshold=3,
            window_size=10,
            min_requests=5
        )
        
        self.dev_breaker = CircuitBreaker(
            "DevAgent",
            breaker_config
        ) if enable_circuit_breaker else None
        
        self.qa_breaker = CircuitBreaker(
            "QAAgent",
            breaker_config
        ) if enable_circuit_breaker else None
        
        self.ops_breaker = CircuitBreaker(
            "OpsAgent",
            breaker_config
        ) if enable_circuit_breaker else None
        
        # Unified dev+fix queue and pool (will replace dev_queue and fix_queue)
        self.unified_queue = AsyncTaskQueue("UnifiedDevFixQueue")
        self.unified_pool = None  # Initialized in start()
        
        # Dependency analyzer (Phase 2.1)
        self.dependency_analyzer = DependencyAnalyzer()
        self.dependency_batches = []
        self.critical_path_files = set()  # Store critical path files for priority assignment
        self.use_dependency_analysis = True
        
        # Register circuit breaker callbacks
        if enable_circuit_breaker:
            self._register_circuit_breaker_callbacks()
        
        logger.info(
            f"🚀 EnhancedPipelineManager: Initialized "
            f"(dev:{dev_workers_min}-{dev_workers_max}, "
            f"qa:{qa_workers_min}-{qa_workers_max}, "
            f"cache:{enable_cache}, circuit_breaker:{enable_circuit_breaker}, "
            f"dependency_analysis:{self.use_dependency_analysis})"
        )
    
    def _register_event_handlers(self):
        """Register event handlers for pipeline stages."""
        # Dev completion → QA
        self.event_router.register_handler(
            EventType.FILE_COMPLETED,
            self._handle_file_completed
        )
        
        # QA results
        self.event_router.register_handler(
            EventType.QA_PASSED,
            self._handle_qa_passed
        )
        self.event_router.register_handler(
            EventType.QA_FAILED,
            self._handle_qa_failed
        )
        
        # Fix completion → Re-QA
        self.event_router.register_handler(
            EventType.FIX_COMPLETED,
            self._handle_fix_completed
        )
        
        # Deploy
        self.event_router.register_handler(
            EventType.DEPLOY_READY,
            self._handle_deploy_ready
        )
        
        # Escalation
        self.event_router.register_handler(
            EventType.ESCALATE_TO_PM,
            self._handle_escalation
        )
        
        logger.info("📮 Event handlers registered")
    
    def _register_circuit_breaker_callbacks(self):
        """Register callbacks for circuit breaker state changes."""
        if self.dev_breaker:
            self.dev_breaker.on_open(
                lambda b: logger.error(
                    f"🔴 {b.name} circuit OPENED "
                    f"(error_rate: {b.get_error_rate():.1%})"
                )
            )
            self.dev_breaker.on_close(
                lambda b: logger.info(
                    f"🟢 {b.name} circuit CLOSED (recovered)"
                )
            )
        
        if self.qa_breaker:
            self.qa_breaker.on_open(
                lambda b: logger.error(
                    f"🔴 {b.name} circuit OPENED "
                    f"(error_rate: {b.get_error_rate():.1%})"
                )
            )
            self.qa_breaker.on_close(
                lambda b: logger.info(
                    f"🟢 {b.name} circuit CLOSED (recovered)"
                )
            )
        
        if self.ops_breaker:
            self.ops_breaker.on_open(
                lambda b: logger.error(
                    f"🔴 {b.name} circuit OPENED "
                    f"(error_rate: {b.get_error_rate():.1%})"
                )
            )
            self.ops_breaker.on_close(
                lambda b: logger.info(
                    f"🟢 {b.name} circuit CLOSED (recovered)"
                )
            )
    
    # ========================================================================
    # Event Handlers
    # ========================================================================
    
    async def _handle_file_completed(self, event: Event):
        """Handle dev file completion - route to QA."""
        logger.info(f"📄 File completed: {event.task_id}, routing to QA")
        
        # Create QA task
        qa_task = QueueTask(
            task_id=f"qa_{event.task_id}",
            task_type="qa",
            payload=event.payload,
            priority=event.payload.get('priority', TaskPriority.NORMAL.value)
        )
        
        await self.qa_queue.put(qa_task)
    
    async def _handle_qa_passed(self, event: Event):
        """Handle QA pass - route to deploy."""
        # Check QA status from metadata
        qa_confidence = event.payload.get('metadata', {}).get('qa_confidence', 1.0)
        qa_issues = event.payload.get('metadata', {}).get('qa_issues', [])
        
        if qa_confidence >= 0.8:
            logger.info(f"✅ QA passed: {event.task_id} (confidence: {qa_confidence:.2f}), routing to deploy")
        else:
            logger.warning(f"⚠️  QA flagged: {event.task_id} (confidence: {qa_confidence:.2f}), deploying with warnings")
            logger.warning(f"   Issues found: {len(qa_issues)}")
        
        # Create deploy task
        deploy_task = QueueTask(
            task_id=f"deploy_{event.task_id}",
            task_type="deploy",
            payload=event.payload,
            priority=event.payload.get('priority', TaskPriority.NORMAL.value)
        )
        
        await self.deploy_queue.put(deploy_task)
    
    async def _handle_qa_failed(self, event: Event):
        """Handle QA failure - route to fix ONCE, then directly to deploy."""
        logger.warning(f"❌ QA failed: {event.task_id}, routing to Dev for one-time fix")
        
        # Check if this has already been fixed once
        payload = event.payload
        fix_attempt_count = payload.get('fix_attempt_count', 0)
        
        if fix_attempt_count >= 1:
            # Already fixed once - send directly to deploy with warnings
            logger.warning(
                f"⚠️  {event.task_id} already fixed once, "
                f"bypassing retest and sending to deploy with known issues"
            )
            deploy_task = QueueTask(
                task_id=f"deploy_{event.task_id}_with_issues",
                task_type="deploy",
                payload={
                    **payload,
                    'has_known_issues': True,
                    'qa_status': 'failed_after_fix'
                },
                priority=TaskPriority.LOW.value  # Lower priority for problematic files
            )
            await self.deploy_queue.put(deploy_task)
        else:
            # First QA failure - request one-time fix from Dev
            logger.info(f"🔧 Requesting Dev fix for {event.task_id} (attempt 1/1)")
            fix_task = QueueTask(
                task_id=f"fix_{event.task_id}",
                task_type="fix",
                payload={
                    **payload,
                    'fix_attempt_count': fix_attempt_count + 1,
                    'is_final_fix': True  # Indicate this is the only fix attempt
                },
                priority=TaskPriority.RETRY.value  # Fixes have higher priority
            )
            await self.unified_queue.put(fix_task)  # Use unified queue
    
    async def _handle_fix_completed(self, event: Event):
        """Handle fix completion - send DIRECTLY to deploy without retesting."""
        logger.info(
            f"🔧 Fix completed: {event.task_id}, "
            f"sending directly to deploy (skipping retest)"
        )
        
        # Send directly to deploy without QA retest
        deploy_task = QueueTask(
            task_id=f"deploy_{event.task_id}_fixed",
            task_type="deploy",
            payload={
                **event.payload,
                'was_fixed': True,
                'skip_qa_retest': True
            },
            priority=TaskPriority.NORMAL.value
        )
        
        await self.deploy_queue.put(deploy_task)
    
    async def _handle_deploy_ready(self, event: Event):
        """Handle deploy ready event."""
        logger.info(f"🚀 Deploy ready: {event.task_id}")
        # Already in deploy queue via _handle_qa_passed
    
    async def _handle_escalation(self, event: Event):
        """Handle task escalation to PM Agent."""
        logger.error(
            f"💀 Task escalated to PM Agent: {event.task_id}\n"
            f"   Reason: {event.payload.get('reason', 'Unknown')}\n"
            f"   Original event: {event.payload.get('original_event_type', 'Unknown')}"
        )
        
        self.failed_tasks += 1
        
        # TODO: Implement PM Agent notification
        # Could send email, Slack message, or write to file
    
    # ========================================================================
    # Enhanced Task Processing (with cache and circuit breakers)
    # ========================================================================
    
    async def _process_dev_task_enhanced(self, task: QueueTask) -> Optional[QueueTask]:
        """
        Process dev task with caching and circuit breaker.
        
        Args:
            task: Dev task to process
            
        Returns:
            Result for output queue (or None if routing via events)
        """
        try:
            logger.info(f"💻 Processing dev task: {task.task_id}")
            
            payload = task.payload
            subtask = payload.get("subtask")
            
            # Check cache first
            if self.result_cache:
                cached_result = self.result_cache.get(subtask)
                if cached_result:
                    logger.info(
                        f"💾 Cache HIT for {task.task_id} - using cached result"
                    )
                    result = cached_result
                else:
                    # Cache miss - generate code
                    result = await self._call_dev_agent_with_breaker(task)
                    
                    # Cache the result
                    if result:
                        self.result_cache.set(subtask, result)
            else:
                # No cache - call agent directly
                result = await self._call_dev_agent_with_breaker(task)
            
            if result:
                # Extract result data - execute_task returns Task object
                from models.task import Task
                if isinstance(result, Task):
                    # Task completed successfully - convert to dict for QA
                    result_data = result.to_dict()
                else:
                    result_data = result
                
                # Emit event for routing
                event = Event(
                    event_type=EventType.FILE_COMPLETED,
                    task_id=task.task_id,
                    payload={
                        **payload,
                        'dev_result': result_data
                    },
                    timestamp=datetime.now()
                )
                await self.event_router.route_event(event)
            
            return None  # Routing via events
            
        except CircuitBreakerOpenError as cbe:
            logger.warning(
                f"⚠️  Circuit breaker OPEN for dev task {task.task_id} - "
                f"will retry after timeout. Task will be requeued."
            )
            # Let the task queue's retry mechanism handle it
            raise
        except Exception as e:
            logger.error(
                f"❌ Failed processing dev task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _process_fix_task_enhanced(self, task: QueueTask) -> Optional[QueueTask]:
        """
        Process fix task with circuit breaker.
        
        Args:
            task: Fix task to process
            
        Returns:
            Result for output queue (or None if routing via events)
        """
        try:
            logger.info(f"🔧 Processing fix task: {task.task_id}")
            
            result = await self._call_dev_agent_with_breaker(task, is_fix=True)
            
            if result:
                # Emit event for routing back to QA
                event = Event(
                    event_type=EventType.FIX_COMPLETED,
                    task_id=task.task_id,
                    payload={
                        **task.payload,
                        'fixed_code': result
                    },
                    timestamp=datetime.now()
                )
                await self.event_router.route_event(event)
            
            return None  # Routing via events
            
        except CircuitBreakerOpenError:
            logger.error(
                f"🔴 Circuit breaker OPEN for fix task {task.task_id} - skipping"
            )
            raise
        except Exception as e:
            logger.error(
                f"❌ Failed processing fix task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _call_dev_agent_with_breaker(
        self,
        task: QueueTask,
        is_fix: bool = False
    ) -> Dict[str, Any]:
        """
        Call dev agent through circuit breaker.
        
        Args:
            task: Task to process
            is_fix: True if this is a fix task
            
        Returns:
            Dev agent result
        """
        from models.task import Task
        from models.enums import TaskStatus
        from datetime import datetime
        
        payload = task.payload
        subtask_dict = payload.get("subtask")
        websocket = payload.get("websocket")
        project_desc = payload.get("project_desc")
        plan = payload.get("plan")
        
        if not self.dev_agent:
            raise ValueError("Dev agent not set")
        
        # Convert dict to Task object for execute_task (both dev and fix)
        if isinstance(subtask_dict, dict):
            # Get metadata and add fix context if needed
            metadata = dict(subtask_dict.get('metadata') or {})
            plan = payload.get("plan")
            if isinstance(plan, dict):
                plan_id = plan.get('id') or plan.get('plan_id')
                if plan_id and metadata.get('plan_id') is None:
                    metadata['plan_id'] = plan_id
            if is_fix:
                metadata['is_fix_attempt'] = True
                metadata['original_code'] = payload.get("code")
                metadata['qa_feedback'] = payload.get("qa_result")
            
            # Create Task object from dict
            description = subtask_dict.get('description', '')
            if is_fix:
                qa_issues = payload.get('qa_result', {}).get('issues_found', [])
                description = f"FIX: {description}\n\nQA Feedback: {len(qa_issues)} issues found. See metadata for details."
            
            task_obj = Task(
                id=subtask_dict.get('id', task.task_id),
                title=subtask_dict.get('title', 'Development Task'),
                description=description,
                priority=subtask_dict.get('priority', 5),
                status=TaskStatus.PENDING,
                dependencies=subtask_dict.get('dependencies', []),
                estimated_hours=subtask_dict.get('estimated_hours'),
                complexity=subtask_dict.get('complexity'),
                agent_type=subtask_dict.get('agent_type', 'dev_agent'),
                created_at=datetime.now(),
                metadata=metadata
            )
        else:
            task_obj = subtask_dict
        
        # Call through circuit breaker (both dev and fix use execute_task)
        if self.dev_breaker:
            result = await self.dev_breaker.call(
                self.dev_agent.execute_task,
                task=task_obj
            )
        else:
            # No circuit breaker - call directly
            result = await self.dev_agent.execute_task(
                task=task_obj
            )
        
        return result
    
    async def _process_qa_task_enhanced(self, task: QueueTask) -> Optional[QueueTask]:
        """
        Process QA task with circuit breaker and event routing.
        
        Args:
            task: QA task to process
            
        Returns:
            Result for output queue (or None if routing via events)
        """
        try:
            logger.info(f"🧪 Processing QA task: {task.task_id}")
            
            payload = task.payload
            subtask = payload.get("subtask")
            dev_result = payload.get("dev_result")
            websocket = payload.get("websocket")
            project_desc = payload.get("project_desc")
            
            if not self.qa_agent:
                raise ValueError("QA agent not set")
            
            # Convert subtask dict to Task object (same as DevAgent)
            from models.task import Task
            from models.enums import TaskStatus
            
            subtask_dict = subtask if isinstance(subtask, dict) else subtask.to_dict()

            metadata = dict(subtask_dict.get('metadata') or {})
            plan = payload.get("plan")
            if isinstance(plan, dict):
                plan_id = plan.get('id') or plan.get('plan_id')
                if plan_id and metadata.get('plan_id') is None:
                    metadata['plan_id'] = plan_id

            # Add dev context for QA agent
            metadata['dev_result'] = dev_result
            metadata['project_desc'] = project_desc

            task_obj = Task(
                id=subtask_dict.get('id', f"task_{task.task_id}"),
                title=subtask_dict.get('title', ''),
                description=subtask_dict.get('description', ''),
                priority=subtask_dict.get('priority', 5),
                status=TaskStatus.PENDING,
                dependencies=subtask_dict.get('dependencies', []),
                estimated_hours=subtask_dict.get('estimated_hours'),
                complexity=subtask_dict.get('complexity'),
                agent_type=subtask_dict.get('agent_type', 'qa_agent'),
                metadata=metadata
            )
            
            # Call through circuit breaker
            if self.qa_breaker:
                result_task = await self.qa_breaker.call(
                    self.qa_agent.execute_task,
                    task=task_obj
                )
            else:
                result_task = await self.qa_agent.execute_task(
                    task=task_obj
                )
            
            # Convert Task result back to dict for pipeline
            qa_result = result_task.to_dict() if hasattr(result_task, 'to_dict') else result_task
            
            # Emit event based on QA result (check task status)
            tests_passed = (
                result_task.status == TaskStatus.COMPLETED 
                if hasattr(result_task, 'status') 
                else qa_result.get("status") == "completed"
            )
            
            if tests_passed:
                event = Event(
                    event_type=EventType.QA_PASSED,
                    task_id=task.task_id,
                    payload={
                        **payload,
                        'qa_result': qa_result,
                        'metadata': result_task.metadata if hasattr(result_task, 'metadata') else {}
                    },
                    timestamp=datetime.now()
                )
            else:
                event = Event(
                    event_type=EventType.QA_FAILED,
                    task_id=task.task_id,
                    payload={
                        **payload,
                        'qa_result': qa_result,
                        'metadata': result_task.metadata if hasattr(result_task, 'metadata') else {}
                    },
                    timestamp=datetime.now()
                )
            
            await self.event_router.route_event(event)
            
            return None  # Routing via events
            
        except CircuitBreakerOpenError as cbe:
            logger.warning(
                f"⚠️  Circuit breaker OPEN for QA task {task.task_id} - "
                f"will retry after timeout. Task will be requeued."
            )
            # Let the task queue's retry mechanism handle it
            raise
        except Exception as e:
            logger.error(
                f"❌ Failed processing QA task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _process_deploy_task_enhanced(self, task: QueueTask) -> None:
        """
        Process deploy task with circuit breaker.
        
        Args:
            task: Deploy task to process
        """
        try:
            logger.info(f"🚀 Processing deploy task: {task.task_id}")
            
            payload = task.payload
            subtask = payload.get("subtask")
            qa_result = payload.get("qa_result")
            websocket = payload.get("websocket")
            plan = payload.get("plan")

            if not self.ops_agent:
                raise ValueError("Ops agent not set")

            from models.task import Task
            from models.enums import TaskStatus

            subtask_dict = subtask if isinstance(subtask, dict) else subtask.to_dict()

            metadata = dict(subtask_dict.get('metadata') or {})

            # Ensure plan metadata is available for Ops agent
            if isinstance(plan, dict):
                plan_id = plan.get('id') or plan.get('plan_id')
                if plan_id and metadata.get('plan_id') is None:
                    metadata['plan_id'] = plan_id

            if qa_result is not None:
                metadata['qa_result'] = qa_result

            qa_payload_meta = payload.get('metadata') or {}
            if isinstance(qa_payload_meta, dict):
                for key in ('qa_confidence', 'qa_mode', 'qa_issues'):
                    if key in qa_payload_meta and metadata.get(key) is None:
                        metadata[key] = qa_payload_meta[key]
                if not metadata.get('plan_id'):
                    plan_id = qa_payload_meta.get('plan_id')
                    if plan_id:
                        metadata['plan_id'] = plan_id

            metadata['deployment_context'] = {
                'was_fixed': payload.get('was_fixed', False),
                'skip_qa_retest': payload.get('skip_qa_retest', False),
                'has_known_issues': payload.get('has_known_issues', False),
                'qa_status': payload.get('qa_status', 'passed')
            }

            description = subtask_dict.get('description', '')
            if payload.get('was_fixed'):
                description = f"DEPLOY FIX: {description}"
            elif payload.get('has_known_issues'):
                description = f"DEPLOY WITH WARNINGS: {description}"

            default_priority = subtask_dict.get('priority')
            if default_priority is None:
                default_priority = TaskPriority.NORMAL.value

            deploy_task_obj = Task(
                id=subtask_dict.get('id', f"deploy_{task.task_id}"),
                title=subtask_dict.get('title', 'Deployment Task'),
                description=description,
                priority=default_priority,
                status=TaskStatus.PENDING,
                dependencies=subtask_dict.get('dependencies', []),
                estimated_hours=subtask_dict.get('estimated_hours'),
                complexity=subtask_dict.get('complexity'),
                agent_type='ops_agent',
                metadata=metadata
            )

            # Call through circuit breaker using ops agent execute_task
            if self.ops_breaker:
                await self.ops_breaker.call(
                    self.ops_agent.execute_task,
                    task=deploy_task_obj
                )
            else:
                await self.ops_agent.execute_task(
                    task=deploy_task_obj
                )
            
            self.completed_tasks += 1
            
            logger.info(
                f"✅ Deploy task {task.task_id} completed "
                f"(total: {self.completed_tasks})"
            )
            
        except CircuitBreakerOpenError as cbe:
            logger.warning(
                f"⚠️  Circuit breaker OPEN for deploy task {task.task_id} - "
                f"will retry after timeout. Task will be requeued."
            )
            # Let the task queue's retry mechanism handle it
            raise
        except Exception as e:
            logger.error(
                f"❌ Failed processing deploy task {task.task_id}: {e}",
                exc_info=True
            )
            raise
    
    # ========================================================================
    # Start/Stop with Enhanced Pools
    # ========================================================================
    
    async def start(self):
        """Start enhanced pipeline with auto-scaling and unified pools."""
        if self.is_running:
            logger.warning("⚠️ EnhancedPipelineManager: Already running")
            return
        
        logger.info("🚀 EnhancedPipelineManager: Starting enhanced pipeline...")
        
        # Create unified dev+fix pool with auto-scaling
        self.unified_pool = UnifiedWorkerPool(
            name="UnifiedDevFixPool",
            min_workers=self.dev_workers_min,
            max_workers=self.dev_workers_max,
            task_queue=self.unified_queue,
            dev_func=self._process_dev_task_enhanced,
            fix_func=self._process_fix_task_enhanced,
            output_queue=None,  # Using event routing
            scale_up_threshold=self.scale_up_threshold,
            scale_down_threshold=self.scale_down_threshold
        )
        
        # Create auto-scaling QA pool
        self.qa_pool = AutoScalingWorkerPool(
            name="QAPool",
            min_workers=self.qa_workers_min,
            max_workers=self.qa_workers_max,
            task_queue=self.qa_queue,
            process_func=self._process_qa_task_enhanced,
            output_queue=None,  # Using event routing
            scale_up_threshold=self.scale_up_threshold,
            scale_down_threshold=self.scale_down_threshold
        )
        
        # Create deploy pool (fixed size, no auto-scaling needed)
        from utils.worker_pool import WorkerPool
        self.deploy_pool = WorkerPool(
            name="DeployPool",
            worker_count=self.deploy_workers_count,
            task_queue=self.deploy_queue,
            process_func=self._process_deploy_task_enhanced,
            output_queue=None
        )
        
        # Start all pools
        await self.unified_pool.start()
        await self.qa_pool.start()
        await self.deploy_pool.start()
        
        self.is_running = True
        self.start_time = datetime.now()
        
        logger.info(
            f"✅ EnhancedPipelineManager: All pools started "
            f"(unified:{self.dev_workers_min}-{self.dev_workers_max}, "
            f"qa:{self.qa_workers_min}-{self.qa_workers_max}, "
            f"deploy:{self.deploy_workers_count})"
        )
    
    async def stop(self, graceful: bool = True, timeout: float = 60.0):
        """Stop enhanced pipeline."""
        if not self.is_running:
            logger.warning("⚠️ EnhancedPipelineManager: Not running")
            return
        
        logger.info(
            f"🛑 EnhancedPipelineManager: Stopping pipeline "
            f"(graceful={graceful}, timeout={timeout}s)..."
        )
        
        # Stop all pools
        await asyncio.gather(
            self.deploy_pool.stop(graceful, timeout / 3),
            self.qa_pool.stop(graceful, timeout / 3),
            self.unified_pool.stop(graceful, timeout / 3)
        )
        
        self.is_running = False
        
        # Log final statistics
        stats = self.get_enhanced_stats()
        logger.info(
            f"📊 EnhancedPipelineManager: Final stats\n"
            f"   Tasks: {stats['total_tasks']} total, "
            f"{stats['completed_tasks']} completed, "
            f"{stats['failed_tasks']} failed\n"
            f"   Cache: {stats['cache']['hit_rate']}% hit rate\n"
            f"   DLQ: {stats['dlq_size']} items\n"
            f"   Uptime: {stats['uptime']:.1f}s"
        )
        
        logger.info("✅ EnhancedPipelineManager: Pipeline stopped")
    
    # ========================================================================
    # Task Submission with Priority Assignment
    # ========================================================================
    
    async def submit_dev_task(
        self,
        task_id: str,
        subtask: Dict[str, Any],
        websocket,
        project_desc: str,
        plan: Dict[str, Any],
        priority: Optional[int] = None
    ):
        """
        Submit dev task with automatic priority assignment.
        
        Args:
            task_id: Unique task identifier
            subtask: Task data
            websocket: WebSocket for updates
            project_desc: Project description
            plan: Full plan
            priority: Manual priority (None = auto-assign)
        """
        # Auto-assign priority if not provided
        if priority is None:
            priority = self.priority_assigner.assign_priority(subtask)
        
        task = QueueTask(
            task_id=task_id,
            task_type="dev",
            payload={
                "subtask": subtask,
                "websocket": websocket,
                "project_desc": project_desc,
                "plan": plan,
                "priority": priority
            },
            priority=priority
        )
        
        await self.unified_queue.put(task)
        self.total_tasks += 1
        
        logger.info(
            f"📥 Submitted dev task {task_id} "
            f"(priority: {priority}, total: {self.total_tasks})"
        )
    
    # ========================================================================
    # Dependency-Aware Task Submission (Phase 2.1)
    # ========================================================================
    
    async def analyze_and_submit_plan(
        self,
        plan: Dict[str, Any],
        websocket,
        project_desc: str
    ) -> Dict[str, Any]:
        """
        Analyze plan dependencies and submit tasks in dependency-ordered batches.
        
        Args:
            plan: Complete plan dictionary with tasks
            websocket: WebSocket for updates
            project_desc: Project description
            
        Returns:
            Analysis statistics
        """
        if not self.use_dependency_analysis:
            # Fallback to sequential submission
            logger.info("⚠️ Dependency analysis disabled, using sequential submission")
            return {'batches': 0, 'mode': 'sequential'}
        
        logger.info("🔍 Analyzing plan dependencies...")
        
        # Extract tasks from plan
        tasks = plan.get('tasks', [])
        if not tasks:
            logger.warning("No tasks found in plan")
            return {'batches': 0, 'tasks': 0}
        
        # Build dependency graph using our analyzer
        self.dependency_analyzer.build_dependency_graph(tasks)
        
        # Perform topological sort
        batches = self.dependency_analyzer.topological_sort()
        
        # Store batches for status tracking
        self.dependency_batches = batches
        
        # Store critical path files for priority assignment
        critical_path_files, critical_path_length = self.dependency_analyzer.analyze_critical_path()
        self.critical_path_files = set(critical_path_files) if critical_path_files else set()
        
        # Get statistics from analyzer
        stats = self.dependency_analyzer.get_statistics()
        
        logger.info(
            f"📊 Dependency Analysis Complete:\n"
            f"   Total Tasks: {len(tasks)}\n"
            f"   Batches: {len(batches)}\n"
            f"   Total Files: {stats['total_files']}\n"
            f"   Total Dependencies: {stats['total_dependencies']}\n"
            f"   Critical Path Length: {stats['critical_path_length']}\n"
            f"   Critical Path Files: {len(self.critical_path_files)}"
        )
        
        # Submit tasks batch by batch
        await self._submit_dependency_batches(
            self.dependency_batches,
            websocket,
            project_desc,
            plan
        )
        
        return {
            'batches': len(self.dependency_batches),
            'tasks': len(tasks),
            'stats': stats
        }
    
    async def _submit_dependency_batches(
        self,
        batches: List,
        websocket,
        project_desc: str,
        plan: Dict[str, Any]
    ):
        """
        Submit tasks in dependency-ordered batches.
        
        Args:
            batches: List of DependencyBatch objects
            websocket: WebSocket for updates
            project_desc: Project description
            plan: Full plan dictionary
        """
        for batch_idx, batch in enumerate(batches, 1):
            logger.info(
                f"📦 Submitting Batch {batch_idx}/{len(batches)} "
                f"({len(batch.files)} tasks, level: {batch.level})"
            )
            
            # Submit all tasks in this batch (they can run in parallel)
            submission_tasks = []
            for file_dep in batch.files:
                task_id = f"dev_{file_dep.file_path}_{batch_idx}"
                
                # Find matching task data from plan
                task_data = self._find_task_by_file(plan, file_dep.file_path)
                if not task_data:
                    logger.warning(f"⚠️ No task data found for {file_dep.file_path}")
                    continue
                
                # Assign priority (HIGH for critical path)
                priority = (
                    TaskPriority.HIGH.value 
                    if file_dep.file_path in self.critical_path_files 
                    else TaskPriority.NORMAL.value
                )
                
                submission_tasks.append(
                    self.submit_dev_task(
                        task_id=task_id,
                        subtask=task_data,
                        websocket=websocket,
                        project_desc=project_desc,
                        plan=plan,
                        priority=priority
                    )
                )
            
            # Submit all tasks in batch concurrently
            if submission_tasks:
                await asyncio.gather(*submission_tasks)
            
            logger.info(f"✅ Batch {batch_idx} submitted ({len(submission_tasks)} tasks)")
    
    def _find_task_by_file(
        self,
        plan: Dict[str, Any],
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find task data by file path.
        
        Args:
            plan: Plan dictionary
            file_path: Target file path
            
        Returns:
            Task data dict or None
        """
        tasks = plan.get('tasks', [])
        for task in tasks:
            # Check if this task generates the target file
            files = task.get('files_to_generate', [])
            if file_path in files or any(file_path.endswith(f) for f in files):
                return task
            
            # Also check title as fallback
            if file_path in task.get('title', '').lower().replace(' ', '_'):
                return task
        
        return None
    
    # ========================================================================
    # Enhanced Statistics
    # ========================================================================
    
    def get_enhanced_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive enhanced pipeline statistics.
        
        Returns:
            Dictionary with all metrics including cache, circuit breakers, DLQ
        """
        base_stats = self.get_stats()
        
        enhanced_stats = {
            **base_stats,
            'cache': self.result_cache.get_stats() if self.result_cache else {},
            'circuit_breakers': {
                'dev': self.dev_breaker.get_stats() if self.dev_breaker else {},
                'qa': self.qa_breaker.get_stats() if self.qa_breaker else {},
                'ops': self.ops_breaker.get_stats() if self.ops_breaker else {}
            },
            'event_router': self.event_router.get_stats(),
            'dlq_size': len(self.event_router.get_dlq_items()),
            'priority_stats': self.priority_assigner.get_stats(),
            'unified_pool': (
                self.unified_pool.get_unified_stats()
                if self.unified_pool
                else {}
            ),
            'dependency_analysis': {
                'enabled': self.use_dependency_analysis,
                'batches': len(self.dependency_batches),
                'analyzer_stats': self.dependency_analyzer.get_stats()
            }
        }
        
        return enhanced_stats
    
    def get_dlq_items(self) -> List[Event]:
        """Get items from Dead Letter Queue."""
        return self.event_router.get_dlq_items()
    
    def retry_dlq_item(self, task_id: str) -> bool:
        """
        Retry a specific DLQ item.
        
        Args:
            task_id: Task ID to retry
            
        Returns:
            True if item was found and retried
        """
        return self.event_router.retry_dlq_item(task_id)
    
    def clear_cache(self):
        """Clear result cache."""
        if self.result_cache:
            self.result_cache.clear()
            logger.info("🗑️ Result cache cleared")
    
    async def reset_circuit_breakers(self):
        """Manually reset all circuit breakers to CLOSED state."""
        if self.dev_breaker:
            await self.dev_breaker.reset()
        if self.qa_breaker:
            await self.qa_breaker.reset()
        if self.ops_breaker:
            await self.ops_breaker.reset()
        logger.info("🔄 All circuit breakers reset")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"EnhancedPipelineManager("
            f"running={self.is_running}, "
            f"completed={self.completed_tasks}/{self.total_tasks}, "
            f"cache_enabled={self.cache_enabled}, "
            f"circuit_breaker_enabled={self.circuit_breaker_enabled})"
        )
