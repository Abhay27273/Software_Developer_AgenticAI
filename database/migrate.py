"""
Database migration runner script.

Provides utilities to run migrations, check migration status, and manage
the database schema.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic.config import Config
from alembic import command
from database.connection import get_db, init_db, close_db


def get_alembic_config():
    """Get Alembic configuration."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    alembic_ini = project_root / "alembic.ini"
    
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")
    
    config = Config(str(alembic_ini))
    
    # Override database URL from environment if present
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        config.set_main_option('sqlalchemy.url', database_url)
    
    return config


def upgrade(revision='head'):
    """
    Upgrade database to a specific revision.
    
    Args:
        revision: Target revision (default: 'head' for latest)
    """
    print(f"Upgrading database to revision: {revision}")
    config = get_alembic_config()
    command.upgrade(config, revision)
    print("Database upgrade completed successfully!")


def downgrade(revision):
    """
    Downgrade database to a specific revision.
    
    Args:
        revision: Target revision
    """
    print(f"Downgrading database to revision: {revision}")
    config = get_alembic_config()
    command.downgrade(config, revision)
    print("Database downgrade completed successfully!")


def current():
    """Show current database revision."""
    print("Current database revision:")
    config = get_alembic_config()
    command.current(config)


def history():
    """Show migration history."""
    print("Migration history:")
    config = get_alembic_config()
    command.history(config)


def stamp(revision):
    """
    Stamp database with a specific revision without running migrations.
    
    Args:
        revision: Target revision to stamp
    """
    print(f"Stamping database with revision: {revision}")
    config = get_alembic_config()
    command.stamp(config, revision)
    print("Database stamped successfully!")


async def init_database():
    """
    Initialize database with all tables.
    
    This runs all migrations to set up the database schema.
    """
    print("Initializing database...")
    
    # Initialize connection pool
    await init_db()
    
    # Run migrations
    upgrade('head')
    
    print("Database initialized successfully!")
    
    # Close connection pool
    await close_db()


async def reset_database():
    """
    Reset database by downgrading to base and upgrading to head.
    
    WARNING: This will drop all tables and data!
    """
    print("WARNING: This will drop all tables and data!")
    response = input("Are you sure you want to continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Database reset cancelled.")
        return
    
    print("Resetting database...")
    
    # Downgrade to base
    downgrade('base')
    
    # Upgrade to head
    upgrade('head')
    
    print("Database reset completed!")


async def check_connection():
    """Check database connection."""
    print("Checking database connection...")
    
    try:
        db = get_db()
        await db.initialize()
        
        # Try a simple query
        result = await db.fetchval('SELECT 1')
        
        if result == 1:
            print("✓ Database connection successful!")
            
            # Get PostgreSQL version
            version = await db.fetchval('SELECT version()')
            print(f"✓ PostgreSQL version: {version.split(',')[0]}")
            
            # Check if uuid-ossp extension is available
            has_uuid = await db.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp')"
            )
            if has_uuid:
                print("✓ uuid-ossp extension is installed")
            else:
                print("⚠ uuid-ossp extension is not installed (will be installed during migration)")
        
        await db.close()
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("""
Database Migration Tool

Usage:
    python database/migrate.py <command> [args]

Commands:
    upgrade [revision]  - Upgrade to a revision (default: head)
    downgrade <revision> - Downgrade to a revision
    current             - Show current revision
    history             - Show migration history
    stamp <revision>    - Stamp database with revision
    init                - Initialize database with all tables
    reset               - Reset database (WARNING: drops all data)
    check               - Check database connection

Examples:
    python database/migrate.py upgrade
    python database/migrate.py upgrade 001
    python database/migrate.py downgrade 001
    python database/migrate.py current
    python database/migrate.py init
    python database/migrate.py check
        """)
        sys.exit(1)
    
    command_name = sys.argv[1]
    
    if command_name == 'upgrade':
        revision = sys.argv[2] if len(sys.argv) > 2 else 'head'
        upgrade(revision)
    
    elif command_name == 'downgrade':
        if len(sys.argv) < 3:
            print("Error: downgrade requires a revision argument")
            sys.exit(1)
        downgrade(sys.argv[2])
    
    elif command_name == 'current':
        current()
    
    elif command_name == 'history':
        history()
    
    elif command_name == 'stamp':
        if len(sys.argv) < 3:
            print("Error: stamp requires a revision argument")
            sys.exit(1)
        stamp(sys.argv[2])
    
    elif command_name == 'init':
        asyncio.run(init_database())
    
    elif command_name == 'reset':
        asyncio.run(reset_database())
    
    elif command_name == 'check':
        asyncio.run(check_connection())
    
    else:
        print(f"Error: Unknown command '{command_name}'")
        sys.exit(1)


if __name__ == '__main__':
    main()
