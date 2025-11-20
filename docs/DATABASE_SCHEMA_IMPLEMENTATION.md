# Database Schema Implementation

## Overview

This document describes the database schema implementation for the Software Developer Agentic AI production enhancement features (Task 8).

## Implementation Summary

### Components Created

1. **Database Module** (`database/`)
   - Connection management with asyncpg
   - Pydantic models for type safety
   - Migration system with Alembic
   - Comprehensive documentation

2. **Database Tables**
   - `project_contexts` - Project state storage
   - `modifications` - Modification tracking
   - `templates` - Template library

3. **Migration Scripts**
   - 001: Create project_contexts table
   - 002: Create modifications table
   - 003: Create templates table

4. **Utilities**
   - Migration runner (`migrate.py`)
   - Setup script (`setup.py`)
   - Test suite (`test_migrations.py`)

## Database Schema

### project_contexts Table

Stores complete project state across iterations.

**Columns:**
- `id` (UUID) - Primary key
- `name` (VARCHAR) - Project name
- `type` (VARCHAR) - Project type (api, web_app, etc.)
- `status` (VARCHAR) - Status (active, archived, deleted)
- `owner_id` (VARCHAR) - Owner identifier
- `codebase` (JSONB) - File storage
- `dependencies` (TEXT[]) - Dependency list
- `environment_vars` (JSONB) - Environment variables
- `deployment_config` (JSONB) - Deployment configuration
- `test_coverage` (NUMERIC) - Test coverage metric
- `security_score` (NUMERIC) - Security score metric
- `performance_score` (NUMERIC) - Performance score metric
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp
- `last_deployed_at` (TIMESTAMP) - Last deployment timestamp

**Indexes:**
- B-tree: owner_id, status, type, created_at, updated_at
- GIN: codebase, environment_vars
- Composite: (owner_id, status)


### modifications Table

Tracks project modification requests and results.

**Columns:**
- `id` (UUID) - Primary key
- `project_id` (UUID) - Foreign key to project_contexts
- `request` (TEXT) - Modification request
- `requested_by` (VARCHAR) - Requester identifier
- `requested_at` (TIMESTAMP) - Request timestamp
- `impact_analysis` (JSONB) - Impact analysis data
- `affected_files` (TEXT[]) - List of affected files
- `status` (VARCHAR) - Status (pending, approved, applied, failed, rejected)
- `applied_at` (TIMESTAMP) - Application timestamp
- `modified_files` (JSONB) - Modified file contents
- `test_results` (JSONB) - Test execution results

**Indexes:**
- B-tree: project_id, requested_by, status, requested_at
- GIN: impact_analysis, test_results
- Composite: (project_id, status)

**Constraints:**
- Foreign key to project_contexts with CASCADE delete

### templates Table

Stores reusable project templates.

**Columns:**
- `id` (UUID) - Primary key
- `name` (VARCHAR) - Template name
- `description` (TEXT) - Template description
- `category` (VARCHAR) - Category (api, web, mobile, data, microservice)
- `files` (JSONB) - Template file contents
- `required_vars` (TEXT[]) - Required variables
- `optional_vars` (TEXT[]) - Optional variables
- `tech_stack` (TEXT[]) - Technology stack
- `estimated_setup_time` (INTEGER) - Setup time in minutes
- `complexity` (VARCHAR) - Complexity (simple, medium, complex)
- `tags` (TEXT[]) - Tags for categorization
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp

**Indexes:**
- B-tree: category, complexity, created_at
- GIN: files, tech_stack, tags

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Database URL

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/agenticai"
```

### 3. Run Setup

```bash
python database/setup.py
```

### 4. Verify Installation

```bash
python database/test_migrations.py
```

## Usage Examples

### Initialize Database Connection

```python
from database import init_db, get_db

# Initialize connection pool
await init_db()

# Get database manager
db = get_db()
```

### Query Project Contexts

```python
# Get all active projects for a user
projects = await db.fetch(
    "SELECT * FROM project_contexts WHERE owner_id = $1 AND status = $2",
    user_id, 'active'
)

# Query JSONB data
projects_with_fastapi = await db.fetch(
    "SELECT * FROM project_contexts WHERE codebase @> $1",
    '{"requirements.txt": "fastapi"}'
)
```

### Track Modifications

```python
# Create modification request
mod_id = await db.fetchval("""
    INSERT INTO modifications (project_id, request, requested_by, affected_files)
    VALUES ($1, $2, $3, $4)
    RETURNING id
""", project_id, "Add authentication", user_id, ['main.py', 'auth.py'])

# Update modification status
await db.execute("""
    UPDATE modifications SET status = $1, applied_at = CURRENT_TIMESTAMP
    WHERE id = $2
""", 'applied', mod_id)
```

### Work with Templates

```python
# Get templates by category
api_templates = await db.fetch(
    "SELECT * FROM templates WHERE category = $1",
    'api'
)

# Search by tech stack
fastapi_templates = await db.fetch(
    "SELECT * FROM templates WHERE 'FastAPI' = ANY(tech_stack)"
)
```

## Migration Management

### Check Current Version

```bash
python database/migrate.py current
```

### Upgrade to Latest

```bash
python database/migrate.py upgrade
```

### Downgrade

```bash
python database/migrate.py downgrade 001
```

### View History

```bash
python database/migrate.py history
```

## Testing

Run the comprehensive test suite:

```bash
python database/test_migrations.py
```

Tests include:
- Connection verification
- Table operations (CRUD)
- JSONB queries
- Array queries
- Index verification
- Trigger functionality
- Cascade deletes

## Performance Considerations

### Connection Pooling

- Min connections: 10
- Max connections: 50
- Command timeout: 60s
- Automatic connection recycling

### Indexing Strategy

1. **B-tree indexes** for equality and range queries
2. **GIN indexes** for JSONB and array containment queries
3. **Composite indexes** for common multi-column queries

### Query Optimization

- Use parameterized queries
- Leverage JSONB operators (@>, ?, etc.)
- Use array operators (ANY, ALL)
- Monitor query performance with EXPLAIN ANALYZE

## Security

### Best Practices

1. **Never hardcode credentials** - Use environment variables
2. **Use parameterized queries** - Prevent SQL injection
3. **Limit permissions** - Grant only necessary privileges
4. **Enable SSL** - For production connections
5. **Regular backups** - Automated backup strategy

### Connection Security

```python
# Use SSL in production
DATABASE_URL = "postgresql://user:pass@host:5432/db?sslmode=require"
```

## Troubleshooting

### Connection Issues

```bash
# Check PostgreSQL is running
pg_isready

# Test connection
python database/migrate.py check
```

### Migration Issues

```bash
# Check current state
python database/migrate.py current

# View history
python database/migrate.py history

# Manually stamp if needed
python database/migrate.py stamp 003
```

## Requirements Met

This implementation satisfies all requirements from task 8:

✓ 8.1 - Created project_contexts table with all required columns and indexes
✓ 8.2 - Created modifications table with impact analysis and test results
✓ 8.3 - Created templates table with flexible JSONB storage
✓ 8.4 - Implemented Alembic migrations with comprehensive testing

## Next Steps

1. Integrate with existing ProjectContextStore
2. Update TemplateLibrary to use database
3. Implement modification tracking in PM Agent
4. Add database connection to main application
5. Set up production database with proper backups

## References

- Requirements: 1.1, 2.1, 12.1
- Design Document: `.kiro/specs/production-enhancement/design.md`
- Database README: `database/README.md`
