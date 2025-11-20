# Database Module

This module provides database connectivity, models, and migrations for the Software Developer Agentic AI production enhancement features.

## Overview

The database module uses:
- **PostgreSQL** as the database engine
- **asyncpg** for high-performance async database connectivity
- **Alembic** for database migrations
- **JSONB** columns for flexible schema storage

## Database Schema

### Tables

1. **project_contexts** - Stores project state across iterations
   - Project metadata (name, type, status, owner)
   - Codebase (JSONB storage for files)
   - Configuration (environment vars, deployment config)
   - Metrics (test coverage, security score, performance score)

2. **modifications** - Tracks project modification requests
   - Modification requests and analysis
   - Impact analysis and affected files
   - Execution status and results
   - Test results

3. **templates** - Stores reusable project templates
   - Template metadata and content
   - Required and optional variables
   - Tech stack and complexity information

## Setup

### Prerequisites

1. PostgreSQL 12 or higher installed
2. Python dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

### Environment Variables

Set the `DATABASE_URL` environment variable:

```bash
# Development
export DATABASE_URL="postgresql://user:password@localhost:5432/agenticai"

# Production
export DATABASE_URL="postgresql://user:password@prod-host:5432/agenticai"
```

Or add to `.env` file:
```
DATABASE_URL=postgresql://user:password@localhost:5432/agenticai
```

### Initialize Database

Run migrations to create all tables:

```bash
python database/migrate.py init
```

This will:
1. Create the database connection pool
2. Run all migrations to create tables
3. Set up indexes and constraints

## Usage

### Running Migrations

**Upgrade to latest version:**
```bash
python database/migrate.py upgrade
```

**Upgrade to specific version:**
```bash
python database/migrate.py upgrade 001
```

**Downgrade to specific version:**
```bash
python database/migrate.py downgrade 001
```

**Check current version:**
```bash
python database/migrate.py current
```

**View migration history:**
```bash
python database/migrate.py history
```

**Check database connection:**
```bash
python database/migrate.py check
```

### Using in Code

**Initialize database connection:**
```python
from database import get_db, init_db

# Initialize connection pool
await init_db()

# Get database manager
db = get_db()
```

**Execute queries:**
```python
# Fetch multiple rows
projects = await db.fetch(
    "SELECT * FROM project_contexts WHERE owner_id = $1",
    user_id
)

# Fetch single row
project = await db.fetchrow(
    "SELECT * FROM project_contexts WHERE id = $1",
    project_id
)

# Fetch single value
count = await db.fetchval(
    "SELECT COUNT(*) FROM project_contexts WHERE status = $1",
    'active'
)

# Execute without result
await db.execute(
    "UPDATE project_contexts SET status = $1 WHERE id = $2",
    'archived', project_id
)
```

**Using connection context manager:**
```python
async with db.acquire() as conn:
    # Use connection for multiple operations
    await conn.execute("BEGIN")
    try:
        await conn.execute("INSERT INTO ...")
        await conn.execute("UPDATE ...")
        await conn.execute("COMMIT")
    except:
        await conn.execute("ROLLBACK")
        raise
```

### Working with Models

```python
from database.models import ProjectContext, Modification, Template
from datetime import datetime

# Create a project context
project = ProjectContext(
    name="My API",
    type="api",
    owner_id="user123",
    codebase={
        "main.py": "from fastapi import FastAPI...",
        "models.py": "from sqlalchemy import..."
    },
    environment_vars={
        "DATABASE_URL": "postgresql://localhost/db"
    },
    test_coverage=0.85
)

# Convert to dict for database insertion
project_dict = project.model_dump()
```

## Migration Files

Migration files are located in `database/migrations/versions/`:

- `001_create_project_contexts_table.py` - Creates project_contexts table
- `002_create_modifications_table.py` - Creates modifications table
- `003_create_templates_table.py` - Creates templates table

Each migration includes:
- `upgrade()` - Apply the migration
- `downgrade()` - Revert the migration

## Indexes

The schema includes several types of indexes for performance:

1. **B-tree indexes** - For standard column queries (owner_id, status, etc.)
2. **GIN indexes** - For JSONB and array columns (codebase, tags, etc.)
3. **Composite indexes** - For common multi-column queries

## Connection Pooling

The database manager uses connection pooling for efficient resource management:

- **Min connections:** 10
- **Max connections:** 50
- **Command timeout:** 60 seconds
- **Max queries per connection:** 50,000
- **Max inactive connection lifetime:** 300 seconds

## Best Practices

1. **Always use parameterized queries** to prevent SQL injection:
   ```python
   # Good
   await db.fetch("SELECT * FROM projects WHERE id = $1", project_id)
   
   # Bad
   await db.fetch(f"SELECT * FROM projects WHERE id = '{project_id}'")
   ```

2. **Use transactions for multiple operations:**
   ```python
   async with db.acquire() as conn:
       async with conn.transaction():
           await conn.execute("INSERT ...")
           await conn.execute("UPDATE ...")
   ```

3. **Close connections when done:**
   ```python
   from database import close_db
   
   # At application shutdown
   await close_db()
   ```

4. **Use JSONB for flexible data:**
   - Store complex nested structures
   - Query with PostgreSQL JSONB operators
   - Index with GIN for performance

## Troubleshooting

### Connection Issues

If you get connection errors:

1. Check PostgreSQL is running:
   ```bash
   pg_isready
   ```

2. Verify DATABASE_URL is correct:
   ```bash
   echo $DATABASE_URL
   ```

3. Test connection:
   ```bash
   python database/migrate.py check
   ```

### Migration Issues

If migrations fail:

1. Check current migration status:
   ```bash
   python database/migrate.py current
   ```

2. View migration history:
   ```bash
   python database/migrate.py history
   ```

3. Manually stamp database if needed:
   ```bash
   python database/migrate.py stamp <revision>
   ```

### Performance Issues

If queries are slow:

1. Check if indexes are being used:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM project_contexts WHERE owner_id = 'user123';
   ```

2. Monitor connection pool:
   ```python
   print(f"Pool size: {db.pool.get_size()}")
   print(f"Free connections: {db.pool.get_idle_size()}")
   ```

3. Consider adding more indexes for specific queries

## Development

### Creating New Migrations

To create a new migration:

1. Create a new file in `database/migrations/versions/`
2. Follow the naming convention: `00X_description.py`
3. Implement `upgrade()` and `downgrade()` functions
4. Update the revision chain

Example:
```python
"""Add new column

Revision ID: 004
Revises: 003
"""

def upgrade():
    op.add_column('project_contexts', 
                  sa.Column('new_field', sa.String(100)))

def downgrade():
    op.drop_column('project_contexts', 'new_field')
```

### Testing Migrations

Test migrations in development:

```bash
# Apply migration
python database/migrate.py upgrade

# Test rollback
python database/migrate.py downgrade <previous_revision>

# Re-apply
python database/migrate.py upgrade
```

## Production Deployment

For production deployment:

1. **Backup database** before running migrations
2. **Test migrations** in staging environment first
3. **Run migrations** during maintenance window if possible
4. **Monitor** application after migration

```bash
# Backup
pg_dump $DATABASE_URL > backup.sql

# Run migration
python database/migrate.py upgrade

# Verify
python database/migrate.py current
```

## Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
