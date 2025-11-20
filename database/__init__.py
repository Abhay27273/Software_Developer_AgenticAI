"""
Database module for Software Developer Agentic AI.

This module provides database connectivity, models, and migrations
for the production enhancement features.
"""

from .connection import DatabaseManager, get_db
from .models import ProjectContext, Modification, Template

__all__ = [
    'DatabaseManager',
    'get_db',
    'ProjectContext',
    'Modification',
    'Template'
]
