from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    KIPPED = "skipped"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 5
    HIGH = 8
    CRITICAL = 10

class ProjectStatus(Enum):
    """Project status constants."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"
    PENDING = "PENDING"

# Export constants for backward compatibility
ACTIVE = ProjectStatus.ACTIVE.value
INACTIVE = ProjectStatus.INACTIVE.value
ARCHIVED = ProjectStatus.ARCHIVED.value
DELETED = ProjectStatus.DELETED.value
PENDING = ProjectStatus.PENDING.value