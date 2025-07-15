from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 5
    HIGH = 8
    CRITICAL = 10
