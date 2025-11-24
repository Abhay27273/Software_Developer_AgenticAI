"""
Task models for Lambda functions.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class Task:
    """
    Task model.
    
    Represents a development task within a project plan.
    """
    
    def __init__(
        self,
        id: str,
        title: str,
        description: str = "",
        status: TaskStatus = TaskStatus.PENDING,
        dependencies: Optional[List[str]] = None,
        assigned_to: Optional[str] = None,
        priority: int = 0,
        estimated_hours: float = 0.0,
        actual_hours: float = 0.0,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        completed_at: Optional[str] = None
    ):
        self.id = id
        self.title = title
        self.description = description
        self.status = status if isinstance(status, TaskStatus) else TaskStatus(status)
        self.dependencies = dependencies or []
        self.assigned_to = assigned_to
        self.priority = priority
        self.estimated_hours = estimated_hours
        self.actual_hours = actual_hours
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()
        self.completed_at = completed_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value if isinstance(self.status, TaskStatus) else self.status,
            'dependencies': self.dependencies,
            'assigned_to': self.assigned_to,
            'priority': self.priority,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'completed_at': self.completed_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create instance from dictionary."""
        return cls(
            id=data['id'],
            title=data['title'],
            description=data.get('description', ''),
            status=data.get('status', TaskStatus.PENDING),
            dependencies=data.get('dependencies', []),
            assigned_to=data.get('assigned_to'),
            priority=data.get('priority', 0),
            estimated_hours=data.get('estimated_hours', 0.0),
            actual_hours=data.get('actual_hours', 0.0),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            completed_at=data.get('completed_at')
        )
