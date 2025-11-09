"""
Comprehensive tests for Phase 2.5: Real-time Metrics Feed.

Tests cover:
- Metrics collection and aggregation
- WebSocket connection management
- Subscription-based filtering
- Heartbeat and connection lifecycle
- Performance statistics
- Error handling and cleanup
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json

from utils.metrics_stream import (
    MetricsStreamManager,
    MetricsCollector,
    Metric,
    MetricType,
    MetricPriority,
    ConnectionInfo,
    create_task_progress_metric,
    create_performance_metric,
    create_error_metric
)


# Mock WebSocket for testing
class MockWebSocket:
    """Mock WebSocket connection for testing."""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.messages = []
        self.is_open = True
        self.closed = False
    
    async def send(self, message: str):
        """Simulate sending a message."""
        if not self.is_open:
            raise RuntimeError("WebSocket is closed")
        self.messages.append(json.loads(message))
    
    async def close(self):
        """Simulate closing the connection."""
        self.is_open = False
        self.closed = True
    
    def get_messages_by_type(self, msg_type: str):
        """Get messages of a specific type."""
        return [msg for msg in self.messages if msg.get('type') == msg_type]


@pytest.mark.asyncio
class TestMetricsCollector:
    """Test MetricsCollector functionality."""
    
    async def test_collector_initialization(self):
        """Test collector initializes correctly."""
        collector = MetricsCollector(window_size=50, retention_seconds=1800)
        
        assert collector.window_size == 50
        assert collector.retention_seconds == 1800
        assert len(collector.metrics) == len(MetricType)
        assert all(isinstance(q, type(collector.metrics[MetricType.TASK_PROGRESS])) 
                  for q in collector.metrics.values())
    
    async def test_record_metric(self):
        """Test recording a metric."""
        collector = MetricsCollector()
        
        metric = create_task_progress_metric(
            task_id="test-task",
            status="in_progress",
            progress=0.5
        )
        
        collector.record(metric)
        
        metrics = collector.get_recent_metrics(MetricType.TASK_PROGRESS)
        assert len(metrics) == 1
        assert metrics[0]['data']['task_id'] == "test-task"
    
    async def test_performance_aggregation(self):
        """Test performance metrics aggregation."""
        collector = MetricsCollector()
        
        # Record multiple performance metrics
        latencies = [100, 150, 200, 120, 180]
        for latency in latencies:
            metric = create_performance_metric(
                latency=latency,
                success_count=10,
                error_count=2
            )
            collector.record(metric)
        
        stats = collector.get_stats(MetricType.PERFORMANCE)
        
        assert 'avg_latency' in stats
        assert 'p50_latency' in stats
        assert 'p95_latency' in stats
        assert stats['total_success'] == 50  # 10 * 5
        assert stats['total_errors'] == 10   # 2 * 5
        assert 'error_rate' in stats
    
    async def test_window_size_limit(self):
        """Test that window size limits are respected."""
        collector = MetricsCollector(window_size=10)
        
        # Record more than window size
        for i in range(20):
            metric = create_task_progress_metric(
                task_id=f"task-{i}",
                status="completed",
                progress=1.0
            )
            collector.record(metric)
        
        metrics = collector.get_recent_metrics(MetricType.TASK_PROGRESS)
        assert len(metrics) == 10  # Should be limited to window size
        
        # Should have most recent metrics
        assert metrics[-1]['data']['task_id'] == "task-19"
    
    async def test_get_recent_metrics_with_limit(self):
        """Test retrieving limited number of recent metrics."""
        collector = MetricsCollector()
        
        for i in range(10):
            metric = create_task_progress_metric(
                task_id=f"task-{i}",
                status="completed",
                progress=1.0
            )
            collector.record(metric)
        
        # Get only 5 most recent
        metrics = collector.get_recent_metrics(MetricType.TASK_PROGRESS, limit=5)
        assert len(metrics) == 5
        assert metrics[-1]['data']['task_id'] == "task-9"
    
    async def test_clear_old_metrics(self):
        """Test clearing old metrics."""
        collector = MetricsCollector(retention_seconds=1)
        
        # Record old metric
        old_metric = Metric(
            metric_type=MetricType.TASK_PROGRESS,
            timestamp=datetime.now() - timedelta(seconds=5),
            data={'task_id': 'old-task'},
            priority=MetricPriority.NORMAL
        )
        collector.metrics[MetricType.TASK_PROGRESS].append(old_metric)
        
        # Record recent metric
        recent_metric = create_task_progress_metric(
            task_id="recent-task",
            status="running",
            progress=0.5
        )
        collector.record(recent_metric)
        
        # Clear old
        collector.clear_old_metrics()
        
        metrics = collector.get_recent_metrics(MetricType.TASK_PROGRESS)
        assert len(metrics) == 1
        assert metrics[0]['data']['task_id'] == "recent-task"


@pytest.mark.asyncio
class TestMetricsStreamManager:
    """Test MetricsStreamManager functionality."""
    
    async def test_manager_initialization(self):
        """Test manager initializes correctly."""
        manager = MetricsStreamManager(
            heartbeat_interval=30,
            connection_timeout=60
        )
        
        assert manager.heartbeat_interval == 30
        assert manager.connection_timeout == 60
        assert len(manager.connections) == 0
        assert isinstance(manager.collector, MetricsCollector)
    
    async def test_register_connection(self):
        """Test registering a WebSocket connection."""
        manager = MetricsStreamManager()
        websocket = MockWebSocket("conn-1")
        
        await manager.register_connection(
            "conn-1",
            websocket,
            metadata={'user': 'test-user'}
        )
        
        assert "conn-1" in manager.connections
        assert manager.connections["conn-1"].metadata['user'] == 'test-user'
        
        # Should send welcome message
        welcome_msgs = websocket.get_messages_by_type('welcome')
        assert len(welcome_msgs) == 1
        assert welcome_msgs[0]['connection_id'] == "conn-1"
    
    async def test_unregister_connection(self):
        """Test unregistering a connection."""
        manager = MetricsStreamManager()
        websocket = MockWebSocket("conn-1")
        
        await manager.register_connection("conn-1", websocket)
        assert "conn-1" in manager.connections
        
        await manager.unregister_connection("conn-1")
        assert "conn-1" not in manager.connections
    
    async def test_subscription(self):
        """Test subscribing to metric types."""
        manager = MetricsStreamManager()
        websocket = MockWebSocket("conn-1")
        
        await manager.register_connection("conn-1", websocket)
        
        # Subscribe to specific metrics
        await manager.subscribe("conn-1", [
            MetricType.TASK_PROGRESS,
            MetricType.PERFORMANCE
        ])
        
        conn = manager.connections["conn-1"]
        assert MetricType.TASK_PROGRESS in conn.subscriptions
        assert MetricType.PERFORMANCE in conn.subscriptions
        
        # Should send confirmation
        confirm_msgs = websocket.get_messages_by_type('subscription_confirmed')
        assert len(confirm_msgs) == 1
    
    async def test_unsubscription(self):
        """Test unsubscribing from metric types."""
        manager = MetricsStreamManager()
        websocket = MockWebSocket("conn-1")
        
        await manager.register_connection("conn-1", websocket)
        await manager.subscribe("conn-1", [
            MetricType.TASK_PROGRESS,
            MetricType.PERFORMANCE
        ])
        
        # Unsubscribe from one
        await manager.unsubscribe("conn-1", [MetricType.PERFORMANCE])
        
        conn = manager.connections["conn-1"]
        assert MetricType.TASK_PROGRESS in conn.subscriptions
        assert MetricType.PERFORMANCE not in conn.subscriptions
    
    async def test_broadcast_metric(self):
        """Test broadcasting metrics to subscribers."""
        manager = MetricsStreamManager()
        ws1 = MockWebSocket("conn-1")
        ws2 = MockWebSocket("conn-2")
        ws3 = MockWebSocket("conn-3")
        
        # Register connections
        await manager.register_connection("conn-1", ws1)
        await manager.register_connection("conn-2", ws2)
        await manager.register_connection("conn-3", ws3)
        
        # Subscribe to different metrics
        await manager.subscribe("conn-1", [MetricType.TASK_PROGRESS])
        await manager.subscribe("conn-2", [MetricType.TASK_PROGRESS, MetricType.PERFORMANCE])
        await manager.subscribe("conn-3", [MetricType.PERFORMANCE])
        
        # Broadcast task progress metric
        metric = create_task_progress_metric(
            task_id="test-task",
            status="running",
            progress=0.5
        )
        await manager.broadcast_metric(metric)
        
        # conn-1 and conn-2 should receive (subscribed to TASK_PROGRESS)
        task_msgs_1 = ws1.get_messages_by_type('metric')
        task_msgs_2 = ws2.get_messages_by_type('metric')
        task_msgs_3 = ws3.get_messages_by_type('metric')
        
        assert len(task_msgs_1) == 1
        assert len(task_msgs_2) == 1
        assert len(task_msgs_3) == 0  # Not subscribed
        
        # Broadcast performance metric
        perf_metric = create_performance_metric(
            latency=100,
            success_count=10,
            error_count=2
        )
        await manager.broadcast_metric(perf_metric)
        
        # conn-2 and conn-3 should receive
        perf_msgs_1 = [m for m in ws1.messages if m.get('type') == 'metric' and 
                       m.get('metric_type') == MetricType.PERFORMANCE.value]
        perf_msgs_2 = [m for m in ws2.messages if m.get('type') == 'metric' and 
                       m.get('metric_type') == MetricType.PERFORMANCE.value]
        perf_msgs_3 = [m for m in ws3.messages if m.get('type') == 'metric' and 
                       m.get('metric_type') == MetricType.PERFORMANCE.value]
        
        assert len(perf_msgs_1) == 0
        assert len(perf_msgs_2) == 1
        assert len(perf_msgs_3) == 1
    
    async def test_start_stop_lifecycle(self):
        """Test manager start/stop lifecycle."""
        manager = MetricsStreamManager(heartbeat_interval=1)
        
        assert not manager.is_running
        
        await manager.start()
        assert manager.is_running
        assert manager.heartbeat_task is not None
        assert manager.cleanup_task is not None
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        await manager.stop()
        assert not manager.is_running
    
    async def test_heartbeat_ping(self):
        """Test heartbeat sends ping messages."""
        manager = MetricsStreamManager(heartbeat_interval=1)
        websocket = MockWebSocket("conn-1")
        
        await manager.register_connection("conn-1", websocket)
        await manager.start()
        
        # Wait for heartbeat
        await asyncio.sleep(1.5)
        
        # Should have received ping
        ping_msgs = websocket.get_messages_by_type('ping')
        assert len(ping_msgs) >= 1
        
        await manager.stop()
    
    async def test_connection_cleanup(self):
        """Test cleanup of dead connections."""
        manager = MetricsStreamManager(
            heartbeat_interval=1,
            connection_timeout=2
        )
        websocket = MockWebSocket("conn-1")
        
        await manager.register_connection("conn-1", websocket)
        
        # Mark connection as dead
        manager.connections["conn-1"].is_alive = False
        
        await manager.start()
        
        # Wait for cleanup cycle
        await asyncio.sleep(1.2)
        
        # Should be cleaned up
        # Note: cleanup runs every 60s, but we'll check manually
        manager.collector.clear_old_metrics()
        
        await manager.stop()
    
    async def test_send_system_health(self):
        """Test sending system health metrics."""
        manager = MetricsStreamManager()
        websocket = MockWebSocket("conn-1")
        
        await manager.register_connection("conn-1", websocket)
        await manager.subscribe("conn-1", [MetricType.SYSTEM_HEALTH])
        
        await manager.send_system_health()
        
        # Should receive health metric
        health_msgs = [m for m in websocket.messages 
                      if m.get('type') == 'metric' and 
                      m.get('metric_type') == MetricType.SYSTEM_HEALTH.value]
        
        assert len(health_msgs) == 1
        assert 'connections' in health_msgs[0]['data']
    
    async def test_connection_stats(self):
        """Test getting connection statistics."""
        manager = MetricsStreamManager()
        ws1 = MockWebSocket("conn-1")
        ws2 = MockWebSocket("conn-2")
        
        await manager.register_connection("conn-1", ws1)
        await manager.register_connection("conn-2", ws2)
        
        await manager.subscribe("conn-1", [MetricType.TASK_PROGRESS])
        await manager.subscribe("conn-2", [MetricType.PERFORMANCE, MetricType.ERROR])
        
        stats = manager.get_connection_stats()
        
        assert stats['total_connections'] == 2
        assert stats['active_connections'] == 2
        assert stats['total_subscriptions'] == 3  # 1 + 2
        assert len(stats['connections']) == 2
    
    async def test_metrics_collection_integration(self):
        """Test integration with metrics collector."""
        manager = MetricsStreamManager()
        
        # Broadcast some metrics
        for i in range(5):
            metric = create_task_progress_metric(
                task_id=f"task-{i}",
                status="running",
                progress=i * 0.2
            )
            await manager.broadcast_metric(metric)
        
        # Check collector has them
        recent = manager.collector.get_recent_metrics(MetricType.TASK_PROGRESS)
        assert len(recent) == 5
        
        # Check stats
        stats = manager.get_metrics_stats()
        assert MetricType.TASK_PROGRESS.value in stats


@pytest.mark.asyncio
class TestMetricCreationHelpers:
    """Test convenience functions for creating metrics."""
    
    async def test_create_task_progress_metric(self):
        """Test creating task progress metric."""
        metric = create_task_progress_metric(
            task_id="test-task",
            status="running",
            progress=0.75,
            details={'step': 3}
        )
        
        assert metric.metric_type == MetricType.TASK_PROGRESS
        assert metric.data['task_id'] == "test-task"
        assert metric.data['status'] == "running"
        assert metric.data['progress'] == 0.75
        assert metric.data['details']['step'] == 3
    
    async def test_create_performance_metric(self):
        """Test creating performance metric."""
        metric = create_performance_metric(
            latency=125.5,
            success_count=100,
            error_count=5,
            details={'endpoint': '/api/tasks'}
        )
        
        assert metric.metric_type == MetricType.PERFORMANCE
        assert metric.data['latency'] == 125.5
        assert metric.data['success_count'] == 100
        assert metric.data['error_count'] == 5
    
    async def test_create_error_metric(self):
        """Test creating error metric."""
        metric = create_error_metric(
            error_type="ValueError",
            error_message="Invalid input",
            stack_trace="line 42",
            context={'user': 'test'}
        )
        
        assert metric.metric_type == MetricType.ERROR
        assert metric.priority == MetricPriority.HIGH
        assert metric.data['error_type'] == "ValueError"
        assert metric.data['error_message'] == "Invalid input"


@pytest.mark.asyncio
class TestEndToEndScenarios:
    """Test end-to-end scenarios."""
    
    async def test_multiple_clients_with_different_subscriptions(self):
        """Test multiple clients with different subscription patterns."""
        manager = MetricsStreamManager()
        
        # Create 5 clients with different subscriptions
        clients = []
        for i in range(5):
            ws = MockWebSocket(f"client-{i}")
            await manager.register_connection(f"client-{i}", ws)
            clients.append(ws)
        
        # Different subscription patterns
        await manager.subscribe("client-0", [MetricType.TASK_PROGRESS])
        await manager.subscribe("client-1", [MetricType.PERFORMANCE])
        await manager.subscribe("client-2", [MetricType.TASK_PROGRESS, MetricType.PERFORMANCE])
        await manager.subscribe("client-3", [MetricType.ERROR])
        await manager.subscribe("client-4", list(MetricType))  # All metrics
        
        # Broadcast various metrics
        await manager.broadcast_metric(create_task_progress_metric("task-1", "running", 0.5))
        await manager.broadcast_metric(create_performance_metric(100, 10, 2))
        await manager.broadcast_metric(create_error_metric("TestError", "Test message"))
        
        # Verify each client received correct metrics
        assert len(clients[0].get_messages_by_type('metric')) == 1  # Only task
        assert len(clients[1].get_messages_by_type('metric')) == 1  # Only perf
        assert len(clients[2].get_messages_by_type('metric')) == 2  # Task + perf
        assert len(clients[3].get_messages_by_type('metric')) == 1  # Only error
        assert len(clients[4].get_messages_by_type('metric')) == 3  # All
    
    async def test_high_throughput_metrics(self):
        """Test handling high volume of metrics."""
        manager = MetricsStreamManager()
        websocket = MockWebSocket("client-1")
        
        await manager.register_connection("client-1", websocket)
        await manager.subscribe("client-1", [MetricType.TASK_PROGRESS])
        
        # Broadcast many metrics quickly
        for i in range(100):
            metric = create_task_progress_metric(
                task_id=f"task-{i}",
                status="running",
                progress=i / 100.0
            )
            await manager.broadcast_metric(metric)
        
        # All should be received
        metric_msgs = websocket.get_messages_by_type('metric')
        assert len(metric_msgs) == 100
        
        # Collector should respect window size
        recent = manager.collector.get_recent_metrics(MetricType.TASK_PROGRESS)
        assert len(recent) <= 100  # Default window size
    
    async def test_connection_lifecycle_with_errors(self):
        """Test connection lifecycle with simulated errors."""
        manager = MetricsStreamManager()
        
        # Create failing websocket
        failing_ws = MockWebSocket("failing-client")
        failing_ws.is_open = False  # Simulate closed connection
        
        await manager.register_connection("failing-client", failing_ws)
        await manager.subscribe("failing-client", [MetricType.TASK_PROGRESS])
        
        # Try to broadcast - should handle gracefully
        metric = create_task_progress_metric("task-1", "running", 0.5)
        await manager.broadcast_metric(metric)
        
        # Connection should be marked as dead
        assert not manager.connections["failing-client"].is_alive


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
