"""
Enhanced components for production-grade pipeline.

This module provides:
- ResultCache: Cache dev results to avoid regenerating identical code
- PriorityAssigner: Assign priority based on critical path analysis
- Event system: Event-driven architecture support
"""

import json
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# Event System
# ============================================================================

class EventType(Enum):
    """Event types for pipeline routing."""
    FILE_COMPLETED = "file_completed"
    FILE_FAILED = "file_failed"
    QA_PASSED = "qa_passed"
    QA_FAILED = "qa_failed"
    FIX_COMPLETED = "fix_completed"
    DEPLOY_READY = "deploy_ready"
    ESCALATE_TO_PM = "escalate_to_pm"
    CIRCUIT_OPEN = "circuit_open"
    CIRCUIT_CLOSED = "circuit_closed"


class TaskPriority(Enum):
    """Task priority levels based on critical path."""
    CRITICAL = 1  # Blocks everything (main.py, core models, config)
    HIGH = 2      # Dependencies (schemas, database, auth)
    NORMAL = 3    # Regular features (services, APIs, routes)
    LOW = 4       # Nice-to-have (docs, tests, examples)
    RETRY = 5     # Retries have lower priority


@dataclass
class Event:
    """Event for pipeline routing."""
    event_type: EventType
    task_id: str
    payload: Dict[str, Any]
    timestamp: datetime
    retry_count: int = 0
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Event':
        """Deserialize from JSON."""
        data = json.loads(json_str)
        data['event_type'] = EventType(data['event_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


# ============================================================================
# Result Cache
# ============================================================================

class ResultCache:
    """
    Cache for dev results to avoid regenerating identical code.
    
    Uses content-based hashing (SHA-256) to detect identical tasks
    and serves cached results instead of calling LLM.
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default: 1 hour)
            max_size: Maximum cache entries (default: 1000)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_size = max_size
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        logger.info(
            f"💾 ResultCache: Initialized "
            f"(ttl={ttl_seconds}s, max_size={max_size})"
        )
    
    def _generate_key(self, task_data: Dict[str, Any]) -> str:
        """
        Generate cache key from task data.
        
        Args:
            task_data: Task data to hash
            
        Returns:
            Cache key (SHA-256 hash prefix)
        """
        # Extract relevant fields for hashing
        key_data = {
            'title': task_data.get('title', ''),
            'description': task_data.get('description', ''),
            'files': sorted(task_data.get('files_to_generate', [])),
            'agent_type': task_data.get('agent_type', 'dev')
        }
        
        # Create stable JSON string
        key_str = json.dumps(key_data, sort_keys=True)
        
        # Hash to fixed-length key
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
    
    def get(self, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached result if available and not expired.
        
        Args:
            task_data: Task data to look up
            
        Returns:
            Cached result or None if not found/expired
        """
        key = self._generate_key(task_data)
        
        if key in self.cache:
            entry = self.cache[key]
            age = datetime.now() - entry['timestamp']
            
            if age < self.ttl:
                self.hits += 1
                logger.info(
                    f"💾 Cache HIT: {key} "
                    f"(age: {age.total_seconds():.1f}s, hit_rate: {self.hit_rate():.1%})"
                )
                return entry['result']
            else:
                # Expired - remove from cache
                del self.cache[key]
                logger.debug(f"⏰ Cache EXPIRED: {key}")
        
        self.misses += 1
        logger.debug(f"❌ Cache MISS: {key} (hit_rate: {self.hit_rate():.1%})")
        return None
    
    def set(self, task_data: Dict[str, Any], result: Dict[str, Any]):
        """
        Cache a result.
        
        Args:
            task_data: Task data (used for key generation)
            result: Result to cache
        """
        # Check size limit
        if len(self.cache) >= self.max_size:
            # LRU eviction - remove oldest entry
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k]['timestamp']
            )
            del self.cache[oldest_key]
            self.evictions += 1
            logger.debug(
                f"🗑️ Cache evicted oldest: {oldest_key} "
                f"(total evictions: {self.evictions})"
            )
        
        key = self._generate_key(task_data)
        self.cache[key] = {
            'result': result,
            'timestamp': datetime.now()
        }
        
        logger.info(
            f"💾 Cache SET: {key} "
            f"(size: {len(self.cache)}/{self.max_size})"
        )
    
    def invalidate(self, task_data: Dict[str, Any]) -> bool:
        """
        Invalidate a cache entry.
        
        Args:
            task_data: Task data to invalidate
            
        Returns:
            True if entry was removed, False if not found
        """
        key = self._generate_key(task_data)
        if key in self.cache:
            del self.cache[key]
            logger.info(f"🗑️ Cache invalidated: {key}")
            return True
        return False
    
    def clear(self):
        """Clear all cache entries."""
        size = len(self.cache)
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        logger.info(f"🗑️ Cache cleared ({size} entries removed)")
    
    def hit_rate(self) -> float:
        """
        Calculate cache hit rate.
        
        Returns:
            Hit rate as decimal (0.0 to 1.0)
        """
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'hit_rate': round(self.hit_rate() * 100, 2),
            'ttl_seconds': int(self.ttl.total_seconds())
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"ResultCache(size={len(self.cache)}/{self.max_size}, "
            f"hit_rate={self.hit_rate():.1%}, "
            f"hits={self.hits}, misses={self.misses})"
        )


# ============================================================================
# Priority Assigner
# ============================================================================

class PriorityAssigner:
    """
    Assigns priority to tasks based on critical path analysis.
    
    Uses keyword matching and dependency analysis to determine
    which tasks should be processed first.
    """
    
    # Keywords that indicate critical/high priority
    CRITICAL_KEYWORDS = [
        'main', 'config', 'init', 'setup', 'core',
        'app.py', '__init__', 'settings'
    ]
    
    HIGH_KEYWORDS = [
        'model', 'schema', 'database', 'db', 'auth',
        'user', 'connection', 'middleware'
    ]
    
    NORMAL_KEYWORDS = [
        'service', 'api', 'route', 'controller',
        'handler', 'view', 'endpoint'
    ]
    
    LOW_KEYWORDS = [
        'test', 'doc', 'readme', 'example',
        'demo', 'sample', 'tutorial'
    ]
    
    def __init__(self):
        """Initialize priority assigner."""
        self.priority_stats = {
            'critical': 0,
            'high': 0,
            'normal': 0,
            'low': 0
        }
        logger.info("📊 PriorityAssigner: Initialized")
    
    def assign_priority(self, task: Dict[str, Any]) -> int:
        """
        Assign priority level to a task.
        
        Args:
            task: Task data with title, description, files_to_generate
            
        Returns:
            Priority value (1=critical, 2=high, 3=normal, 4=low)
        """
        title = task.get('title', '').lower()
        description = task.get('description', '').lower()
        files = [f.lower() for f in task.get('files_to_generate', [])]
        
        # Combine all text for analysis
        all_text = f"{title} {description} {' '.join(files)}"
        
        # Check for critical keywords
        for keyword in self.CRITICAL_KEYWORDS:
            if keyword in all_text:
                self.priority_stats['critical'] += 1
                logger.debug(
                    f"📌 Priority CRITICAL: {task.get('id', 'unknown')} "
                    f"(keyword: {keyword})"
                )
                return TaskPriority.CRITICAL.value
        
        # Check for high priority
        for keyword in self.HIGH_KEYWORDS:
            if keyword in all_text:
                self.priority_stats['high'] += 1
                logger.debug(
                    f"📌 Priority HIGH: {task.get('id', 'unknown')} "
                    f"(keyword: {keyword})"
                )
                return TaskPriority.HIGH.value
        
        # Check for low priority
        for keyword in self.LOW_KEYWORDS:
            if keyword in all_text:
                self.priority_stats['low'] += 1
                logger.debug(
                    f"📌 Priority LOW: {task.get('id', 'unknown')} "
                    f"(keyword: {keyword})"
                )
                return TaskPriority.LOW.value
        
        # Default: normal priority
        self.priority_stats['normal'] += 1
        logger.debug(f"📌 Priority NORMAL: {task.get('id', 'unknown')}")
        return TaskPriority.NORMAL.value
    
    def assign_priorities_bulk(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Assign priorities to multiple tasks.
        
        Args:
            tasks: List of tasks
            
        Returns:
            List of tasks with 'priority' field added
        """
        for task in tasks:
            if 'priority' not in task:
                task['priority'] = self.assign_priority(task)
        
        logger.info(
            f"📊 Assigned priorities to {len(tasks)} tasks: "
            f"critical={self.priority_stats['critical']}, "
            f"high={self.priority_stats['high']}, "
            f"normal={self.priority_stats['normal']}, "
            f"low={self.priority_stats['low']}"
        )
        
        return tasks
    
    def sort_by_priority(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sort tasks by priority (critical first, low last).
        
        Args:
            tasks: List of tasks with 'priority' field
            
        Returns:
            Sorted list of tasks
        """
        # Assign priorities if not present
        self.assign_priorities_bulk(tasks)
        
        # Sort by priority (lower number = higher priority)
        sorted_tasks = sorted(tasks, key=lambda t: t.get('priority', 999))
        
        logger.info(
            f"🔀 Sorted {len(tasks)} tasks by priority "
            f"(first: {sorted_tasks[0].get('id', 'unknown')}, "
            f"last: {sorted_tasks[-1].get('id', 'unknown')})"
        )
        
        return sorted_tasks
    
    def get_stats(self) -> Dict[str, Any]:
        """Get priority assignment statistics."""
        total = sum(self.priority_stats.values())
        return {
            'total_assigned': total,
            'critical': self.priority_stats['critical'],
            'high': self.priority_stats['high'],
            'normal': self.priority_stats['normal'],
            'low': self.priority_stats['low'],
            'percentages': {
                level: round(count / total * 100, 1) if total > 0 else 0
                for level, count in self.priority_stats.items()
            }
        }
    
    def reset_stats(self):
        """Reset priority statistics."""
        self.priority_stats = {k: 0 for k in self.priority_stats}
        logger.info("📊 Priority statistics reset")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"PriorityAssigner("
            f"critical={self.priority_stats['critical']}, "
            f"high={self.priority_stats['high']}, "
            f"normal={self.priority_stats['normal']}, "
            f"low={self.priority_stats['low']})"
        )
