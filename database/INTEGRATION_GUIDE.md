# Database Integration Guide

This guide explains how to integrate the new database system with existing components.

## Overview

The database system provides persistent storage for:
- Project contexts (replacing file-based storage)
- Modification tracking (new feature)
- Template library (replacing file-based storage)

## Integration Points

### 1. ProjectContextStore Integration

**Current:** `utils/project_context_store.py` uses JSON file storage
**Target:** Migrate to database backend

#### Steps:

1. Update `utils/project_context_store.py`:

```python
from database import get_db
from database.models import ProjectContext
import json

class ProjectContextStore:
    def __init__(self):
        self.db = get_db()
    
    async def save_context(self, context: ProjectContext) -> str:
        """Save project context to database."""
        context_dict = context.model_dump()
        
        project_id = await self.db.fetchval("""
            INSERT INTO project_contexts 
            (id, name, type, owner_id, codebase, dependencies, 
             environment_vars, deployment_config, test_coverage, 
             security_score, performance_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                codebase = EXCLUDED.codebase,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, 
            context_dict['id'],
            context_dict['name'],
            context_dict['type'],
            context_dict['owner_id'],
            json.dumps(context_dict['codebase']),
            context_dict['dependencies'],
            json.dumps(context_dict['environment_vars']),
            json.dumps(context_dict['deployment_config']),
            context_dict['test_coverage'],
            context_dict['security_score'],
            context_dict['performance_score']
        )
        
        return project_id
    
    async def load_context(self, project_id: str) -> ProjectContext:
        """Load project context from database."""
        row = await self.db.fetchrow("""
            SELECT * FROM project_contexts WHERE id = $1
        """, project_id)
        
        if not row:
            raise ValueError(f"Project {project_id} not found")
        
        return ProjectContext(
            id=str(row['id']),
            name=row['name'],
            type=row['type'],
            status=row['status'],
            owner_id=row['owner_id'],
            codebase=row['codebase'],
            dependencies=list(row['dependencies']),
            environment_vars=row['environment_vars'],
            deployment_config=row['deployment_config'],
            test_coverage=float(row['test_coverage']),
            security_score=float(row['security_score']),
            performance_score=float(row['performance_score']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            last_deployed_at=row['last_deployed_at']
        )
```

### 2. TemplateLibrary Integration

**Current:** `utils/template_library.py` uses JSON file storage
**Target:** Migrate to database backend

#### Steps:

1. Update `utils/template_library.py`:

```python
from database import get_db
from database.models import Template
import json

class TemplateLibrary:
    def __init__(self):
        self.db = get_db()
    
    async def save_template(self, template: Template) -> str:
        """Save template to database."""
        template_dict = template.model_dump()
        
        template_id = await self.db.fetchval("""
            INSERT INTO templates 
            (id, name, description, category, files, required_vars,
             optional_vars, tech_stack, estimated_setup_time, 
             complexity, tags)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
        """,
            template_dict['id'],
            template_dict['name'],
            template_dict['description'],
            template_dict['category'],
            json.dumps(template_dict['files']),
            template_dict['required_vars'],
            template_dict['optional_vars'],
            template_dict['tech_stack'],
            template_dict['estimated_setup_time'],
            template_dict['complexity'],
            template_dict['tags']
        )
        
        return template_id
    
    async def load_template(self, template_id: str) -> Template:
        """Load template from database."""
        row = await self.db.fetchrow("""
            SELECT * FROM templates WHERE id = $1
        """, template_id)
        
        if not row:
            raise ValueError(f"Template {template_id} not found")
        
        return Template(**dict(row))
    
    async def list_templates(self, category: str = None) -> list[Template]:
        """List all templates, optionally filtered by category."""
        if category:
            rows = await self.db.fetch("""
                SELECT * FROM templates WHERE category = $1
                ORDER BY name
            """, category)
        else:
            rows = await self.db.fetch("""
                SELECT * FROM templates ORDER BY name
            """)
        
        return [Template(**dict(row)) for row in rows]
```

### 3. PM Agent Integration

**Current:** PM Agent doesn't track modifications
**Target:** Add modification tracking

#### Steps:

1. Update `agents/pm_agent.py`:

```python
from database import get_db
from database.models import Modification
import json

class PlannerAgent:
    def __init__(self):
        # ... existing code ...
        self.db = get_db()
    
    async def track_modification(self, project_id: str, request: str, 
                                 requested_by: str, impact_analysis: dict,
                                 affected_files: list) -> str:
        """Track a modification request."""
        mod_id = await self.db.fetchval("""
            INSERT INTO modifications 
            (project_id, request, requested_by, impact_analysis, affected_files)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """,
            project_id,
            request,
            requested_by,
            json.dumps(impact_analysis),
            affected_files
        )
        
        return mod_id
    
    async def update_modification_status(self, mod_id: str, status: str,
                                        modified_files: dict = None,
                                        test_results: dict = None):
        """Update modification status and results."""
        await self.db.execute("""
            UPDATE modifications 
            SET status = $1, 
                applied_at = CASE WHEN $1 = 'applied' THEN CURRENT_TIMESTAMP ELSE applied_at END,
                modified_files = $2,
                test_results = $3
            WHERE id = $4
        """,
            status,
            json.dumps(modified_files) if modified_files else None,
            json.dumps(test_results) if test_results else None,
            mod_id
        )
```

### 4. Main Application Integration

Update `main.py` to initialize database:

```python
from database import init_db, close_db

async def startup():
    """Application startup."""
    # Initialize database connection pool
    await init_db()
    print("✓ Database initialized")

async def shutdown():
    """Application shutdown."""
    # Close database connection pool
    await close_db()
    print("✓ Database closed")

# In FastAPI
@app.on_event("startup")
async def on_startup():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    await shutdown()
```

### 5. API Routes Integration

Update `api/routes.py` to add database endpoints:

```python
from database import get_db
from database.models import ProjectContext, Modification, Template

@router.get("/api/projects")
async def list_projects(owner_id: str):
    """List all projects for a user."""
    db = get_db()
    projects = await db.fetch("""
        SELECT * FROM project_contexts 
        WHERE owner_id = $1 AND status = 'active'
        ORDER BY updated_at DESC
    """, owner_id)
    
    return [dict(p) for p in projects]

@router.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details."""
    db = get_db()
    project = await db.fetchrow("""
        SELECT * FROM project_contexts WHERE id = $1
    """, project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return dict(project)

@router.get("/api/projects/{project_id}/modifications")
async def list_modifications(project_id: str):
    """List all modifications for a project."""
    db = get_db()
    modifications = await db.fetch("""
        SELECT * FROM modifications 
        WHERE project_id = $1
        ORDER BY requested_at DESC
    """, project_id)
    
    return [dict(m) for m in modifications]

@router.get("/api/templates")
async def list_templates(category: str = None):
    """List all templates."""
    db = get_db()
    
    if category:
        templates = await db.fetch("""
            SELECT * FROM templates WHERE category = $1
            ORDER BY name
        """, category)
    else:
        templates = await db.fetch("""
            SELECT * FROM templates ORDER BY name
        """)
    
    return [dict(t) for t in templates]
```

## Migration Strategy

### Phase 1: Parallel Operation (Recommended)

1. Keep existing file-based storage
2. Add database storage alongside
3. Write to both systems
4. Read from database, fallback to files
5. Verify data consistency

### Phase 2: Database Primary

1. Make database the primary storage
2. Keep file-based as backup
3. Monitor for issues

### Phase 3: Database Only

1. Remove file-based storage code
2. Clean up old files
3. Full database operation

## Testing Integration

Add integration tests:

```python
# tests/test_database_integration.py
import pytest
from database import init_db, close_db, get_db
from utils.project_context_store import ProjectContextStore

@pytest.fixture
async def db():
    await init_db()
    yield get_db()
    await close_db()

async def test_project_context_store_integration(db):
    store = ProjectContextStore()
    
    # Create context
    context = ProjectContext(
        name="Test Project",
        type="api",
        owner_id="test_user"
    )
    
    # Save to database
    project_id = await store.save_context(context)
    
    # Load from database
    loaded = await store.load_context(project_id)
    
    assert loaded.name == "Test Project"
    assert loaded.type == "api"
```

## Rollback Plan

If issues occur:

1. **Immediate:** Switch back to file-based storage
2. **Data Recovery:** Export database to JSON files
3. **Investigation:** Review logs and errors
4. **Fix:** Address issues in development
5. **Retry:** Re-deploy with fixes

## Monitoring

Add monitoring for:

- Database connection pool usage
- Query performance
- Error rates
- Data consistency

```python
# Monitor connection pool
db = get_db()
print(f"Pool size: {db.pool.get_size()}")
print(f"Free connections: {db.pool.get_idle_size()}")
```

## Best Practices

1. **Always use async/await** for database operations
2. **Use transactions** for multi-step operations
3. **Handle errors gracefully** with try/except
4. **Log database operations** for debugging
5. **Monitor performance** regularly
6. **Backup regularly** before major changes

## Support

For integration issues:
1. Check database connection: `python database/migrate.py check`
2. Review logs for errors
3. Test with `python database/test_migrations.py`
4. Consult `database/README.md` for detailed documentation
