"""
Real-time Metrics Feed with WebSocket Streaming.

This module implements a production-grade metrics streaming system with:
- WebSocket server for real-time metrics broadcasting
- Connection management with heartbeat/ping-pong
- Metrics collection and aggregation pipeline
- Live task progress tracking
- System health monitoring
- Performance dashboards support
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Set, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import statistics
from collections import deque

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""
    TASK_PROGRESS = "task_progress"
    SYSTEM_HEALTH = "system_health"
    PERFORMANCE = "performance"
    QUEUE_STATUS = "queue_status"
    WORKER_STATUS = "worker_status"
    ERROR = "error"
    DEPLOYMENT = "deployment"


class MetricPriority(Enum):
    """Metric priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Metric:
    """Represents a single metric data point."""
    metric_type: MetricType
    timestamp: datetime
    data: Dict[str, Any]
    priority: MetricPriority = MetricPriority.NORMAL
    source: str = "system"
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'metric_type': self.metric_type.value,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'priority': self.priority.value,
            'source': self.source,
            'tags': self.tags
        }


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    connection_id: str
    connected_at: datetime
    last_ping: Optional[datetime] = None
    last_pong: Optional[datetime] = None
    subscriptions: Set[MetricType] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_alive: bool = True


class MetricsCollector:
    """
    Collects and aggregates metrics from various sources.
    
    Features:
    - Multiple metric sources
    - Automatic aggregation
    - Time-windowed statistics
    - Memory-efficient storage
    """
    
    def __init__(
        self,
        window_size: int = 100,
        retention_seconds: int = 3600
    ):
        """
        Initialize metrics collector.
        
        Args:
            window_size: Number of recent metrics to keep per type
            retention_seconds: How long to retain metrics
        """
        self.window_size = window_size
        self.retention_seconds = retention_seconds
        
        # Storage for recent metrics (using deque for efficient operations)
        self.metrics: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=window_size)
            for metric_type in MetricType
        }
        
        # Aggregated statistics
        self.stats: Dict[MetricType, Dict[str, Any]] = {}
        
        logger.info(
            f"📊 MetricsCollector: Initialized "
            f"(window: {window_size}, retention: {retention_seconds}s)"
        )
    
    def record(self, metric: Metric):
        """
        Record a new metric.
        
        Args:
            metric: Metric to record
        """
        # Add to appropriate queue
        self.metrics[metric.metric_type].append(metric)
        
        # Update statistics
        self._update_stats(metric.metric_type)
        
        logger.debug(
            f"📈 Recorded {metric.metric_type.value} metric "
            f"(priority: {metric.priority.name})"
        )
    
    def _update_stats(self, metric_type: MetricType):
        """Update aggregated statistics for a metric type."""
        metrics = list(self.metrics[metric_type])
        
        if not metrics:
            return
        
        # Calculate basic stats
        self.stats[metric_type] = {
            'count': len(metrics),
            'latest': metrics[-1].to_dict(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Type-specific aggregations
        if metric_type == MetricType.PERFORMANCE:
            self._aggregate_performance_stats(metrics)
        elif metric_type == MetricType.QUEUE_STATUS:
            self._aggregate_queue_stats(metrics)
    
    def _aggregate_performance_stats(self, metrics: List[Metric]):
        """Aggregate performance metrics."""
        latencies = []
        success_counts = []
        error_counts = []
        
        for metric in metrics:
            if 'latency' in metric.data:
                latencies.append(metric.data['latency'])
            if 'success_count' in metric.data:
                success_counts.append(metric.data['success_count'])
            if 'error_count' in metric.data:
                error_counts.append(metric.data['error_count'])
        
        perf_stats = {}
        
        if latencies:
            perf_stats['avg_latency'] = statistics.mean(latencies)
            perf_stats['p50_latency'] = statistics.median(latencies)
            perf_stats['p95_latency'] = sorted(latencies)[int(len(latencies) * 0.95)]
        
        if success_counts:
            perf_stats['total_success'] = sum(success_counts)
        
        if error_counts:
            perf_stats['total_errors'] = sum(error_counts)
            total_requests = sum(success_counts) + sum(error_counts)
            if total_requests > 0:
                perf_stats['error_rate'] = sum(error_counts) / total_requests
        
        self.stats[MetricType.PERFORMANCE].update(perf_stats)
    
    def _aggregate_queue_stats(self, metrics: List[Metric]):
        """Aggregate queue status metrics."""
        latest = metrics[-1].data
        
        queue_stats = {
            'current_depth': latest.get('depth', 0),
            'avg_depth': statistics.mean([m.data.get('depth', 0) for m in metrics]),
            'peak_depth': max([m.data.get('depth', 0) for m in metrics]),
        }
        
        self.stats[MetricType.QUEUE_STATUS].update(queue_stats)
    
    def get_recent_metrics(
        self,
        metric_type: MetricType,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent metrics of a specific type.
        
        Args:
            metric_type: Type of metrics to retrieve
            limit: Maximum number of metrics to return
            
        Returns:
            List of metric dictionaries
        """
        metrics = list(self.metrics[metric_type])
        
        if limit:
            metrics = metrics[-limit:]
        
        return [m.to_dict() for m in metrics]
    
    def get_stats(self, metric_type: Optional[MetricType] = None) -> Dict[str, Any]:
        """
        Get aggregated statistics.
        
        Args:
            metric_type: Specific type or None for all
            
        Returns:
            Statistics dictionary
        """
        if metric_type:
            return self.stats.get(metric_type, {})
        
        return {
            mt.value: self.stats.get(mt, {})
            for mt in MetricType
        }
    
    def clear_old_metrics(self):
        """Clear metrics older than retention period."""
        cutoff = datetime.now() - timedelta(seconds=self.retention_seconds)
        
        for metric_type in MetricType:
            queue = self.metrics[metric_type]
            # Remove old metrics from front of deque
            while queue and queue[0].timestamp < cutoff:
                queue.popleft()
        
        logger.debug("🧹 Cleared old metrics")


class MetricsStreamManager:
    """
    Manages real-time metrics streaming to WebSocket clients.
    
    Features:
    - Connection lifecycle management
    - Subscription-based filtering
    - Automatic heartbeat/ping-pong
    - Broadcast to multiple clients
    - Graceful connection handling
    """
    
    def __init__(
        self,
        heartbeat_interval: int = 30,
        connection_timeout: int = 60
    ):
        """
        Initialize metrics stream manager.
        
        Args:
            heartbeat_interval: Seconds between heartbeat pings
            connection_timeout: Seconds before considering connection dead
        """
        self.heartbeat_interval = heartbeat_interval
        self.connection_timeout = connection_timeout
        
        # Active connections
        self.connections: Dict[str, ConnectionInfo] = {}
        
        # WebSocket connections (actual WebSocket objects)
        self.websockets: Dict[str, Any] = {}
        
        # Metrics collector
        self.collector = MetricsCollector()
        
        # Background tasks
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        logger.info(
            f"🌐 MetricsStreamManager: Initialized "
            f"(heartbeat: {heartbeat_interval}s, timeout: {connection_timeout}s)"
        )
    
    async def start(self):
        """Start background tasks."""
        if self.is_running:
            logger.warning("Metrics stream manager already running")
            return
        
        self.is_running = True
        
        # Start heartbeat
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # Start cleanup
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("▶️ Metrics stream manager started")
    
    async def stop(self):
        """Stop background tasks and close connections."""
        self.is_running = False
        
        # Cancel tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        await self.close_all_connections()
        
        logger.info("⏹️ Metrics stream manager stopped")
    
    async def register_connection(
        self,
        connection_id: str,
        websocket: Any,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register a new WebSocket connection.
        
        Args:
            connection_id: Unique connection identifier
            websocket: WebSocket connection object
            metadata: Optional connection metadata
        """
        connection = ConnectionInfo(
            connection_id=connection_id,
            connected_at=datetime.now(),
            metadata=metadata or {}
        )
        
        self.connections[connection_id] = connection
        self.websockets[connection_id] = websocket
        
        logger.info(f"🔌 Connection registered: {connection_id}")
        
        # Send welcome message
        await self._send_to_connection(connection_id, {
            'type': 'welcome',
            'connection_id': connection_id,
            'timestamp': datetime.now().isoformat(),
            'available_metrics': [mt.value for mt in MetricType]
        })
    
    async def unregister_connection(self, connection_id: str):
        """
        Unregister a WebSocket connection.
        
        Args:
            connection_id: Connection to unregister
        """
        if connection_id in self.connections:
            del self.connections[connection_id]
        
        if connection_id in self.websockets:
            del self.websockets[connection_id]
        
        logger.info(f"🔌 Connection unregistered: {connection_id}")
    
    async def subscribe(
        self,
        connection_id: str,
        metric_types: List[MetricType]
    ):
        """
        Subscribe connection to specific metric types.
        
        Args:
            connection_id: Connection to subscribe
            metric_types: List of metric types to subscribe to
        """
        if connection_id not in self.connections:
            logger.warning(f"Cannot subscribe unknown connection: {connection_id}")
            return
        
        connection = self.connections[connection_id]
        connection.subscriptions.update(metric_types)
        
        logger.info(
            f"📡 {connection_id} subscribed to: "
            f"{[mt.value for mt in metric_types]}"
        )
        
        # Send confirmation
        await self._send_to_connection(connection_id, {
            'type': 'subscription_confirmed',
            'subscriptions': [mt.value for mt in connection.subscriptions]
        })
    
    async def unsubscribe(
        self,
        connection_id: str,
        metric_types: List[MetricType]
    ):
        """Unsubscribe from metric types."""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        connection.subscriptions.difference_update(metric_types)
        
        logger.info(
            f"📡 {connection_id} unsubscribed from: "
            f"{[mt.value for mt in metric_types]}"
        )
    
    async def broadcast_metric(self, metric: Metric):
        """
        Broadcast metric to all subscribed connections.
        
        Args:
            metric: Metric to broadcast
        """
        # Record in collector
        self.collector.record(metric)
        
        # Find subscribed connections
        subscribed = [
            conn_id for conn_id, conn in self.connections.items()
            if metric.metric_type in conn.subscriptions
        ]
        
        if not subscribed:
            return
        
        # Prepare message
        message = {
            'type': 'metric',
            **metric.to_dict()
        }
        
        # Broadcast to all subscribed
        await asyncio.gather(*[
            self._send_to_connection(conn_id, message)
            for conn_id in subscribed
        ], return_exceptions=True)
        
        logger.debug(
            f"📢 Broadcasted {metric.metric_type.value} to {len(subscribed)} connections"
        )
    
    async def send_system_health(self):
        """Send current system health to all subscribed connections."""
        health_metric = Metric(
            metric_type=MetricType.SYSTEM_HEALTH,
            timestamp=datetime.now(),
            data={
                'connections': len(self.connections),
                'active_subscriptions': sum(
                    len(c.subscriptions) for c in self.connections.values()
                ),
                'metrics_collected': sum(
                    len(self.collector.metrics[mt]) for mt in MetricType
                )
            },
            priority=MetricPriority.NORMAL,
            source="metrics_manager"
        )
        
        await self.broadcast_metric(health_metric)
    
    async def _send_to_connection(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection."""
        if connection_id not in self.websockets:
            return
        
        websocket = self.websockets[connection_id]
        
        try:
            # Convert to JSON and send
            await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send to {connection_id}: {e}")
            # Mark connection as dead
            if connection_id in self.connections:
                self.connections[connection_id].is_alive = False
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat pings to all connections."""
        try:
            while self.is_running:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Send ping to all connections
                for conn_id in list(self.connections.keys()):
                    if conn_id in self.connections:
                        self.connections[conn_id].last_ping = datetime.now()
                        await self._send_to_connection(conn_id, {
                            'type': 'ping',
                            'timestamp': datetime.now().isoformat()
                        })
                
                logger.debug(f"💓 Heartbeat sent to {len(self.connections)} connections")
                
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}", exc_info=True)
    
    async def _cleanup_loop(self):
        """Clean up dead connections and old metrics."""
        try:
            while self.is_running:
                await asyncio.sleep(60)  # Cleanup every minute
                
                # Find dead connections
                timeout = datetime.now() - timedelta(seconds=self.connection_timeout)
                dead_connections = [
                    conn_id for conn_id, conn in self.connections.items()
                    if not conn.is_alive or 
                    (conn.last_ping and conn.last_ping < timeout and
                     (not conn.last_pong or conn.last_pong < timeout))
                ]
                
                # Remove dead connections
                for conn_id in dead_connections:
                    await self.unregister_connection(conn_id)
                    logger.info(f"🧹 Cleaned up dead connection: {conn_id}")
                
                # Clean old metrics
                self.collector.clear_old_metrics()
                
        except asyncio.CancelledError:
            logger.info("Cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}", exc_info=True)
    
    async def close_all_connections(self):
        """Close all active connections."""
        for conn_id in list(self.connections.keys()):
            await self.unregister_connection(conn_id)
        
        logger.info(f"🔌 Closed all connections")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about connections."""
        return {
            'total_connections': len(self.connections),
            'active_connections': sum(
                1 for c in self.connections.values() if c.is_alive
            ),
            'total_subscriptions': sum(
                len(c.subscriptions) for c in self.connections.values()
            ),
            'connections': [
                {
                    'connection_id': conn.connection_id,
                    'connected_at': conn.connected_at.isoformat(),
                    'subscriptions': [mt.value for mt in conn.subscriptions],
                    'is_alive': conn.is_alive
                }
                for conn in self.connections.values()
            ]
        }
    
    def get_metrics_stats(self) -> Dict[str, Any]:
        """Get statistics about collected metrics."""
        return self.collector.get_stats()
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MetricsStreamManager("
            f"connections={len(self.connections)}, "
            f"running={self.is_running})"
        )


# Convenience functions for creating common metrics

def create_task_progress_metric(
    task_id: str,
    status: str,
    progress: float,
    details: Optional[Dict[str, Any]] = None
) -> Metric:
    """Create a task progress metric."""
    return Metric(
        metric_type=MetricType.TASK_PROGRESS,
        timestamp=datetime.now(),
        data={
            'task_id': task_id,
            'status': status,
            'progress': progress,
            'details': details or {}
        },
        priority=MetricPriority.NORMAL,
        source="task_manager"
    )


def create_performance_metric(
    latency: float,
    success_count: int,
    error_count: int,
    details: Optional[Dict[str, Any]] = None
) -> Metric:
    """Create a performance metric."""
    return Metric(
        metric_type=MetricType.PERFORMANCE,
        timestamp=datetime.now(),
        data={
            'latency': latency,
            'success_count': success_count,
            'error_count': error_count,
            'details': details or {}
        },
        priority=MetricPriority.NORMAL,
        source="performance_monitor"
    )


def create_error_metric(
    error_type: str,
    error_message: str,
    stack_trace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Metric:
    """Create an error metric."""
    return Metric(
        metric_type=MetricType.ERROR,
        timestamp=datetime.now(),
        data={
            'error_type': error_type,
            'error_message': error_message,
            'stack_trace': stack_trace,
            'context': context or {}
        },
        priority=MetricPriority.HIGH,
        source="error_handler"
    )
