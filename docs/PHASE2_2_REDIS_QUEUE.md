# Phase 2.2: Redis-Based Distributed Queue

## Overview

Phase 2.2 introduces a production-grade distributed task queue using Redis as the backend. This enables:

- **Distributed Processing**: Multiple workers can process tasks concurrently
- **Priority-Based Execution**: Tasks are processed by priority (CRITICAL > HIGH > NORMAL > LOW)
- **Persistent State**: Task state survives application restarts
- **Automatic Retry**: Failed tasks are automatically retried with exponential backoff
- **Dead Letter Queue**: Failed tasks after max retries are moved to DLQ for manual review
- **Worker Coordination**: Multiple workers coordinate through Redis without conflicts

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Redis Task Queue                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ PENDING  │  │PROCESSING│  │COMPLETED │  │   DLQ    │  │
│  │ (sorted) │  │  (set)   │  │  (set)   │  │  (set)   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│       ▲             │              │              │         │
│       │             │              │              │         │
│       │    ┌────────┴────────┬─────┴────────┬─────┘        │
│       │    │                 │              │               │
└───────┼────┼─────────────────┼──────────────┼──────────────┘
        │    │                 │              │
        │    ▼                 ▼              ▼
   ┌────┴────────┐      ┌──────────┐   ┌──────────┐
   │   Worker 1  │      │ Worker 2 │   │ Worker 3 │
   │             │      │          │   │          │
   │ Dev Tasks   │      │ QA Tasks │   │Fix Tasks │
   └─────────────┘      └──────────┘   └──────────┘
```

## Key Components

### 1. RedisTask

Represents a task in the queue with full lifecycle tracking:

```python
@dataclass
class RedisTask:
    task_id: str                    # Unique identifier
    task_type: str                  # dev, qa, fix, deploy
    payload: Dict[str, Any]         # Task data
    priority: int                   # 0-3 (LOW to CRITICAL)
    state: str                      # pending, processing, completed, failed, dead_letter
    retry_count: int                # Current retry attempt
    max_retries: int                # Maximum retry attempts
    created_at: str                 # ISO timestamp
    started_at: Optional[str]       # When worker started processing
    completed_at: Optional[str]     # When task completed
    worker_id: Optional[str]        # Worker processing the task
    error: Optional[str]            # Error message if failed
```

### 2. RedisTaskQueue

Main queue implementation with full task lifecycle management:

```python
queue = RedisTaskQueue(
    queue_name="agentic_ai",
    redis_url="redis://localhost:6379",
    max_retries=3,
    task_ttl_seconds=3600,
    enable_dlq=True
)

await queue.connect()
```

## Usage Guide

### Basic Operations

#### 1. Enqueue Tasks

```python
# Enqueue with priority
task = await queue.enqueue(
    task_id="dev_main_py",
    task_type="dev",
    payload={
        "file": "main.py",
        "requirements": "Create Flask app"
    },
    priority=TaskPriority.HIGH.value
)
```

#### 2. Worker Processing

```python
async def worker(worker_id):
    while True:
        # Blocking dequeue with timeout
        task = await queue.dequeue(worker_id, timeout=5.0)
        
        if not task:
            continue
        
        try:
            # Process task
            result = await process_task(task)
            await queue.complete_task(task.task_id, result)
        except Exception as e:
            # Fail with retry
            await queue.fail_task(task.task_id, str(e), retry=True)
```

#### 3. Monitor Queue

```python
# Get queue sizes
sizes = await queue.get_queue_size()
print(f"Pending: {sizes['pending']}")
print(f"Processing: {sizes['processing']}")
print(f"DLQ: {sizes['dlq']}")

# Get statistics
stats = await queue.get_statistics()
print(f"Success Rate: {stats['success_rate']}%")
```

### Priority Levels

Tasks are processed in priority order:

```python
class TaskPriority(int, Enum):
    LOW = 0         # Background tasks
    NORMAL = 1      # Regular tasks
    HIGH = 2        # Critical path tasks
    CRITICAL = 3    # System critical tasks
```

### Retry Logic

Failed tasks are automatically retried with exponential backoff:

- **Attempt 1**: Immediate retry
- **Attempt 2**: 2 second delay
- **Attempt 3**: 4 second delay
- **After max retries**: Move to Dead Letter Queue

```python
# Fail with retry
await queue.fail_task(task_id, error="Temporary failure", retry=True)

# Fail permanently (no retry)
await queue.fail_task(task_id, error="Invalid task", retry=False)
```

### Dead Letter Queue

Tasks that exceed max retries are moved to DLQ for manual review:

```python
# List DLQ tasks
dlq_tasks = await queue.list_tasks(state=TaskState.DEAD_LETTER)

for task in dlq_tasks:
    print(f"Failed: {task.task_id}, Error: {task.error}")
    
    # Fix and retry manually
    if should_retry(task):
        await queue.retry_dlq_task(task.task_id)
```

## Integration with Pipeline

### EnhancedPipelineManager + Redis

The Redis queue can be integrated with the enhanced pipeline:

```python
from utils.enhanced_pipeline_manager import EnhancedPipelineManager
from utils.redis_queue import RedisTaskQueue

class DistributedPipelineManager(EnhancedPipelineManager):
    """Pipeline with Redis-backed distributed queue."""
    
    def __init__(self, redis_url="redis://localhost:6379", **kwargs):
        super().__init__(**kwargs)
        self.redis_queue = RedisTaskQueue(redis_url=redis_url)
    
    async def start(self):
        """Start pipeline with Redis queue."""
        await self.redis_queue.connect()
        await super().start()
    
    async def submit_dev_task(self, task_id, subtask, **kwargs):
        """Submit via Redis instead of local queue."""
        await self.redis_queue.enqueue(
            task_id=task_id,
            task_type="dev",
            payload={
                "subtask": subtask,
                **kwargs
            },
            priority=self.priority_assigner.assign_priority(subtask)
        )
```

## Performance Characteristics

Based on test results:

- **Enqueue Rate**: ~1000+ tasks/second
- **Dequeue Rate**: ~500+ tasks/second per worker
- **Priority Ordering**: Consistent O(log N) performance
- **Task Lookup**: O(1) with Redis hash lookup
- **Memory**: ~1KB per task (average)

## Redis Configuration

### Development

```bash
# Install Redis
brew install redis  # macOS
apt-get install redis-server  # Ubuntu

# Start Redis
redis-server

# Test connection
redis-cli ping
```

### Production

```yaml
# docker-compose.yml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 2gb

volumes:
  redis_data:
```

### Redis Configuration Options

```python
queue = RedisTaskQueue(
    queue_name="production",           # Queue namespace
    redis_url="redis://localhost:6379",  # Redis connection
    max_retries=5,                     # Increase for production
    task_ttl_seconds=86400,            # 24 hour TTL
    enable_dlq=True                    # Always enable in production
)
```

## Monitoring & Operations

### Health Checks

```python
async def health_check():
    """Check queue health."""
    try:
        await queue.redis.ping()
        stats = await queue.get_statistics()
        
        return {
            "status": "healthy",
            "pending": stats['pending'],
            "processing": stats['processing'],
            "dlq_size": stats['dlq'],
            "success_rate": stats['success_rate']
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### Metrics to Monitor

1. **Queue Depth**: Pending task count
2. **Processing Time**: Time from enqueue to complete
3. **Error Rate**: Failed tasks / total tasks
4. **DLQ Growth**: Rate of DLQ additions
5. **Worker Utilization**: Processing vs idle time

### Cleanup Operations

```python
# Clear old completed tasks (daily)
await queue.clear_completed(older_than_seconds=86400)

# Monitor DLQ size
dlq_size = await queue.redis.scard(queue.dlq_key)
if dlq_size > 100:
    alert("DLQ threshold exceeded")
```

## Testing

### Running Tests

```bash
# Install Redis
pip install redis

# Start Redis server
redis-server

# Run tests
pytest tests/test_phase2_redis_queue.py -v
```

### Test Coverage

- ✅ Basic enqueue/dequeue operations
- ✅ Priority-based processing
- ✅ Retry logic and exponential backoff
- ✅ Dead letter queue
- ✅ Concurrent worker coordination
- ✅ Performance benchmarks
- ✅ Integration scenarios

## Best Practices

### 1. Task Design

- Keep payloads small (< 1MB)
- Use task_id as idempotency key
- Include retry hints in payload
- Set appropriate TTL for task type

### 2. Worker Design

- Use dedicated workers per task type
- Implement graceful shutdown
- Handle worker crashes (heartbeats)
- Monitor worker health

### 3. Error Handling

- Log all errors with context
- Use DLQ for manual investigation
- Implement alerts for DLQ growth
- Review DLQ tasks regularly

### 4. Scaling

- Scale workers horizontally
- Use Redis Cluster for > 10k tasks/sec
- Monitor Redis memory usage
- Implement rate limiting if needed

## Troubleshooting

### Queue Growing Too Fast

```python
# Check worker capacity
stats = await queue.get_statistics()
if stats['pending'] > 1000:
    # Scale up workers or increase worker pool
    pass
```

### Tasks Stuck in Processing

```python
# Implement worker heartbeat
# Mark stale tasks as failed after timeout
async def check_stale_tasks(timeout_seconds=300):
    processing = await queue.list_tasks(state=TaskState.PROCESSING)
    for task in processing:
        if task.started_at:
            started = datetime.fromisoformat(task.started_at)
            if datetime.now() - started > timedelta(seconds=timeout_seconds):
                await queue.fail_task(task.task_id, "Worker timeout", retry=True)
```

### Redis Connection Issues

```python
# Implement connection retry
async def connect_with_retry(max_attempts=5):
    for attempt in range(max_attempts):
        try:
            await queue.connect()
            return
        except Exception as e:
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise
```

## Next Steps

Phase 2.2 Complete! ✅

Next: **Phase 2.3** - Integration Test Suite

- End-to-end workflow tests
- Multi-agent collaboration
- Performance benchmarks
- Failure recovery scenarios
