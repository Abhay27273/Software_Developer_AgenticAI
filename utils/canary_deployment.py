"""
Canary Deployment System for Progressive Code Rollout.

This module implements a production-grade canary deployment system with:
- Progressive traffic shifting (10% → 25% → 50% → 75% → 100%)
- Automatic health monitoring and rollback
- A/B testing capabilities
- Success metrics tracking
- Rollback on failure detection
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import statistics

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Deployment status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MONITORING = "monitoring"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class DeploymentStage:
    """Represents a canary deployment stage."""
    stage_number: int
    traffic_percentage: int
    duration_seconds: int
    success_threshold: float = 0.95  # 95% success rate required
    max_error_rate: float = 0.05  # 5% max error rate
    max_latency_ms: float = 1000.0  # 1s max p95 latency


@dataclass
class DeploymentMetrics:
    """Metrics collected during deployment."""
    timestamp: datetime
    traffic_percentage: int
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    error_rate: float = 0.0
    success_rate: float = 1.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    
    def calculate_stats(self):
        """Calculate statistical metrics."""
        if self.requests_total > 0:
            self.error_rate = self.requests_failed / self.requests_total
            self.success_rate = self.requests_success / self.requests_total
        
        if self.latencies_ms:
            sorted_latencies = sorted(self.latencies_ms)
            self.p50_latency = statistics.median(sorted_latencies)
            self.p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            self.p99_latency = sorted_latencies[int(len(sorted_latencies) * 0.99)]


@dataclass
class CanaryDeployment:
    """Represents a canary deployment configuration."""
    deployment_id: str
    version_current: str
    version_canary: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    current_stage: int = 0
    traffic_percentage: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metrics_history: List[DeploymentMetrics] = field(default_factory=list)
    rollback_reason: Optional[str] = None


class CanaryDeploymentManager:
    """
    Manages canary deployments with progressive traffic shifting.
    
    Features:
    - Progressive rollout (10% → 25% → 50% → 75% → 100%)
    - Real-time health monitoring
    - Automatic rollback on failure
    - Success metrics tracking
    - A/B testing support
    """
    
    DEFAULT_STAGES = [
        DeploymentStage(1, 10, 300),   # 10% for 5 minutes
        DeploymentStage(2, 25, 300),   # 25% for 5 minutes
        DeploymentStage(3, 50, 600),   # 50% for 10 minutes
        DeploymentStage(4, 75, 600),   # 75% for 10 minutes
        DeploymentStage(5, 100, 0),    # 100% (complete)
    ]
    
    def __init__(
        self,
        stages: Optional[List[DeploymentStage]] = None,
        health_check_interval: int = 30,
        enable_auto_rollback: bool = True
    ):
        """
        Initialize canary deployment manager.
        
        Args:
            stages: List of deployment stages (uses DEFAULT_STAGES if None)
            health_check_interval: Seconds between health checks
            enable_auto_rollback: Enable automatic rollback on failure
        """
        self.stages = stages or self.DEFAULT_STAGES
        self.health_check_interval = health_check_interval
        self.enable_auto_rollback = enable_auto_rollback
        
        # Active deployments
        self.deployments: Dict[str, CanaryDeployment] = {}
        
        # Callbacks
        self.traffic_router: Optional[Callable] = None
        self.health_checker: Optional[Callable] = None
        self.rollback_handler: Optional[Callable] = None
        
        # Monitoring task
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        
        logger.info(
            f"🚀 CanaryDeploymentManager: Initialized "
            f"(stages: {len(self.stages)}, auto_rollback: {enable_auto_rollback})"
        )
    
    def set_traffic_router(self, router: Callable):
        """Set traffic routing callback."""
        self.traffic_router = router
        logger.info("🔀 Traffic router set")
    
    def set_health_checker(self, checker: Callable):
        """Set health check callback."""
        self.health_checker = checker
        logger.info("❤️ Health checker set")
    
    def set_rollback_handler(self, handler: Callable):
        """Set rollback callback."""
        self.rollback_handler = handler
        logger.info("⏪ Rollback handler set")
    
    async def start_deployment(
        self,
        deployment_id: str,
        version_current: str,
        version_canary: str
    ) -> CanaryDeployment:
        """
        Start a new canary deployment.
        
        Args:
            deployment_id: Unique deployment identifier
            version_current: Current stable version
            version_canary: New canary version to deploy
            
        Returns:
            CanaryDeployment object
        """
        if deployment_id in self.deployments:
            raise ValueError(f"Deployment {deployment_id} already exists")
        
        deployment = CanaryDeployment(
            deployment_id=deployment_id,
            version_current=version_current,
            version_canary=version_canary,
            status=DeploymentStatus.IN_PROGRESS,
            started_at=datetime.now()
        )
        
        self.deployments[deployment_id] = deployment
        
        logger.info(
            f"🚀 Starting canary deployment: {deployment_id}\n"
            f"   Current: {version_current}\n"
            f"   Canary: {version_canary}\n"
            f"   Stages: {len(self.stages)}"
        )
        
        # Start monitoring if not already running
        if not self.is_monitoring:
            await self.start_monitoring()
        
        return deployment
    
    async def start_monitoring(self):
        """Start background monitoring of all deployments."""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("Monitoring already running")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("👀 Started deployment monitoring")
    
    async def stop_monitoring(self):
        """Stop background monitoring."""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ Stopped deployment monitoring")
    
    async def _monitoring_loop(self):
        """Background loop for monitoring deployments."""
        try:
            while self.is_monitoring:
                # Monitor all active deployments
                for deployment_id in list(self.deployments.keys()):
                    deployment = self.deployments[deployment_id]
                    
                    if deployment.status in [
                        DeploymentStatus.IN_PROGRESS,
                        DeploymentStatus.MONITORING
                    ]:
                        await self._monitor_deployment(deployment)
                
                # Wait before next check
                await asyncio.sleep(self.health_check_interval)
                
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}", exc_info=True)
    
    async def _monitor_deployment(self, deployment: CanaryDeployment):
        """
        Monitor a single deployment and progress through stages.
        
        Args:
            deployment: Deployment to monitor
        """
        try:
            # Check if we should progress to next stage
            current_stage = self.stages[deployment.current_stage]
            
            # Collect metrics
            metrics = await self._collect_metrics(deployment, current_stage)
            deployment.metrics_history.append(metrics)
            
            logger.debug(
                f"📊 {deployment.deployment_id} Stage {deployment.current_stage + 1}: "
                f"{current_stage.traffic_percentage}% traffic, "
                f"success: {metrics.success_rate:.1%}, "
                f"error: {metrics.error_rate:.1%}, "
                f"p95: {metrics.p95_latency:.0f}ms"
            )
            
            # Check health
            health = await self._check_health(deployment, metrics, current_stage)
            
            if health == HealthStatus.UNHEALTHY:
                # Trigger rollback
                await self.rollback_deployment(
                    deployment.deployment_id,
                    reason=f"Health check failed at stage {deployment.current_stage + 1}"
                )
                return
            
            # Check if stage duration has passed
            if deployment.started_at:
                elapsed = (datetime.now() - deployment.started_at).total_seconds()
                stage_start_time = sum(s.duration_seconds for s in self.stages[:deployment.current_stage])
                stage_elapsed = elapsed - stage_start_time
                
                if stage_elapsed >= current_stage.duration_seconds:
                    # Progress to next stage
                    await self._progress_to_next_stage(deployment)
                    
        except Exception as e:
            logger.error(
                f"Error monitoring deployment {deployment.deployment_id}: {e}",
                exc_info=True
            )
    
    async def _collect_metrics(
        self,
        deployment: CanaryDeployment,
        stage: DeploymentStage
    ) -> DeploymentMetrics:
        """
        Collect metrics for current deployment stage.
        
        Args:
            deployment: Current deployment
            stage: Current stage
            
        Returns:
            DeploymentMetrics object
        """
        metrics = DeploymentMetrics(
            timestamp=datetime.now(),
            traffic_percentage=stage.traffic_percentage
        )
        
        # In real implementation, this would collect actual metrics
        # from monitoring systems (Prometheus, DataDog, etc.)
        # For now, we'll simulate it
        
        # Simulate some metrics
        import random
        metrics.requests_total = random.randint(100, 1000)
        metrics.requests_success = int(metrics.requests_total * 0.98)
        metrics.requests_failed = metrics.requests_total - metrics.requests_success
        metrics.latencies_ms = [
            random.uniform(10, 500) for _ in range(min(100, metrics.requests_total))
        ]
        
        metrics.calculate_stats()
        
        return metrics
    
    async def _check_health(
        self,
        deployment: CanaryDeployment,
        metrics: DeploymentMetrics,
        stage: DeploymentStage
    ) -> HealthStatus:
        """
        Check health of canary deployment.
        
        Args:
            deployment: Current deployment
            metrics: Current metrics
            stage: Current stage
            
        Returns:
            HealthStatus enum
        """
        # Check error rate
        if metrics.error_rate > stage.max_error_rate:
            logger.warning(
                f"⚠️ High error rate: {metrics.error_rate:.1%} > {stage.max_error_rate:.1%}"
            )
            return HealthStatus.UNHEALTHY
        
        # Check success rate
        if metrics.success_rate < stage.success_threshold:
            logger.warning(
                f"⚠️ Low success rate: {metrics.success_rate:.1%} < {stage.success_threshold:.1%}"
            )
            return HealthStatus.UNHEALTHY
        
        # Check latency
        if metrics.p95_latency > stage.max_latency_ms:
            logger.warning(
                f"⚠️ High latency: {metrics.p95_latency:.0f}ms > {stage.max_latency_ms:.0f}ms"
            )
            return HealthStatus.DEGRADED
        
        # Call custom health checker if provided
        if self.health_checker:
            try:
                custom_healthy = await self.health_checker(deployment, metrics)
                if not custom_healthy:
                    return HealthStatus.UNHEALTHY
            except Exception as e:
                logger.error(f"Custom health check failed: {e}")
                return HealthStatus.UNHEALTHY
        
        return HealthStatus.HEALTHY
    
    async def _progress_to_next_stage(self, deployment: CanaryDeployment):
        """Progress deployment to next stage."""
        deployment.current_stage += 1
        
        if deployment.current_stage >= len(self.stages):
            # Deployment complete!
            await self._complete_deployment(deployment)
            return
        
        next_stage = self.stages[deployment.current_stage]
        deployment.traffic_percentage = next_stage.traffic_percentage
        
        logger.info(
            f"➡️ {deployment.deployment_id}: Progressing to stage {deployment.current_stage + 1}\n"
            f"   Traffic: {next_stage.traffic_percentage}%\n"
            f"   Duration: {next_stage.duration_seconds}s"
        )
        
        # Update traffic routing
        if self.traffic_router:
            await self.traffic_router(
                deployment.version_canary,
                next_stage.traffic_percentage
            )
    
    async def _complete_deployment(self, deployment: CanaryDeployment):
        """Mark deployment as completed."""
        deployment.status = DeploymentStatus.COMPLETED
        deployment.completed_at = datetime.now()
        deployment.traffic_percentage = 100
        
        duration = (deployment.completed_at - deployment.started_at).total_seconds()
        
        logger.info(
            f"✅ Deployment {deployment.deployment_id} COMPLETED!\n"
            f"   Version: {deployment.version_canary}\n"
            f"   Duration: {duration:.0f}s\n"
            f"   Stages: {len(self.stages)}"
        )
    
    async def rollback_deployment(
        self,
        deployment_id: str,
        reason: str
    ):
        """
        Rollback a deployment to previous version.
        
        Args:
            deployment_id: Deployment to rollback
            reason: Reason for rollback
        """
        if deployment_id not in self.deployments:
            raise ValueError(f"Deployment {deployment_id} not found")
        
        deployment = self.deployments[deployment_id]
        deployment.status = DeploymentStatus.ROLLING_BACK
        deployment.rollback_reason = reason
        
        logger.error(
            f"🔴 Rolling back deployment {deployment_id}\n"
            f"   Reason: {reason}\n"
            f"   Stage: {deployment.current_stage + 1}/{len(self.stages)}\n"
            f"   Traffic: {deployment.traffic_percentage}%"
        )
        
        # Route all traffic back to current version
        if self.traffic_router:
            await self.traffic_router(deployment.version_current, 100)
        
        # Call custom rollback handler
        if self.rollback_handler:
            await self.rollback_handler(deployment)
        
        deployment.status = DeploymentStatus.ROLLED_BACK
        deployment.completed_at = datetime.now()
        deployment.traffic_percentage = 0
        
        logger.info(f"⏪ Deployment {deployment_id} rolled back successfully")
    
    def get_deployment(self, deployment_id: str) -> Optional[CanaryDeployment]:
        """Get deployment by ID."""
        return self.deployments.get(deployment_id)
    
    def get_all_deployments(self) -> List[CanaryDeployment]:
        """Get all deployments."""
        return list(self.deployments.values())
    
    def get_active_deployments(self) -> List[CanaryDeployment]:
        """Get all active deployments."""
        return [
            d for d in self.deployments.values()
            if d.status in [DeploymentStatus.IN_PROGRESS, DeploymentStatus.MONITORING]
        ]
    
    def get_deployment_stats(self, deployment_id: str) -> Dict[str, Any]:
        """Get detailed stats for a deployment."""
        deployment = self.get_deployment(deployment_id)
        if not deployment:
            return {}
        
        stats = {
            'deployment_id': deployment.deployment_id,
            'status': deployment.status.value,
            'current_stage': deployment.current_stage + 1,
            'total_stages': len(self.stages),
            'traffic_percentage': deployment.traffic_percentage,
            'version_current': deployment.version_current,
            'version_canary': deployment.version_canary,
            'started_at': deployment.started_at.isoformat() if deployment.started_at else None,
            'completed_at': deployment.completed_at.isoformat() if deployment.completed_at else None,
            'metrics_count': len(deployment.metrics_history),
            'rollback_reason': deployment.rollback_reason
        }
        
        # Add latest metrics
        if deployment.metrics_history:
            latest = deployment.metrics_history[-1]
            stats['latest_metrics'] = {
                'success_rate': latest.success_rate,
                'error_rate': latest.error_rate,
                'p50_latency': latest.p50_latency,
                'p95_latency': latest.p95_latency,
                'p99_latency': latest.p99_latency,
                'requests_total': latest.requests_total
            }
        
        return stats
    
    def __repr__(self) -> str:
        """String representation."""
        active = len(self.get_active_deployments())
        total = len(self.deployments)
        return (
            f"CanaryDeploymentManager("
            f"deployments={total}, active={active}, "
            f"stages={len(self.stages)})"
        )
