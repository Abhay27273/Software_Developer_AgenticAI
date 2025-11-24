"""
Plan models for Lambda functions.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from .task import Task


class Plan:
    """
    Plan model.
    
    Represents a project implementation plan with tasks.
    """
    
    def __init__(
        self,
        id: str,
        project_id: str,
        title: str,
        description: str = "",
        tasks: Optional[List[Task]] = None,
        status: str = "draft",
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None
    ):
        self.id = id
        self.project_id = project_id
        self.title = title
        self.description = description
        self.tasks = tasks or []
        self.status = status
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'description': self.description,
            'tasks': [t.to_dict() if isinstance(t, Task) else t for t in self.tasks],
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Plan':
        """Create instance from dictionary."""
        tasks = []
        for task_data in data.get('tasks', []):
            if isinstance(task_data, Task):
                tasks.append(task_data)
            else:
                tasks.append(Task.from_dict(task_data))
        
        return cls(
            id=data['id'],
            project_id=data['project_id'],
            title=data['title'],
            description=data.get('description', ''),
            tasks=tasks,
            status=data.get('status', 'draft'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
