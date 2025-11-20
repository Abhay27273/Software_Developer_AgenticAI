from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class ProjectTemplate:
    """
    Represents a project template that can be used to bootstrap new projects.
    
    Templates include pre-configured file structures, dependencies, and
    best practices for specific project types.
    """
    # Core identification
    id: str
    name: str
    description: str
    category: str  # 'api', 'web_app', 'mobile_backend', 'data_pipeline', 'microservice'
    
    # Template content
    files: Dict[str, str] = field(default_factory=dict)  # filename -> template content
    
    # Configuration variables
    required_vars: List[str] = field(default_factory=list)  # Variables user must provide
    optional_vars: List[str] = field(default_factory=list)  # Optional variables with defaults
    
    # Metadata
    tech_stack: List[str] = field(default_factory=list)  # e.g., ['FastAPI', 'PostgreSQL', 'Redis']
    estimated_setup_time: int = 30  # minutes
    complexity: str = "medium"  # 'simple', 'medium', 'complex'
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Optional metadata
    author: str = "system"
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert ProjectTemplate to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "files": self.files,
            "required_vars": self.required_vars,
            "optional_vars": self.optional_vars,
            "tech_stack": self.tech_stack,
            "estimated_setup_time": self.estimated_setup_time,
            "complexity": self.complexity,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "author": self.author,
            "version": self.version,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectTemplate':
        """Create ProjectTemplate from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=data["category"],
            files=data.get("files", {}),
            required_vars=data.get("required_vars", []),
            optional_vars=data.get("optional_vars", []),
            tech_stack=data.get("tech_stack", []),
            estimated_setup_time=data.get("estimated_setup_time", 30),
            complexity=data.get("complexity", "medium"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            author=data.get("author", "system"),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", [])
        )
    
    # Dict-like access methods for backward compatibility
    def __getitem__(self, key: str):
        """Enable dictionary-style access (e.g., template['id'])."""
        return getattr(self, key)
    
    def __contains__(self, key: str) -> bool:
        """Enable 'in' operator for checking attribute existence."""
        return hasattr(self, key)
    
    def __iter__(self):
        """Enable iteration over template attributes."""
        return iter(self.to_dict())
    
    def keys(self):
        """Return template keys for dict-like behavior."""
        return self.to_dict().keys()
    
    def get(self, key: str, default=None):
        """Get attribute value with optional default (dict-like behavior)."""
        return getattr(self, key, default)
