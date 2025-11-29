"""
Unit tests for DynamoDB adapters.

Tests ProjectContext, Modification, and Template storage and retrieval
using moto library for DynamoDB mocking.

Requirements: 9.1, 9.2, 9.3, 9.5
"""

import pytest
import os
import sys
from datetime import datetime
from moto import mock_aws
import boto3

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.dynamodb_project_store import DynamoDBProjectStore
from utils.dynamodb_modification_store import DynamoDBModificationStore
from utils.dynamodb_template_store import DynamoDBTemplateStore
from models.project_context import (
    ProjectContext, ProjectType, ProjectStatus,
    Dependency, Modification, Deployment, DeploymentConfig
)
from models.modification_plan import (
    ModificationPlan, ModificationStatus, CodeChange
)
from models.template import ProjectTemplate


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['DYNAMODB_TABLE_NAME'] = 'agenticai-data'


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Create a mocked DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create table with GSI indexes
        table = dynamodb.create_table(
            TableName='agenticai-data',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2SK', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                },
                {
                    'IndexName': 'GSI2',
                    'KeySchema': [
                        {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        
        yield table


@pytest.fixture
def sample_project():
    """Create a sample ProjectContext for testing."""
    return ProjectContext(
        id='test_project_123',
        name='Test API Project',
        type=ProjectType.API,
        status=ProjectStatus.ACTIVE,
        owner_id='user_456',
        description='A test API project',
        codebase={
            'main.py': 'print("Hello World")',
            'requirements.txt': 'fastapi==0.104.1\nuvicorn==0.24.0'
        },
        dependencies=[
            Dependency(name='fastapi', version='0.104.1', type='runtime'),
            Dependency(name='uvicorn', version='0.24.0', type='runtime')
        ],
        test_coverage=0.85,
        security_score=0.92,
        performance_score=0.88
    )


@pytest.fixture
def sample_modification():
    """Create a sample ModificationPlan for testing."""
    return ModificationPlan(
        id='mod_123',
        project_id='test_project_123',
        request='Add user authentication',
        affected_files=['main.py', 'auth.py'],
        changes=[
            CodeChange(
                file_path='main.py',
                change_type='modify',
                description='Add authentication middleware',
                before_snippet='app = FastAPI()',
                after_snippet='app = FastAPI()\napp.add_middleware(AuthMiddleware)',
                line_start=10,
                line_end=10
            )
        ],
        risk_level='medium',
        risk_score=0.5,
        estimated_hours=4.0,
        complexity='medium',
        summary='Add JWT-based authentication',
        status=ModificationStatus.PENDING_APPROVAL
    )


@pytest.fixture
def sample_template():
    """Create a sample ProjectTemplate for testing."""
    return ProjectTemplate(
        id='rest-api-fastapi',
        name='REST API with FastAPI',
        description='Production-ready REST API template',
        category='api',
        files={
            'main.py': 'from fastapi import FastAPI\n\napp = FastAPI()',
            'requirements.txt': 'fastapi==0.104.1'
        },
        required_vars=['project_name', 'db_name'],
        optional_vars=['project_description'],
        tech_stack=['FastAPI', 'PostgreSQL'],
        complexity='medium',
        estimated_setup_time=15,
        tags=['api', 'rest', 'fastapi']
    )


# ============================================================================
# ProjectContext CRUD Tests
# ============================================================================

@pytest.mark.asyncio
async def test_save_and_load_project(dynamodb_table, sample_project):
    """Test saving and loading a ProjectContext."""
    store = DynamoDBProjectStore()
    
    # Save project
    result = await store.save_context(sample_project)
    assert result is True
    
    # Load project
    loaded = await store.load_context(sample_project.id)
    assert loaded is not None
    assert loaded.id == sample_project.id
    assert loaded.name == sample_project.name
    assert loaded.type == sample_project.type
    assert loaded.status == sample_project.status
    assert loaded.owner_id == sample_project.owner_id
    assert loaded.description == sample_project.description
    assert loaded.test_coverage == sample_project.test_coverage
    assert loaded.security_score == sample_project.security_score
    assert loaded.performance_score == sample_project.performance_score
    assert len(loaded.codebase) == len(sample_project.codebase)
    assert loaded.codebase['main.py'] == sample_project.codebase['main.py']
    assert len(loaded.dependencies) == len(sample_project.dependencies)


@pytest.mark.asyncio
async def test_load_nonexistent_project(dynamodb_table):
    """Test loading a project that doesn't exist."""
    store = DynamoDBProjectStore()
    
    loaded = await store.load_context('nonexistent_project')
    assert loaded is None


@pytest.mark.asyncio
async def test_update_project(dynamodb_table, sample_project):
    """Test updating a ProjectContext."""
    store = DynamoDBProjectStore()
    
    # Save initial project
    await store.save_context(sample_project)
    
    # Update project
    sample_project.name = 'Updated API Project'
    sample_project.description = 'Updated description'
    sample_project.test_coverage = 0.95
    
    result = await store.update_context(sample_project)
    assert result is True
    
    # Load and verify
    loaded = await store.load_context(sample_project.id)
    assert loaded.name == 'Updated API Project'
    assert loaded.description == 'Updated description'
    assert loaded.test_coverage == 0.95


@pytest.mark.asyncio
async def test_update_project_fields(dynamodb_table, sample_project):
    """Test updating specific fields of a ProjectContext."""
    store = DynamoDBProjectStore()
    
    # Save initial project
    await store.save_context(sample_project)
    
    # Update specific fields
    updates = {
        'name': 'Partially Updated Project',
        'test_coverage': 0.90
    }
    result = await store.update_context_fields(sample_project.id, updates)
    assert result is True
    
    # Load and verify
    loaded = await store.load_context(sample_project.id)
    assert loaded.name == 'Partially Updated Project'
    assert loaded.test_coverage == 0.90
    assert loaded.description == sample_project.description  # Unchanged


@pytest.mark.asyncio
async def test_delete_project(dynamodb_table, sample_project):
    """Test deleting a ProjectContext."""
    store = DynamoDBProjectStore()
    
    # Save project
    await store.save_context(sample_project)
    
    # Verify it exists
    exists = await store.context_exists(sample_project.id)
    assert exists is True
    
    # Delete project
    result = await store.delete_context(sample_project.id)
    assert result is True
    
    # Verify it's gone
    exists = await store.context_exists(sample_project.id)
    assert exists is False
    
    loaded = await store.load_context(sample_project.id)
    assert loaded is None


@pytest.mark.asyncio
async def test_context_exists(dynamodb_table, sample_project):
    """Test checking if a ProjectContext exists."""
    store = DynamoDBProjectStore()
    
    # Check non-existent project
    exists = await store.context_exists('nonexistent')
    assert exists is False
    
    # Save project
    await store.save_context(sample_project)
    
    # Check existing project
    exists = await store.context_exists(sample_project.id)
    assert exists is True


@pytest.mark.asyncio
async def test_list_contexts(dynamodb_table):
    """Test listing all ProjectContexts."""
    store = DynamoDBProjectStore()
    
    # Create multiple projects
    projects = [
        ProjectContext(
            id=f'project_{i}',
            name=f'Project {i}',
            type=ProjectType.API,
            status=ProjectStatus.ACTIVE,
            owner_id='user_456'
        )
        for i in range(3)
    ]
    
    # Save all projects
    for project in projects:
        await store.save_context(project)
    
    # List all contexts
    contexts = await store.list_contexts()
    assert len(contexts) >= 3
    
    # Verify project IDs
    context_ids = [c.id for c in contexts]
    for project in projects:
        assert project.id in context_ids


@pytest.mark.asyncio
async def test_query_by_owner(dynamodb_table):
    """Test querying projects by owner using GSI1."""
    store = DynamoDBProjectStore()
    
    # Create projects with different owners
    project1 = ProjectContext(
        id='project_1',
        name='Project 1',
        type=ProjectType.API,
        status=ProjectStatus.ACTIVE,
        owner_id='user_123'
    )
    project2 = ProjectContext(
        id='project_2',
        name='Project 2',
        type=ProjectType.WEB,
        status=ProjectStatus.ACTIVE,
        owner_id='user_123'
    )
    project3 = ProjectContext(
        id='project_3',
        name='Project 3',
        type=ProjectType.API,
        status=ProjectStatus.ACTIVE,
        owner_id='user_456'
    )
    
    await store.save_context(project1)
    await store.save_context(project2)
    await store.save_context(project3)
    
    # Query by owner
    contexts = await store.query_by_owner('user_123')
    assert len(contexts) == 2
    assert all(c.owner_id == 'user_123' for c in contexts)


@pytest.mark.asyncio
async def test_query_by_status(dynamodb_table):
    """Test querying projects by status using GSI2."""
    store = DynamoDBProjectStore()
    
    # Create projects with different statuses
    project1 = ProjectContext(
        id='project_1',
        name='Project 1',
        type=ProjectType.API,
        status=ProjectStatus.ACTIVE,
        owner_id='user_123'
    )
    project2 = ProjectContext(
        id='project_2',
        name='Project 2',
        type=ProjectType.WEB,
        status=ProjectStatus.ARCHIVED,
        owner_id='user_123'
    )
    project3 = ProjectContext(
        id='project_3',
        name='Project 3',
        type=ProjectType.API,
        status=ProjectStatus.ACTIVE,
        owner_id='user_456'
    )
    
    await store.save_context(project1)
    await store.save_context(project2)
    await store.save_context(project3)
    
    # Query by status
    contexts = await store.query_by_status('active')
    assert len(contexts) == 2
    assert all(c.status == ProjectStatus.ACTIVE for c in contexts)


@pytest.mark.asyncio
async def test_add_modification_to_project(dynamodb_table, sample_project):
    """Test adding a modification record to a project."""
    store = DynamoDBProjectStore()
    
    # Save project
    await store.save_context(sample_project)
    
    # Add modification
    modification = {
        'id': 'mod_123',
        'description': 'Added authentication',
        'affected_files': ['main.py', 'auth.py'],
        'requested_by': 'user_456',
        'status': 'applied'
    }
    result = await store.add_modification(sample_project.id, modification)
    assert result is True
    
    # Load and verify
    loaded = await store.load_context(sample_project.id)
    assert len(loaded.modifications) > 0
    assert loaded.modifications[-1].description == 'Added authentication'


@pytest.mark.asyncio
async def test_add_deployment_to_project(dynamodb_table, sample_project):
    """Test adding a deployment record to a project."""
    store = DynamoDBProjectStore()
    
    # Save project
    await store.save_context(sample_project)
    
    # Add deployment
    deployment = {
        'id': 'deploy_123',
        'environment': 'production',
        'platform': 'aws',
        'url': 'https://api.example.com',
        'status': 'success'
    }
    result = await store.add_deployment(sample_project.id, deployment)
    assert result is True
    
    # Load and verify
    loaded = await store.load_context(sample_project.id)
    assert len(loaded.deployments) > 0
    assert loaded.deployments[-1].environment == 'production'
    assert loaded.last_deployed_at is not None


# ============================================================================
# Modification CRUD Tests
# ============================================================================

@pytest.mark.asyncio
async def test_save_and_load_modification(dynamodb_table, sample_modification):
    """Test saving and loading a ModificationPlan."""
    store = DynamoDBModificationStore()
    
    # Save modification
    result = await store.save_modification(sample_modification)
    assert result is True
    
    # Load modification
    loaded = await store.load_modification(
        sample_modification.project_id,
        sample_modification.id
    )
    assert loaded is not None
    assert loaded.id == sample_modification.id
    assert loaded.project_id == sample_modification.project_id
    assert loaded.request == sample_modification.request
    assert loaded.risk_level == sample_modification.risk_level
    assert loaded.status == sample_modification.status
    assert len(loaded.changes) == len(sample_modification.changes)


@pytest.mark.asyncio
async def test_load_nonexistent_modification(dynamodb_table):
    """Test loading a modification that doesn't exist."""
    store = DynamoDBModificationStore()
    
    loaded = await store.load_modification('project_123', 'nonexistent_mod')
    assert loaded is None


@pytest.mark.asyncio
async def test_update_modification(dynamodb_table, sample_modification):
    """Test updating a ModificationPlan."""
    store = DynamoDBModificationStore()
    
    # Save initial modification
    await store.save_modification(sample_modification)
    
    # Update modification
    sample_modification.status = ModificationStatus.APPROVED
    sample_modification.approved_by = 'user_789'
    sample_modification.approved_at = datetime.utcnow()
    
    result = await store.update_modification(sample_modification)
    assert result is True
    
    # Load and verify
    loaded = await store.load_modification(
        sample_modification.project_id,
        sample_modification.id
    )
    assert loaded.status == ModificationStatus.APPROVED
    assert loaded.approved_by == 'user_789'
    assert loaded.approved_at is not None


@pytest.mark.asyncio
async def test_delete_modification(dynamodb_table, sample_modification):
    """Test deleting a ModificationPlan."""
    store = DynamoDBModificationStore()
    
    # Save modification
    await store.save_modification(sample_modification)
    
    # Verify it exists
    exists = await store.modification_exists(
        sample_modification.project_id,
        sample_modification.id
    )
    assert exists is True
    
    # Delete modification
    result = await store.delete_modification(
        sample_modification.project_id,
        sample_modification.id
    )
    assert result is True
    
    # Verify it's gone
    exists = await store.modification_exists(
        sample_modification.project_id,
        sample_modification.id
    )
    assert exists is False


@pytest.mark.asyncio
async def test_list_modifications_by_project(dynamodb_table):
    """Test listing modifications for a specific project."""
    store = DynamoDBModificationStore()
    
    project_id = 'test_project_123'
    
    # Create multiple modifications
    modifications = [
        ModificationPlan(
            id=f'mod_{i}',
            project_id=project_id,
            request=f'Modification {i}',
            status=ModificationStatus.PENDING_APPROVAL
        )
        for i in range(3)
    ]
    
    # Save all modifications
    for mod in modifications:
        await store.save_modification(mod)
    
    # List modifications for project
    loaded_mods = await store.list_modifications_by_project(project_id)
    assert len(loaded_mods) == 3
    
    # Verify modification IDs
    mod_ids = [m.id for m in loaded_mods]
    for mod in modifications:
        assert mod.id in mod_ids


@pytest.mark.asyncio
async def test_list_modifications_by_status(dynamodb_table):
    """Test listing modifications by status using GSI1."""
    store = DynamoDBModificationStore()
    
    # Create modifications with different statuses
    mod1 = ModificationPlan(
        id='mod_1',
        project_id='project_1',
        request='Modification 1',
        status=ModificationStatus.PENDING_APPROVAL
    )
    mod2 = ModificationPlan(
        id='mod_2',
        project_id='project_2',
        request='Modification 2',
        status=ModificationStatus.APPROVED
    )
    mod3 = ModificationPlan(
        id='mod_3',
        project_id='project_3',
        request='Modification 3',
        status=ModificationStatus.PENDING_APPROVAL
    )
    
    await store.save_modification(mod1)
    await store.save_modification(mod2)
    await store.save_modification(mod3)
    
    # Query by status
    pending_mods = await store.list_modifications_by_status('pending_approval')
    assert len(pending_mods) == 2
    assert all(m.status == ModificationStatus.PENDING_APPROVAL for m in pending_mods)


@pytest.mark.asyncio
async def test_update_modification_status(dynamodb_table, sample_modification):
    """Test updating modification status."""
    store = DynamoDBModificationStore()
    
    # Save modification
    await store.save_modification(sample_modification)
    
    # Update status to IN_PROGRESS
    result = await store.update_modification_status(
        sample_modification.project_id,
        sample_modification.id,
        ModificationStatus.IN_PROGRESS
    )
    assert result is True
    
    # Load and verify
    loaded = await store.load_modification(
        sample_modification.project_id,
        sample_modification.id
    )
    assert loaded.status == ModificationStatus.IN_PROGRESS
    assert loaded.started_at is not None


@pytest.mark.asyncio
async def test_approve_modification(dynamodb_table, sample_modification):
    """Test approving a modification."""
    store = DynamoDBModificationStore()
    
    # Save modification
    await store.save_modification(sample_modification)
    
    # Approve modification
    result = await store.approve_modification(
        sample_modification.project_id,
        sample_modification.id,
        'user_789'
    )
    assert result is True
    
    # Load and verify
    loaded = await store.load_modification(
        sample_modification.project_id,
        sample_modification.id
    )
    assert loaded.status == ModificationStatus.APPROVED
    assert loaded.approved_by == 'user_789'
    assert loaded.approved_at is not None


@pytest.mark.asyncio
async def test_reject_modification(dynamodb_table, sample_modification):
    """Test rejecting a modification."""
    store = DynamoDBModificationStore()
    
    # Save modification
    await store.save_modification(sample_modification)
    
    # Reject modification
    result = await store.reject_modification(
        sample_modification.project_id,
        sample_modification.id
    )
    assert result is True
    
    # Load and verify
    loaded = await store.load_modification(
        sample_modification.project_id,
        sample_modification.id
    )
    assert loaded.status == ModificationStatus.REJECTED


# ============================================================================
# Template CRUD Tests
# ============================================================================

@pytest.mark.asyncio
async def test_save_and_load_template(dynamodb_table, sample_template):
    """Test saving and loading a ProjectTemplate."""
    store = DynamoDBTemplateStore()
    
    # Save template
    result = await store.save_template(sample_template)
    assert result is True
    
    # Load template
    loaded = await store.load_template(sample_template.id)
    assert loaded is not None
    assert loaded.id == sample_template.id
    assert loaded.name == sample_template.name
    assert loaded.description == sample_template.description
    assert loaded.category == sample_template.category
    assert len(loaded.files) == len(sample_template.files)
    assert loaded.files['main.py'] == sample_template.files['main.py']
    assert loaded.required_vars == sample_template.required_vars
    assert loaded.tech_stack == sample_template.tech_stack


@pytest.mark.asyncio
async def test_load_nonexistent_template(dynamodb_table):
    """Test loading a template that doesn't exist."""
    store = DynamoDBTemplateStore()
    
    loaded = await store.load_template('nonexistent_template')
    assert loaded is None


@pytest.mark.asyncio
async def test_update_template(dynamodb_table, sample_template):
    """Test updating a ProjectTemplate."""
    store = DynamoDBTemplateStore()
    
    # Save initial template
    await store.save_template(sample_template)
    
    # Update template
    sample_template.name = 'Updated REST API Template'
    sample_template.description = 'Updated description'
    sample_template.files['config.py'] = 'CONFIG = {}'
    
    result = await store.update_template(sample_template)
    assert result is True
    
    # Load and verify
    loaded = await store.load_template(sample_template.id)
    assert loaded.name == 'Updated REST API Template'
    assert loaded.description == 'Updated description'
    assert 'config.py' in loaded.files


@pytest.mark.asyncio
async def test_delete_template(dynamodb_table, sample_template):
    """Test deleting a ProjectTemplate."""
    store = DynamoDBTemplateStore()
    
    # Save template
    await store.save_template(sample_template)
    
    # Verify it exists
    exists = await store.template_exists(sample_template.id)
    assert exists is True
    
    # Delete template
    result = await store.delete_template(sample_template.id)
    assert result is True
    
    # Verify it's gone
    exists = await store.template_exists(sample_template.id)
    assert exists is False


@pytest.mark.asyncio
async def test_template_exists(dynamodb_table, sample_template):
    """Test checking if a template exists."""
    store = DynamoDBTemplateStore()
    
    # Check non-existent template
    exists = await store.template_exists('nonexistent')
    assert exists is False
    
    # Save template
    await store.save_template(sample_template)
    
    # Check existing template
    exists = await store.template_exists(sample_template.id)
    assert exists is True


@pytest.mark.asyncio
async def test_list_templates(dynamodb_table):
    """Test listing all templates."""
    store = DynamoDBTemplateStore()
    
    # Create multiple templates
    templates = [
        ProjectTemplate(
            id=f'template_{i}',
            name=f'Template {i}',
            description=f'Description {i}',
            category='api',
            files={'main.py': f'# Template {i}'}
        )
        for i in range(3)
    ]
    
    # Save all templates
    for template in templates:
        await store.save_template(template)
    
    # List all templates
    loaded_templates = await store.list_templates()
    assert len(loaded_templates) >= 3
    
    # Verify template IDs
    template_ids = [t.id for t in loaded_templates]
    for template in templates:
        assert template.id in template_ids


@pytest.mark.asyncio
async def test_list_templates_by_category(dynamodb_table):
    """Test listing templates by category using GSI1."""
    store = DynamoDBTemplateStore()
    
    # Create templates with different categories
    template1 = ProjectTemplate(
        id='template_1',
        name='API Template',
        description='API template',
        category='api',
        files={'main.py': '# API'}
    )
    template2 = ProjectTemplate(
        id='template_2',
        name='Web Template',
        description='Web template',
        category='web',
        files={'index.html': '<html></html>'}
    )
    template3 = ProjectTemplate(
        id='template_3',
        name='Another API Template',
        description='Another API template',
        category='api',
        files={'app.py': '# App'}
    )
    
    await store.save_template(template1)
    await store.save_template(template2)
    await store.save_template(template3)
    
    # List templates by category
    api_templates = await store.list_templates(category='api')
    assert len(api_templates) == 2
    assert all(t.category == 'api' for t in api_templates)


@pytest.mark.asyncio
async def test_get_template_file(dynamodb_table, sample_template):
    """Test retrieving a specific file from a template."""
    store = DynamoDBTemplateStore()
    
    # Save template
    await store.save_template(sample_template)
    
    # Get specific file
    content = await store.get_template_file(sample_template.id, 'main.py')
    assert content is not None
    assert content == sample_template.files['main.py']
    
    # Try to get non-existent file
    content = await store.get_template_file(sample_template.id, 'nonexistent.py')
    assert content is None


@pytest.mark.asyncio
async def test_list_template_files(dynamodb_table, sample_template):
    """Test listing all file paths in a template."""
    store = DynamoDBTemplateStore()
    
    # Save template
    await store.save_template(sample_template)
    
    # List files
    file_paths = await store.list_template_files(sample_template.id)
    assert len(file_paths) == len(sample_template.files)
    assert 'main.py' in file_paths
    assert 'requirements.txt' in file_paths


@pytest.mark.asyncio
async def test_update_template_metadata(dynamodb_table, sample_template):
    """Test updating template metadata without loading files."""
    store = DynamoDBTemplateStore()
    
    # Save template
    await store.save_template(sample_template)
    
    # Update metadata
    updates = {
        'name': 'Updated Template Name',
        'complexity': 'high'
    }
    result = await store.update_template_metadata(sample_template.id, updates)
    assert result is True
    
    # Load and verify
    loaded = await store.load_template(sample_template.id)
    assert loaded.name == 'Updated Template Name'
    assert loaded.complexity == 'high'
    assert loaded.description == sample_template.description  # Unchanged


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
