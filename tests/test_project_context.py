"""
Tests for ProjectContext model and ProjectContextStore.
"""
import pytest
import asyncio
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from models.project_context import (
    ProjectContext, ProjectType, ProjectStatus, 
    Dependency, Modification, Deployment, DeploymentConfig
)
from utils.project_context_store import ProjectContextStore


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def context_store(temp_storage):
    """Create a ProjectContextStore with temporary storage."""
    return ProjectContextStore(storage_root=temp_storage)


@pytest.fixture
def sample_context():
    """Create a sample ProjectContext for testing."""
    return ProjectContext(
        id="test_project_123",
        name="Test API Project",
        type=ProjectType.API,
        status=ProjectStatus.CREATED,
        owner_id="test_user",
        description="A test REST API project",
        codebase={
            "main.py": "print('Hello World')",
            "config.py": "DEBUG = True"
        },
        dependencies=[
            Dependency(name="fastapi", version="0.100.0", type="runtime"),
            Dependency(name="pytest", version="7.4.0", type="dev")
        ],
        environment_vars={
            "DATABASE_URL": "postgresql://localhost/testdb",
            "API_KEY": "test_key_123"
        },
        test_coverage=0.85,
        security_score=0.92,
        performance_score=0.88
    )


class TestProjectContext:
    """Tests for ProjectContext model."""
    
    def test_project_context_creation(self, sample_context):
        """Test creating a ProjectContext instance."""
        assert sample_context.id == "test_project_123"
        assert sample_context.name == "Test API Project"
        assert sample_context.type == ProjectType.API
        assert sample_context.status == ProjectStatus.CREATED
        assert len(sample_context.dependencies) == 2
        assert sample_context.test_coverage == 0.85
    
    def test_project_context_to_dict(self, sample_context):
        """Test serializing ProjectContext to dictionary."""
        data = sample_context.to_dict()
        
        assert data["id"] == "test_project_123"
        assert data["name"] == "Test API Project"
        assert data["type"] == "api"
        assert data["status"] == "created"
        assert len(data["dependencies"]) == 2
        assert data["dependencies"][0]["name"] == "fastapi"
        assert data["test_coverage"] == 0.85
    
    def test_project_context_from_dict(self, sample_context):
        """Test deserializing ProjectContext from dictionary."""
        data = sample_context.to_dict()
        restored = ProjectContext.from_dict(data)
        
        assert restored.id == sample_context.id
        assert restored.name == sample_context.name
        assert restored.type == sample_context.type
        assert restored.status == sample_context.status
        assert len(restored.dependencies) == len(sample_context.dependencies)
        assert restored.test_coverage == sample_context.test_coverage


class TestProjectContextStore:
    """Tests for ProjectContextStore."""
    
    @pytest.mark.asyncio
    async def test_save_and_load_context(self, context_store, sample_context):
        """Test saving and loading a project context."""
        # Save context
        success = await context_store.save_context(sample_context)
        assert success is True
        
        # Load context
        loaded = await context_store.load_context(sample_context.id)
        assert loaded is not None
        assert loaded.id == sample_context.id
        assert loaded.name == sample_context.name
        assert loaded.type == sample_context.type
        assert len(loaded.dependencies) == 2
    
    @pytest.mark.asyncio
    async def test_update_context(self, context_store, sample_context):
        """Test updating a project context."""
        # Save initial context
        await context_store.save_context(sample_context)
        
        # Update context
        updates = {
            "status": "in_progress",
            "test_coverage": 0.95,
            "description": "Updated description"
        }
        success = await context_store.update_context(sample_context.id, updates)
        assert success is True
        
        # Load and verify updates
        loaded = await context_store.load_context(sample_context.id)
        assert loaded.status == ProjectStatus.IN_PROGRESS
        assert loaded.test_coverage == 0.95
        assert loaded.description == "Updated description"
    
    @pytest.mark.asyncio
    async def test_list_contexts(self, context_store, sample_context):
        """Test listing project contexts."""
        # Create multiple contexts
        context1 = sample_context
        context2 = ProjectContext(
            id="test_project_456",
            name="Another Project",
            type=ProjectType.WEB_APP,
            status=ProjectStatus.CREATED,
            owner_id="test_user"
        )
        
        await context_store.save_context(context1)
        await context_store.save_context(context2)
        
        # List all contexts
        contexts = await context_store.list_contexts()
        assert len(contexts) == 2
        
        # List contexts by owner
        user_contexts = await context_store.list_contexts(owner_id="test_user")
        assert len(user_contexts) == 2
    
    @pytest.mark.asyncio
    async def test_delete_context(self, context_store, sample_context):
        """Test deleting a project context."""
        # Save context
        await context_store.save_context(sample_context)
        
        # Verify it exists
        exists = await context_store.context_exists(sample_context.id)
        assert exists is True
        
        # Delete context
        success = await context_store.delete_context(sample_context.id)
        assert success is True
        
        # Verify it's gone
        exists = await context_store.context_exists(sample_context.id)
        assert exists is False
    
    @pytest.mark.asyncio
    async def test_add_modification(self, context_store, sample_context):
        """Test adding a modification to project history."""
        # Save initial context
        await context_store.save_context(sample_context)
        
        # Add modification
        modification = {
            "description": "Added authentication feature",
            "affected_files": ["auth.py", "main.py"],
            "requested_by": "test_user",
            "status": "applied"
        }
        success = await context_store.add_modification(sample_context.id, modification)
        assert success is True
        
        # Load and verify modification
        loaded = await context_store.load_context(sample_context.id)
        assert len(loaded.modifications) == 1
        assert loaded.modifications[0].description == "Added authentication feature"
        assert len(loaded.modifications[0].affected_files) == 2
    
    @pytest.mark.asyncio
    async def test_add_deployment(self, context_store, sample_context):
        """Test adding a deployment to project history."""
        # Save initial context
        await context_store.save_context(sample_context)
        
        # Add deployment
        deployment = {
            "environment": "production",
            "platform": "render",
            "url": "https://test-api.onrender.com",
            "status": "success"
        }
        success = await context_store.add_deployment(sample_context.id, deployment)
        assert success is True
        
        # Load and verify deployment
        loaded = await context_store.load_context(sample_context.id)
        assert len(loaded.deployments) == 1
        assert loaded.deployments[0].environment == "production"
        assert loaded.deployments[0].platform == "render"
        assert loaded.last_deployed_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
