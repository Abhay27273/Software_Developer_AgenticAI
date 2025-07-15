from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from .task import Task

@dataclass
class Plan:
    id: str
    title: str
    description: str
    tasks: List[Task]
    created_at: datetime = field(default_factory=datetime.now)
    total_estimated_hours: Optional[float] = None
    complexity_distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tasks": [task.to_dict() for task in self.tasks],
            "created_at": self.created_at.isoformat(),
            "total_estimated_hours": self.total_estimated_hours,
            "complexity_distribution": self.complexity_distribution,
        }
