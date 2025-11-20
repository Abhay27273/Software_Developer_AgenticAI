"""
Test script for database migrations.

This script tests that migrations can be applied and rolled back successfully.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_db, init_db, close_db
from database.models import ProjectContext, Modification, Template


async def test_connection():
    """Test database connection."""
    print("Testing database connection...")
    
    try:
        db = get_db()
        await db.initialize()
        
        result = await db.fetchval('SELECT 1')
        assert result == 1, "Connection test failed"
        
        print("✓ Database connection successful")
        return True
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


async def test_project_contexts_table():
    """Test project_contexts table operations."""
    print("\nTesting project_contexts table...")
    
    db = get_db()
    
    try:
        # Test insert
        project_id = await db.fetchval("""
            INSERT INTO project_contexts (name, type, owner_id, codebase, environment_vars)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, "Test Project", "api", "test_user", 
            '{"main.py": "print(\'hello\')"}', 
            '{"API_KEY": "test"}')
        
        print(f"✓ Inserted project with id: {project_id}")
        
        # Test select
        project = await db.fetchrow("""
            SELECT * FROM project_contexts WHERE id = $1
        """, project_id)
        
        assert project['name'] == "Test Project"
        assert project['type'] == "api"
        assert project['owner_id'] == "test_user"
        print("✓ Selected project successfully")
        
        # Test update
        await db.execute("""
            UPDATE project_contexts 
            SET test_coverage = $1, security_score = $2
            WHERE id = $3
        """, 0.85, 0.92, project_id)
        
        updated = await db.fetchrow("""
            SELECT test_coverage, security_score FROM project_contexts WHERE id = $1
        """, project_id)
        
        assert float(updated['test_coverage']) == 0.85
        assert float(updated['security_score']) == 0.92
        print("✓ Updated project successfully")
        
        # Test JSONB query
        projects_with_main = await db.fetch("""
            SELECT id, name FROM project_contexts 
            WHERE codebase ? 'main.py'
        """)
        
        assert len(projects_with_main) > 0
        print("✓ JSONB query successful")
        
        # Test delete
        await db.execute("""
            DELETE FROM project_contexts WHERE id = $1
        """, project_id)
        
        deleted = await db.fetchrow("""
            SELECT * FROM project_contexts WHERE id = $1
        """, project_id)
        
        assert deleted is None
        print("✓ Deleted project successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ project_contexts table test failed: {e}")
        return False


async def test_modifications_table():
    """Test modifications table operations."""
    print("\nTesting modifications table...")
    
    db = get_db()
    
    try:
        # First create a project
        project_id = await db.fetchval("""
            INSERT INTO project_contexts (name, type, owner_id)
            VALUES ($1, $2, $3)
            RETURNING id
        """, "Test Project for Mods", "api", "test_user")
        
        # Test insert modification
        mod_id = await db.fetchval("""
            INSERT INTO modifications (project_id, request, requested_by, impact_analysis, affected_files)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, project_id, "Add authentication", "test_user",
            '{"risk_level": "medium", "estimated_time": "2 hours"}',
            ['main.py', 'auth.py'])
        
        print(f"✓ Inserted modification with id: {mod_id}")
        
        # Test select
        mod = await db.fetchrow("""
            SELECT * FROM modifications WHERE id = $1
        """, mod_id)
        
        assert mod['request'] == "Add authentication"
        assert mod['status'] == "pending"
        print("✓ Selected modification successfully")
        
        # Test update status
        await db.execute("""
            UPDATE modifications 
            SET status = $1, modified_files = $2
            WHERE id = $3
        """, "applied", '{"auth.py": "def authenticate(): pass"}', mod_id)
        
        updated = await db.fetchrow("""
            SELECT status FROM modifications WHERE id = $1
        """, mod_id)
        
        assert updated['status'] == "applied"
        print("✓ Updated modification successfully")
        
        # Test cascade delete
        await db.execute("""
            DELETE FROM project_contexts WHERE id = $1
        """, project_id)
        
        mod_after_delete = await db.fetchrow("""
            SELECT * FROM modifications WHERE id = $1
        """, mod_id)
        
        assert mod_after_delete is None
        print("✓ Cascade delete successful")
        
        return True
        
    except Exception as e:
        print(f"✗ modifications table test failed: {e}")
        return False


async def test_templates_table():
    """Test templates table operations."""
    print("\nTesting templates table...")
    
    db = get_db()
    
    try:
        # Test insert
        template_id = await db.fetchval("""
            INSERT INTO templates (name, description, category, files, required_vars, tech_stack, tags)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, "REST API Template", "A simple REST API template", "api",
            '{"main.py": "from fastapi import FastAPI"}',
            ['project_name', 'db_name'],
            ['FastAPI', 'PostgreSQL'],
            ['api', 'rest'])
        
        print(f"✓ Inserted template with id: {template_id}")
        
        # Test select
        template = await db.fetchrow("""
            SELECT * FROM templates WHERE id = $1
        """, template_id)
        
        assert template['name'] == "REST API Template"
        assert template['category'] == "api"
        print("✓ Selected template successfully")
        
        # Test array query
        templates_with_fastapi = await db.fetch("""
            SELECT id, name FROM templates 
            WHERE 'FastAPI' = ANY(tech_stack)
        """)
        
        assert len(templates_with_fastapi) > 0
        print("✓ Array query successful")
        
        # Test tag query
        templates_with_tag = await db.fetch("""
            SELECT id, name FROM templates 
            WHERE 'api' = ANY(tags)
        """)
        
        assert len(templates_with_tag) > 0
        print("✓ Tag query successful")
        
        # Test delete
        await db.execute("""
            DELETE FROM templates WHERE id = $1
        """, template_id)
        
        deleted = await db.fetchrow("""
            SELECT * FROM templates WHERE id = $1
        """, template_id)
        
        assert deleted is None
        print("✓ Deleted template successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ templates table test failed: {e}")
        return False


async def test_indexes():
    """Test that indexes are created."""
    print("\nTesting indexes...")
    
    db = get_db()
    
    try:
        # Get all indexes
        indexes = await db.fetch("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)
        
        index_names = [idx['indexname'] for idx in indexes]
        
        # Check for key indexes
        required_indexes = [
            'idx_project_contexts_owner_id',
            'idx_project_contexts_codebase',
            'idx_modifications_project_id',
            'idx_modifications_impact_analysis',
            'idx_templates_category',
            'idx_templates_tech_stack'
        ]
        
        for idx_name in required_indexes:
            if idx_name in index_names:
                print(f"✓ Index {idx_name} exists")
            else:
                print(f"✗ Index {idx_name} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Index test failed: {e}")
        return False


async def test_triggers():
    """Test that triggers are working."""
    print("\nTesting triggers...")
    
    db = get_db()
    
    try:
        # Create a project
        project_id = await db.fetchval("""
            INSERT INTO project_contexts (name, type, owner_id)
            VALUES ($1, $2, $3)
            RETURNING id
        """, "Trigger Test", "api", "test_user")
        
        # Get initial timestamps
        initial = await db.fetchrow("""
            SELECT created_at, updated_at FROM project_contexts WHERE id = $1
        """, project_id)
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Update the project
        await db.execute("""
            UPDATE project_contexts SET name = $1 WHERE id = $2
        """, "Trigger Test Updated", project_id)
        
        # Get updated timestamps
        updated = await db.fetchrow("""
            SELECT created_at, updated_at FROM project_contexts WHERE id = $1
        """, project_id)
        
        # Check that updated_at changed but created_at didn't
        assert updated['created_at'] == initial['created_at']
        assert updated['updated_at'] > initial['updated_at']
        
        print("✓ Trigger updated updated_at timestamp")
        
        # Cleanup
        await db.execute("""
            DELETE FROM project_contexts WHERE id = $1
        """, project_id)
        
        return True
        
    except Exception as e:
        print(f"✗ Trigger test failed: {e}")
        return False


async def run_all_tests():
    """Run all migration tests."""
    print("=" * 60)
    print("Database Migration Tests")
    print("=" * 60)
    
    # Check if DATABASE_URL is set
    if not os.getenv('DATABASE_URL'):
        print("\n⚠ WARNING: DATABASE_URL not set. Using default.")
        print("Set DATABASE_URL environment variable for custom database.")
    
    # Initialize database
    await init_db()
    
    results = []
    
    # Run tests
    results.append(("Connection", await test_connection()))
    results.append(("project_contexts table", await test_project_contexts_table()))
    results.append(("modifications table", await test_modifications_table()))
    results.append(("templates table", await test_templates_table()))
    results.append(("Indexes", await test_indexes()))
    results.append(("Triggers", await test_triggers()))
    
    # Close database
    await close_db()
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
