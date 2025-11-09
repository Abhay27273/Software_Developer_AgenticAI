"""
Unit tests for Phase 2.4: Canary Deployment System.

Tests cover:
- Deployment lifecycle (start, monitor, complete)
- Progressive traffic shifting through stages
- Health monitoring and failure detection
- Automatic rollback on failures
- Metrics collection and analysis
- A/B testing scenarios
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from utils.canary_deployment import (
    CanaryDeploymentManager, CanaryDeployment, DeploymentStage,
    DeploymentStatus, HealthStatus, DeploymentMetrics
)


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestCanaryDeploymentBasics:
    """Test basic canary deployment functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create canary deployment manager."""
        return CanaryDeploymentManager(
            health_check_interval=1,  # Fast for testing
            enable_auto_rollback=True
        )
    
    def test_manager_initialization(self, manager):
        """Test manager initializes correctly."""
        assert manager is not None
        assert len(manager.stages) == 5  # Default stages
        assert manager.health_check_interval == 1
        assert manager.enable_auto_rollback is True
        assert len(manager.deployments) == 0
    
    def test_custom_stages(self):
        """Test manager with custom stages."""
        custom_stages = [
            DeploymentStage(1, 20, 60),
            DeploymentStage(2, 50, 120),
            DeploymentStage(3, 100, 0)
        ]
        
        manager = CanaryDeploymentManager(stages=custom_stages)
        assert len(manager.stages) == 3
        assert manager.stages[0].traffic_percentage == 20
        assert manager.stages[1].traffic_percentage == 50
    
    @pytest.mark.asyncio
    async def test_start_deployment(self, manager):
        """Test starting a new deployment."""
        deployment = await manager.start_deployment(
            deployment_id="deploy-001",
            version_current="v1.0.0",
            version_canary="v1.1.0"
        )
        
        assert deployment is not None
        assert deployment.deployment_id == "deploy-001"
        assert deployment.version_current == "v1.0.0"
        assert deployment.version_canary == "v1.1.0"
        assert deployment.status == DeploymentStatus.IN_PROGRESS
        assert deployment.current_stage == 0
        assert deployment.started_at is not None
    
    @pytest.mark.asyncio
    async def test_duplicate_deployment_rejected(self, manager):
        """Test that duplicate deployment IDs are rejected."""
        await manager.start_deployment("deploy-001", "v1.0", "v1.1")
        
        with pytest.raises(ValueError, match="already exists"):
            await manager.start_deployment("deploy-001", "v1.0", "v1.2")
    
    @pytest.mark.asyncio
    async def test_set_callbacks(self, manager):
        """Test setting callback functions."""
        router = AsyncMock()
        checker = AsyncMock()
        rollback = AsyncMock()
        
        manager.set_traffic_router(router)
        manager.set_health_checker(checker)
        manager.set_rollback_handler(rollback)
        
        assert manager.traffic_router == router
        assert manager.health_checker == checker
        assert manager.rollback_handler == rollback


# ============================================================================
# Deployment Lifecycle Tests
# ============================================================================

class TestDeploymentLifecycle:
    """Test full deployment lifecycle."""
    
    @pytest.fixture
    def fast_manager(self):
        """Create manager with fast stages for testing."""
        fast_stages = [
            DeploymentStage(1, 25, 1),   # 1 second
            DeploymentStage(2, 50, 1),   # 1 second
            DeploymentStage(3, 100, 0),  # Complete
        ]
        return CanaryDeploymentManager(
            stages=fast_stages,
            health_check_interval=0.5,
            enable_auto_rollback=True
        )
    
    @pytest.mark.asyncio
    async def test_deployment_progresses_through_stages(self, fast_manager):
        """Test deployment progresses through all stages."""
        # Mock traffic router
        router_calls = []
        async def mock_router(version, percentage):
            router_calls.append((version, percentage))
        
        fast_manager.set_traffic_router(mock_router)
        
        # Start deployment
        deployment = await fast_manager.start_deployment(
            "deploy-001", "v1.0", "v1.1"
        )
        
        # Wait for completion
        await asyncio.sleep(3)
        
        # Check final status
        deployment = fast_manager.get_deployment("deploy-001")
        assert deployment.status == DeploymentStatus.COMPLETED
        assert deployment.traffic_percentage == 100
        assert deployment.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_get_deployment_stats(self, fast_manager):
        """Test getting deployment statistics."""
        deployment = await fast_manager.start_deployment(
            "deploy-001", "v1.0", "v1.1"
        )
        
        stats = fast_manager.get_deployment_stats("deploy-001")
        
        assert stats['deployment_id'] == "deploy-001"
        assert stats['status'] == DeploymentStatus.IN_PROGRESS.value
        assert stats['version_current'] == "v1.0"
        assert stats['version_canary'] == "v1.1"
        assert 'started_at' in stats
    
    @pytest.mark.asyncio
    async def test_get_all_deployments(self, fast_manager):
        """Test getting all deployments."""
        await fast_manager.start_deployment("deploy-001", "v1.0", "v1.1")
        await fast_manager.start_deployment("deploy-002", "v1.1", "v1.2")
        
        all_deployments = fast_manager.get_all_deployments()
        assert len(all_deployments) == 2
        
        active = fast_manager.get_active_deployments()
        assert len(active) == 2


# ============================================================================
# Health Monitoring Tests
# ============================================================================

class TestHealthMonitoring:
    """Test health monitoring and failure detection."""
    
    @pytest.fixture
    def manager_with_strict_thresholds(self):
        """Create manager with strict health thresholds."""
        stages = [
            DeploymentStage(
                1, 50, 10,
                success_threshold=0.99,  # Very strict
                max_error_rate=0.01,
                max_latency_ms=100.0
            ),
            DeploymentStage(2, 100, 0)
        ]
        return CanaryDeploymentManager(
            stages=stages,
            health_check_interval=0.5
        )
    
    @pytest.mark.asyncio
    async def test_health_check_with_good_metrics(self, manager_with_strict_thresholds):
        """Test health check passes with good metrics."""
        deployment = CanaryDeployment(
            deployment_id="test",
            version_current="v1.0",
            version_canary="v1.1"
        )
        
        metrics = DeploymentMetrics(
            timestamp=datetime.now(),
            traffic_percentage=50,
            requests_total=1000,
            requests_success=995,
            requests_failed=5,
            latencies_ms=[50.0] * 100
        )
        metrics.calculate_stats()
        
        stage = manager_with_strict_thresholds.stages[0]
        health = await manager_with_strict_thresholds._check_health(
            deployment, metrics, stage
        )
        
        assert health == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_health_check_fails_on_high_error_rate(self, manager_with_strict_thresholds):
        """Test health check fails with high error rate."""
        deployment = CanaryDeployment(
            deployment_id="test",
            version_current="v1.0",
            version_canary="v1.1"
        )
        
        metrics = DeploymentMetrics(
            timestamp=datetime.now(),
            traffic_percentage=50,
            requests_total=1000,
            requests_success=900,  # 90% success = 10% error (too high)
            requests_failed=100,
            latencies_ms=[50.0] * 100
        )
        metrics.calculate_stats()
        
        stage = manager_with_strict_thresholds.stages[0]
        health = await manager_with_strict_thresholds._check_health(
            deployment, metrics, stage
        )
        
        assert health == HealthStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_health_check_degraded_on_high_latency(self, manager_with_strict_thresholds):
        """Test health check reports degraded on high latency."""
        deployment = CanaryDeployment(
            deployment_id="test",
            version_current="v1.0",
            version_canary="v1.1"
        )
        
        metrics = DeploymentMetrics(
            timestamp=datetime.now(),
            traffic_percentage=50,
            requests_total=1000,
            requests_success=995,
            requests_failed=5,
            latencies_ms=[200.0] * 100  # High latency
        )
        metrics.calculate_stats()
        
        stage = manager_with_strict_thresholds.stages[0]
        health = await manager_with_strict_thresholds._check_health(
            deployment, metrics, stage
        )
        
        assert health == HealthStatus.DEGRADED


# ============================================================================
# Rollback Tests
# ============================================================================

class TestRollback:
    """Test automatic rollback functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create manager for rollback tests."""
        return CanaryDeploymentManager(
            health_check_interval=0.5,
            enable_auto_rollback=True
        )
    
    @pytest.mark.asyncio
    async def test_manual_rollback(self, manager):
        """Test manual rollback of deployment."""
        deployment = await manager.start_deployment(
            "deploy-001", "v1.0", "v1.1"
        )
        
        # Mock traffic router
        router_calls = []
        async def mock_router(version, percentage):
            router_calls.append((version, percentage))
        
        manager.set_traffic_router(mock_router)
        
        # Trigger rollback
        await manager.rollback_deployment(
            "deploy-001",
            reason="Manual rollback for testing"
        )
        
        # Verify rollback
        deployment = manager.get_deployment("deploy-001")
        assert deployment.status == DeploymentStatus.ROLLED_BACK
        assert deployment.rollback_reason == "Manual rollback for testing"
        assert deployment.traffic_percentage == 0
        assert deployment.completed_at is not None
        
        # Verify traffic was routed back to current version
        assert len(router_calls) > 0
        assert router_calls[-1] == ("v1.0", 100)
    
    @pytest.mark.asyncio
    async def test_rollback_calls_custom_handler(self, manager):
        """Test rollback calls custom handler."""
        deployment = await manager.start_deployment(
            "deploy-001", "v1.0", "v1.1"
        )
        
        # Mock rollback handler
        handler_called = []
        async def mock_handler(dep):
            handler_called.append(dep.deployment_id)
        
        manager.set_rollback_handler(mock_handler)
        
        # Trigger rollback
        await manager.rollback_deployment("deploy-001", "Test")
        
        assert len(handler_called) == 1
        assert handler_called[0] == "deploy-001"
    
    @pytest.mark.asyncio
    async def test_rollback_nonexistent_deployment(self, manager):
        """Test rollback of non-existent deployment fails."""
        with pytest.raises(ValueError, match="not found"):
            await manager.rollback_deployment("nonexistent", "Test")


# ============================================================================
# Metrics Tests
# ============================================================================

class TestMetrics:
    """Test metrics collection and calculation."""
    
    def test_metrics_calculation(self):
        """Test metrics statistical calculations."""
        metrics = DeploymentMetrics(
            timestamp=datetime.now(),
            traffic_percentage=50,
            requests_total=1000,
            requests_success=950,
            requests_failed=50,
            latencies_ms=[10.0, 20.0, 30.0, 40.0, 50.0] * 20
        )
        
        metrics.calculate_stats()
        
        assert metrics.error_rate == 0.05
        assert metrics.success_rate == 0.95
        assert metrics.p50_latency == 30.0
        assert metrics.p95_latency > 0
        assert metrics.p99_latency > 0
    
    def test_metrics_with_no_requests(self):
        """Test metrics with zero requests."""
        metrics = DeploymentMetrics(
            timestamp=datetime.now(),
            traffic_percentage=0
        )
        
        metrics.calculate_stats()
        
        assert metrics.error_rate == 0.0
        assert metrics.success_rate == 1.0


# ============================================================================
# Integration Tests
# ============================================================================

class TestCanaryIntegration:
    """Test complete canary deployment scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_successful_deployment(self):
        """Test complete successful deployment through all stages."""
        # Create fast stages
        stages = [
            DeploymentStage(1, 25, 0.5),
            DeploymentStage(2, 50, 0.5),
            DeploymentStage(3, 100, 0)
        ]
        
        manager = CanaryDeploymentManager(
            stages=stages,
            health_check_interval=0.3
        )
        
        # Track traffic changes
        traffic_changes = []
        async def track_traffic(version, percentage):
            traffic_changes.append((version, percentage))
        
        manager.set_traffic_router(track_traffic)
        
        # Start deployment
        deployment = await manager.start_deployment(
            "deploy-001", "v1.0", "v1.1"
        )
        
        # Wait for completion
        await asyncio.sleep(2.5)
        
        # Stop monitoring
        await manager.stop_monitoring()
        
        # Verify completion
        final_deployment = manager.get_deployment("deploy-001")
        assert final_deployment.status == DeploymentStatus.COMPLETED
        assert final_deployment.traffic_percentage == 100
        
        # Verify traffic progression
        assert len(traffic_changes) >= 2
    
    @pytest.mark.asyncio
    async def test_monitoring_start_stop(self):
        """Test starting and stopping monitoring."""
        manager = CanaryDeploymentManager()
        
        # Start monitoring
        await manager.start_monitoring()
        assert manager.is_monitoring is True
        assert manager.monitoring_task is not None
        
        # Stop monitoring
        await manager.stop_monitoring()
        assert manager.is_monitoring is False
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_deployments(self):
        """Test managing multiple deployments concurrently."""
        stages = [DeploymentStage(1, 100, 0)]  # Single stage for quick test
        manager = CanaryDeploymentManager(stages=stages, health_check_interval=0.5)
        
        # Start multiple deployments
        await manager.start_deployment("deploy-001", "v1.0", "v1.1")
        await manager.start_deployment("deploy-002", "v2.0", "v2.1")
        await manager.start_deployment("deploy-003", "v3.0", "v3.1")
        
        # Verify all active
        active = manager.get_active_deployments()
        assert len(active) == 3
        
        # Wait for completion
        await asyncio.sleep(1.5)
        
        # All should be completed
        for deploy_id in ["deploy-001", "deploy-002", "deploy-003"]:
            deployment = manager.get_deployment(deploy_id)
            assert deployment.status == DeploymentStatus.COMPLETED
        
        await manager.stop_monitoring()


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance of canary system."""
    
    @pytest.mark.asyncio
    async def test_many_deployments_performance(self):
        """Test handling many deployments efficiently."""
        manager = CanaryDeploymentManager(health_check_interval=0.1)
        
        import time
        start = time.time()
        
        # Create many deployments
        for i in range(50):
            await manager.start_deployment(
                f"deploy-{i:03d}",
                "v1.0",
                "v1.1"
            )
        
        duration = time.time() - start
        
        # Should create quickly
        assert duration < 1.0  # Less than 1 second
        assert len(manager.deployments) == 50
        
        await manager.stop_monitoring()
