from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from .enums import TaskStatus

@dataclass
class Task:
    id: str
    title: str
    description: str
    priority: int
    status: TaskStatus
    dependencies: List[str] = field(default_factory=list)
    estimated_hours: Optional[float] = None
    complexity: Optional[str] = None
    agent_type: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "estimated_hours": self.estimated_hours,
            "complexity": self.complexity,
            "agent_type": self.agent_type,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }