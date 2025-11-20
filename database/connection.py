"""
Database connection management using asyncpg for PostgreSQL.

Provides connection pooling and database session management.
"""

import os
import asyncpg
from typing import Optional
from contextlib import asynccontextmanager


class DatabaseManager:
    """
    Manages database connections with connection pooling.
    
    Uses asyncpg for high-performance PostgreSQL connectivity with
    connection pooling for efficient resource management.
    """
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://user:password@localhost:5432/agenticai'
        )
    
    async def initialize(self):
        """Initialize the connection pool."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=10,
                max_size=50,
                command_timeout=60,
                max_queries=50000,
                max_inactive_connection_lifetime=300
            )
    
    async def close(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.
        
        Usage:
            async with db_manager.acquire() as conn:
                result = await conn.fetch('SELECT * FROM table')
        """
        if self.pool is None:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def execute(self, query: str, *args):
        """Execute a query without returning results."""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Fetch multiple rows."""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Fetch a single row."""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Fetch a single value."""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager: The global database manager
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_db():
    """Initialize the database connection pool."""
    db = get_db()
    await db.initialize()


async def close_db():
    """Close the database connection pool."""
    db = get_db()
    await db.close()
