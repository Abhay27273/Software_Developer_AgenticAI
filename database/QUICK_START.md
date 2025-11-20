# Database Quick Start Guide

## Prerequisites

- PostgreSQL 12+ installed and running
- Python 3.8+ with pip

## 5-Minute Setup

### 1. Install Dependencies

```bash
pip install asyncpg alembic sqlalchemy
```

Or install all project dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Database

Set your database URL (choose one method):

**Option A: Environment Variable**
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/agenticai"
```

**Option B: .env File**
```
DATABASE_URL=postgresql://user:password@localhost:5432/agenticai
```

**Option C: Use Default**
The system will use `postgresql://user:password@localhost:5432/agenticai` if not set.

### 3. Run Setup

```bash
python database/setup.py
```

This will:
- Check your database connection
- Run all migrations
- Create all tables
- Verify the setup

### 4. Verify (Optional)

```bash
python database/test_migrations.py
```

## Common Commands

### Check Connection
```bash
python database/migrate.py check
```

### View Current Version
```bash
python database/migrate.py current
```

### Upgrade Database
```bash
python database/migrate.py upgrade
```

### View Migration History
```bash
python database/migrate.py history
```

## Using in Code

```python
from database import init_db, get_db

# Initialize (do this once at startup)
await init_db()

# Get database instance
db = get_db()

# Query data
projects = await db.fetch(
    "SELECT * FROM project_contexts WHERE owner_id = $1",
    user_id
)

# Insert data
project_id = await db.fetchval("""
    INSERT INTO project_contexts (name, type, owner_id)
    VALUES ($1, $2, $3)
    RETURNING id
""", "My Project", "api", "user123")

# Update data
await db.execute("""
    UPDATE project_contexts 
    SET test_coverage = $1 
    WHERE id = $2
""", 0.85, project_id)
```

## Troubleshooting

### "Connection refused"
- Check PostgreSQL is running: `pg_isready`
- Verify DATABASE_URL is correct
- Check firewall settings

### "Database does not exist"
Create the database:
```bash
createdb agenticai
```

### "Permission denied"
Grant permissions:
```sql
GRANT ALL PRIVILEGES ON DATABASE agenticai TO your_user;
```

## Next Steps

- Read full documentation: `database/README.md`
- View implementation details: `docs/DATABASE_SCHEMA_IMPLEMENTATION.md`
- Explore schema: `database/schema.sql`

## Support

For issues or questions:
1. Check `database/README.md` for detailed documentation
2. Run tests: `python database/test_migrations.py`
3. Verify connection: `python database/migrate.py check`
