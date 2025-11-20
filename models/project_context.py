from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class ProjectType(Enum):
    """Types of projects that can be created."""
    API = "api"
    WEB_APP = "web_app"
    MOBILE_BACKEND = "mobile_backend"
    DATA_PIPELINE = "data_pipeline"
    MICROSERVICE = "microservice"
    OTHER = "other"


class ProjectStatus(Enum):
    """Status of a project."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    FAILED = "failed"


@dataclass
class Dependency:
    """Represents a project dependency."""
    name: str
    version: str
    type: str  # 'runtime', 'dev', 'optional'


@dataclass
class Modification:
    """Represents a modification made to a project."""
    id: str
    timestamp: datetime
    description: str
    affected_files: List[str]
    requested_by: str
    status: str  # 'pending', 'applied', 'failed', 'rolled_back'


@dataclass
class Deployment:
    """Represents a deployment of a project."""
    id: str
    timestamp: datetime
    environment: str  # 'dev', 'staging', 'production'
    platform: str  # 'render', 'railway', 'flyio', etc.
    url: Optional[str] = None
    status: str = "pending"  # 'pending', 'success', 'failed'


@dataclass
class DeploymentConfig:
    """Configuration for project deployment."""
    platform: str = "render"
    environment: str = "production"
    auto_deploy: bool = False
    health_check_enabled: bool = True
    monitoring_enabled: bool = False


@dataclass
class ProjectContext:
    """
    Stores complete project state across iterations.
    Enables project modification, tracking, and persistence.
    """
    # Core identification
    id: str
    name: str
    type: ProjectType
    status: ProjectStatus = ProjectStatus.CREATED
    
    # Ownership
    owner_id: str = "default_user"
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_deployed_at: Optional[datetime] = None
    
    # Code and structure
    codebase: Dict[str, str] = field(default_factory=dict)  # filename -> content
    dependencies: List[Dependency] = field(default_factory=list)
    
    # History tracking
    modifications: List[Modification] = field(default_factory=list)
    deployments: List[Deployment] = field(default_factory=list)
    
    # Configuration
    environment_vars: Dict[str, str] = field(default_factory=dict)
    deployment_config: DeploymentConfig = field(default_factory=DeploymentConfig)
    
    # Metrics
    test_coverage: float = 0.0
    security_score: float = 0.0
    performance_score: float = 0.0
    
    # Optional metadata
    description: str = ""
    repository_url: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert ProjectContext to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_deployed_at": self.last_deployed_at.isoformat() if self.last_deployed_at else None,
            "codebase": self.codebase,
            "dependencies": [
                {"name": d.name, "version": d.version, "type": d.type}
                for d in self.dependencies
            ],
            "modifications": [
                {
                    "id": m.id,
                    "timestamp": m.timestamp.isoformat(),
                    "description": m.description,
                    "affected_files": m.affected_files,
                    "requested_by": m.requested_by,
                    "status": m.status
                }
                for m in self.modifications
            ],
            "deployments": [
                {
                    "id": d.id,
                    "timestamp": d.timestamp.isoformat(),
                    "environment": d.environment,
                    "platform": d.platform,
                    "url": d.url,
                    "status": d.status
                }
                for d in self.deployments
            ],
            "environment_vars": self.environment_vars,
            "deployment_config": {
                "platform": self.deployment_config.platform,
                "environment": self.deployment_config.environment,
                "auto_deploy": self.deployment_config.auto_deploy,
                "health_check_enabled": self.deployment_config.health_check_enabled,
                "monitoring_enabled": self.deployment_config.monitoring_enabled
            },
            "test_coverage": self.test_coverage,
            "security_score": self.security_score,
            "performance_score": self.performance_score,
            "description": self.description,
            "repository_url": self.repository_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectContext':
        """Create ProjectContext from dictionary."""
        # Parse dependencies
        dependencies = [
            Dependency(
                name=d["name"],
                version=d["version"],
                type=d["type"]
            )
            for d in data.get("dependencies", [])
        ]
        
        # Parse modifications
        modifications = [
            Modification(
                id=m["id"],
                timestamp=datetime.fromisoformat(m["timestamp"]),
                description=m["description"],
                affected_files=m["affected_files"],
                requested_by=m["requested_by"],
                status=m["status"]
            )
            for m in data.get("modifications", [])
        ]
        
        # Parse deployments
        deployments = [
            Deployment(
                id=d["id"],
                timestamp=datetime.fromisoformat(d["timestamp"]),
                environment=d["environment"],
                platform=d["platform"],
                url=d.get("url"),
                status=d["status"]
            )
            for d in data.get("deployments", [])
        ]
        
        # Parse deployment config
        dc_data = data.get("deployment_config", {})
        deployment_config = DeploymentConfig(
            platform=dc_data.get("platform", "render"),
            environment=dc_data.get("environment", "production"),
            auto_deploy=dc_data.get("auto_deploy", False),
            health_check_enabled=dc_data.get("health_check_enabled", True),
            monitoring_enabled=dc_data.get("monitoring_enabled", False)
        )
        
        return cls(
            id=data["id"],
            name=data["name"],
            type=ProjectType(data["type"]),
            status=ProjectStatus(data["status"]),
            owner_id=data.get("owner_id", "default_user"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_deployed_at=datetime.fromisoformat(data["last_deployed_at"]) if data.get("last_deployed_at") else None,
            codebase=data.get("codebase", {}),
            dependencies=dependencies,
            modifications=modifications,
            deployments=deployments,
            environment_vars=data.get("environment_vars", {}),
            deployment_config=deployment_config,
            test_coverage=data.get("test_coverage", 0.0),
            security_score=data.get("security_score", 0.0),
            performance_score=data.get("performance_score", 0.0),
            description=data.get("description", ""),
            repository_url=data.get("repository_url")
        )
