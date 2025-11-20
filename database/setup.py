"""
Database setup script.

Helps users set up the database for the first time.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_environment():
    """Check if environment is properly configured."""
    print("Checking environment configuration...")
    
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("\n⚠ DATABASE_URL environment variable is not set.")
        print("\nPlease set DATABASE_URL in one of the following ways:")
        print("\n1. Export environment variable:")
        print("   export DATABASE_URL='postgresql://user:password@localhost:5432/agenticai'")
        print("\n2. Add to .env file:")
        print("   DATABASE_URL=postgresql://user:password@localhost:5432/agenticai")
        print("\n3. Use default (not recommended for production):")
        print("   The system will use: postgresql://user:password@localhost:5432/agenticai")
        
        response = input("\nContinue with default? (yes/no): ")
        if response.lower() != 'yes':
            print("Setup cancelled.")
            sys.exit(1)
        
        database_url = 'postgresql://user:password@localhost:5432/agenticai'
        os.environ['DATABASE_URL'] = database_url
    
    print(f"✓ Using database: {database_url.split('@')[1] if '@' in database_url else database_url}")
    return database_url


async def check_database_connection():
    """Check if we can connect to the database."""
    print("\nChecking database connection...")
    
    from database.connection import get_db
    
    try:
        db = get_db()
        await db.initialize()
        
        result = await db.fetchval('SELECT 1')
        
        if result == 1:
            print("✓ Database connection successful")
            
            # Get PostgreSQL version
            version = await db.fetchval('SELECT version()')
            print(f"✓ PostgreSQL version: {version.split(',')[0]}")
            
            await db.close()
            return True
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("\nPlease ensure:")
        print("1. PostgreSQL is installed and running")
        print("2. Database exists (or will be created)")
        print("3. User has proper permissions")
        print("4. DATABASE_URL is correct")
        return False


def run_migrations():
    """Run database migrations."""
    print("\nRunning database migrations...")
    
    from database.migrate import upgrade
    
    try:
        upgrade('head')
        print("✓ Migrations completed successfully")
        return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False


async def verify_tables():
    """Verify that all tables were created."""
    print("\nVerifying database tables...")
    
    from database.connection import get_db
    
    try:
        db = get_db()
        await db.initialize()
        
        # Check for tables
        tables = await db.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        
        table_names = [t['tablename'] for t in tables]
        
        required_tables = ['project_contexts', 'modifications', 'templates']
        
        all_present = True
        for table in required_tables:
            if table in table_names:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' missing")
                all_present = False
        
        await db.close()
        return all_present
        
    except Exception as e:
        print(f"✗ Table verification failed: {e}")
        return False


async def main():
    """Main setup function."""
    print("=" * 60)
    print("Database Setup for Software Developer Agentic AI")
    print("=" * 60)
    
    # Step 1: Check environment
    database_url = check_environment()
    
    # Step 2: Check database connection
    if not await check_database_connection():
        print("\n❌ Setup failed: Cannot connect to database")
        sys.exit(1)
    
    # Step 3: Run migrations
    if not run_migrations():
        print("\n❌ Setup failed: Migration error")
        sys.exit(1)
    
    # Step 4: Verify tables
    if not await verify_tables():
        print("\n❌ Setup failed: Table verification error")
        sys.exit(1)
    
    # Success!
    print("\n" + "=" * 60)
    print("✓ Database setup completed successfully!")
    print("=" * 60)
    print("\nYou can now:")
    print("1. Start using the database in your application")
    print("2. Run tests: python database/test_migrations.py")
    print("3. Check status: python database/migrate.py current")
    print("\nFor more information, see database/README.md")


if __name__ == '__main__':
    asyncio.run(main())
