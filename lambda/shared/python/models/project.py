"""
Project context models for Lambda functions.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class ProjectType(str, Enum):
    """Project type enumeration."""
    API = "api"
    WEB = "web"
    MOBILE = "mobile"
    DATA = "data"
    MICROSERVICE = "microservice"
    OTHER = "other"


class ProjectStatus(str, Enum):
    """Project status enumeration."""
    CREATED = "created"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    COMPLETED = "completed"
    ERROR = "error"
    ARCHIVED = "archived"


class ProjectContext:
    """
    Project context model.
    
    Represents a software project with its metadata and configuration.
    """
    
    def __init__(
        self,
        id: str,
        name: str,
        type: ProjectType,
        status: ProjectStatus,
        owner_id: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        environment_vars: Optional[Dict[str, str]] = None,
        deployment_config: Optional[Dict[str, Any]] = None,
        test_coverage: float = 0.0,
        security_score: float = 0.0,
        performance_score: float = 0.0,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None
    ):
        self.id = id
        self.name = name
        self.type = type if isinstance(type, ProjectType) else ProjectType(type)
        self.status = status if isinstance(status, ProjectStatus) else ProjectStatus(status)
        self.owner_id = owner_id
        self.description = description
        self.dependencies = dependencies or []
        self.environment_vars = environment_vars or {}
        self.deployment_config = deployment_config or {}
        self.test_coverage = test_coverage
        self.security_score = security_score
        self.performance_score = performance_score
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value if isinstance(self.type, ProjectType) else self.type,
            'status': self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            'owner_id': self.owner_id,
            'description': self.description,
            'dependencies': self.dependencies,
            'environment_vars': self.environment_vars,
            'deployment_config': self.deployment_config,
            'test_coverage': self.test_coverage,
            'security_score': self.security_score,
            'performance_score': self.performance_score,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectContext':
        """Create instance from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            type=data['type'],
            status=data['status'],
            owner_id=data['owner_id'],
            description=data.get('description', ''),
            dependencies=data.get('dependencies', []),
            environment_vars=data.get('environment_vars', {}),
            deployment_config=data.get('deployment_config', {}),
            test_coverage=data.get('test_coverage', 0.0),
            security_score=data.get('security_score', 0.0),
            performance_score=data.get('performance_score', 0.0),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
