"""
Database models for production enhancement features.

Defines the schema for project_contexts, modifications, and templates tables.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import uuid


class ProjectContext(BaseModel):
    """
    Project context model for storing project state across iterations.
    
    Stores complete project information including codebase, configuration,
    metrics, and history.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str  # 'api', 'web_app', 'mobile_backend', 'data_pipeline', 'microservice'
    status: str = 'active'  # 'active', 'archived', 'deleted'
    owner_id: str
    
    # Code and structure (stored as JSONB)
    codebase: Dict[str, str] = Field(default_factory=dict)  # filename -> content
    dependencies: List[str] = Field(default_factory=list)
    
    # Configuration (stored as JSONB)
    environment_vars: Dict[str, str] = Field(default_factory=dict)
    deployment_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Metrics
    test_coverage: float = 0.0
    security_score: float = 0.0
    performance_score: float = 0.0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_deployed_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Todo API",
                "type": "api",
                "status": "active",
                "owner_id": "user123",
                "codebase": {
                    "main.py": "from fastapi import FastAPI...",
                    "models.py": "from sqlalchemy import..."
                },
                "dependencies": ["fastapi", "sqlalchemy", "pytest"],
                "environment_vars": {
                    "DATABASE_URL": "postgresql://localhost/db",
                    "API_KEY": "***"
                },
                "deployment_config": {
                    "platform": "render",
                    "region": "us-west"
                },
                "test_coverage": 0.85,
                "security_score": 0.92,
                "performance_score": 0.88
            }
        }


class Modification(BaseModel):
    """
    Modification model for tracking project changes.
    
    Stores modification requests, impact analysis, and results.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    
    # Request details
    request: str  # Natural language modification request
    requested_by: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Analysis (stored as JSONB)
    impact_analysis: Dict[str, Any] = Field(default_factory=dict)
    affected_files: List[str] = Field(default_factory=list)
    
    # Execution
    status: str = 'pending'  # 'pending', 'approved', 'applied', 'failed', 'rejected'
    applied_at: Optional[datetime] = None
    
    # Results (stored as JSONB)
    modified_files: Dict[str, str] = Field(default_factory=dict)  # filename -> new content
    test_results: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "project_id": "550e8400-e29b-41d4-a716-446655440000",
                "request": "Add user authentication with JWT",
                "requested_by": "user123",
                "impact_analysis": {
                    "risk_level": "medium",
                    "estimated_time": "2 hours",
                    "breaking_changes": False
                },
                "affected_files": ["main.py", "auth.py", "models.py"],
                "status": "applied",
                "modified_files": {
                    "auth.py": "from fastapi import Depends..."
                },
                "test_results": {
                    "passed": True,
                    "coverage": 0.87
                }
            }
        }


class Template(BaseModel):
    """
    Template model for project templates.
    
    Stores reusable project templates with customization variables.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    category: str  # 'api', 'web', 'mobile', 'data', 'microservice'
    
    # Template content (stored as JSONB)
    files: Dict[str, str] = Field(default_factory=dict)  # filename -> template content
    
    # Configuration
    required_vars: List[str] = Field(default_factory=list)
    optional_vars: List[str] = Field(default_factory=list)
    
    # Metadata
    tech_stack: List[str] = Field(default_factory=list)
    estimated_setup_time: int = 15  # minutes
    complexity: str = 'medium'  # 'simple', 'medium', 'complex'
    tags: List[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "name": "REST API with FastAPI",
                "description": "Production-ready REST API template",
                "category": "api",
                "files": {
                    "main.py": "from fastapi import FastAPI...",
                    "requirements.txt": "fastapi\nuvicorn"
                },
                "required_vars": ["project_name", "db_name"],
                "optional_vars": ["project_description"],
                "tech_stack": ["FastAPI", "PostgreSQL", "Pytest"],
                "estimated_setup_time": 15,
                "complexity": "medium",
                "tags": ["api", "rest", "fastapi"]
            }
        }
