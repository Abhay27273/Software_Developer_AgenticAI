"""
Unit tests for Phase 2.1: Dependency Analyzer.

Tests cover:
- Import parsing (Python, JS, TS)
- Dependency graph construction
- Topological sorting
- Circular dependency detection and breaking
- Critical path analysis
- Batch grouping for parallel execution
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from utils.dependency_analyzer import (
    DependencyAnalyzer, FileDependency, DependencyBatch,
    analyze_plan_dependencies
)


# ============================================================================
# Import Parsing Tests
# ============================================================================

class TestImportParsing:
    """Test import statement parsing for different languages."""
    
    def test_python_import_parsing(self):
        """Test parsing Python import statements."""
        analyzer = DependencyAnalyzer()
        
        content = """
import os
import sys
from pathlib import Path
from utils.cache import ResultCache
from models import User, Task
"""
        
        imports = analyzer.parse_imports_from_content(content, "python")
        
        assert 'os' in imports
        assert 'sys' in imports
        assert 'pathlib' in imports
        assert 'utils.cache' in imports
        assert 'models' in imports
    
    def test_javascript_import_parsing(self):
        """Test parsing JavaScript import statements."""
        analyzer = DependencyAnalyzer()
        
        content = """
import React from 'react';
import { useState } from 'react';
import './styles.css';
const axios = require('axios');
"""
        
        imports = analyzer.parse_imports_from_content(content, "javascript")
        
        assert 'react' in imports
        assert 'styles.css' in imports or 'styles' in imports
        assert 'axios' in imports
    
    def test_typescript_import_parsing(self):
        """Test parsing TypeScript import statements."""
        analyzer = DependencyAnalyzer()
        
        content = """
import type { User } from './types';
import { ApiClient } from '../api/client';
import * as utils from './utils';
"""
        
        imports = analyzer.parse_imports_from_content(content, "typescript")
        
        assert 'types' in imports
        assert 'api/client' in imports or 'client' in imports
        assert 'utils' in imports


# ============================================================================
# Dependency Graph Tests
# ============================================================================

class TestDependencyGraph:
    """Test dependency graph construction."""
    
    def test_simple_dependency_chain(self):
        """Test building a simple linear dependency chain."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'Config',
                'files_to_generate': ['config.py'],
                'code': 'import os'
            },
            {
                'title': 'Models',
                'files_to_generate': ['models.py'],
                'code': 'from config import settings'
            },
            {
                'title': 'Main',
                'files_to_generate': ['main.py'],
                'code': 'from models import User'
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        
        assert len(analyzer.files) == 3
        assert 'config.py' in analyzer.files['models.py'].depends_on
        assert 'models.py' in analyzer.files['main.py'].depends_on
    
    def test_parallel_dependencies(self):
        """Test multiple files with no dependencies (can run in parallel)."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {'title': 'File1', 'files_to_generate': ['file1.py'], 'code': ''},
            {'title': 'File2', 'files_to_generate': ['file2.py'], 'code': ''},
            {'title': 'File3', 'files_to_generate': ['file3.py'], 'code': ''}
        ]
        
        analyzer.build_dependency_graph(tasks)
        
        # All files should have no dependencies
        for file_dep in analyzer.files.values():
            assert len(file_dep.depends_on) == 0
    
    def test_shared_dependency(self):
        """Test multiple files depending on the same file."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'Utils',
                'files_to_generate': ['utils.py'],
                'code': ''
            },
            {
                'title': 'Module1',
                'files_to_generate': ['module1.py'],
                'code': 'from utils import helper'
            },
            {
                'title': 'Module2',
                'files_to_generate': ['module2.py'],
                'code': 'from utils import helper'
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        
        # utils.py should be required by both modules
        assert len(analyzer.files['utils.py'].required_by) == 2
        assert 'module1.py' in analyzer.files['utils.py'].required_by
        assert 'module2.py' in analyzer.files['utils.py'].required_by


# ============================================================================
# Topological Sort Tests
# ============================================================================

class TestTopologicalSort:
    """Test topological sorting for build order."""
    
    def test_simple_linear_sort(self):
        """Test sorting a simple linear dependency chain."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'Main',
                'files_to_generate': ['main.py'],
                'code': 'from app import create_app'
            },
            {
                'title': 'App',
                'files_to_generate': ['app.py'],
                'code': 'from config import settings'
            },
            {
                'title': 'Config',
                'files_to_generate': ['config.py'],
                'code': ''
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        batches = analyzer.topological_sort()
        
        # Should have 3 batches (linear chain)
        assert len(batches) == 3
        
        # First batch should be config.py
        assert batches[0].files[0].file_path == 'config.py'
        
        # Second batch should be app.py
        assert batches[1].files[0].file_path == 'app.py'
        
        # Third batch should be main.py
        assert batches[2].files[0].file_path == 'main.py'
    
    def test_parallel_batch_grouping(self):
        """Test grouping independent files into same batch."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {'title': 'File1', 'files_to_generate': ['file1.py'], 'code': ''},
            {'title': 'File2', 'files_to_generate': ['file2.py'], 'code': ''},
            {'title': 'File3', 'files_to_generate': ['file3.py'], 'code': ''}
        ]
        
        analyzer.build_dependency_graph(tasks)
        batches = analyzer.topological_sort()
        
        # All files should be in one batch (parallel)
        assert len(batches) == 1
        assert len(batches[0].files) == 3
    
    def test_diamond_dependency(self):
        """Test diamond-shaped dependency structure."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'Base',
                'files_to_generate': ['base.py'],
                'code': ''
            },
            {
                'title': 'Left',
                'files_to_generate': ['left.py'],
                'code': 'from base import Base'
            },
            {
                'title': 'Right',
                'files_to_generate': ['right.py'],
                'code': 'from base import Base'
            },
            {
                'title': 'Top',
                'files_to_generate': ['top.py'],
                'code': 'from left import Left\nfrom right import Right'
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        batches = analyzer.topological_sort()
        
        # Should have 3 batches
        assert len(batches) == 3
        
        # Batch 0: base.py
        assert len(batches[0].files) == 1
        assert batches[0].files[0].file_path == 'base.py'
        
        # Batch 1: left.py and right.py (parallel)
        assert len(batches[1].files) == 2
        batch1_files = {f.file_path for f in batches[1].files}
        assert 'left.py' in batch1_files
        assert 'right.py' in batch1_files
        
        # Batch 2: top.py
        assert len(batches[2].files) == 1
        assert batches[2].files[0].file_path == 'top.py'


# ============================================================================
# Circular Dependency Tests
# ============================================================================

class TestCircularDependencies:
    """Test circular dependency detection and breaking."""
    
    def test_simple_circular_dependency(self):
        """Test detecting a simple A → B → A cycle."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'FileA',
                'files_to_generate': ['a.py'],
                'code': 'from b import B'
            },
            {
                'title': 'FileB',
                'files_to_generate': ['b.py'],
                'code': 'from a import A'
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        
        # Detect cycles
        cycles = analyzer._detect_cycles()
        assert len(cycles) > 0
        
        # Should still be able to sort after breaking cycles
        batches = analyzer.topological_sort()
        assert len(batches) >= 1
    
    def test_three_way_circular(self):
        """Test detecting A → B → C → A cycle."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'FileA',
                'files_to_generate': ['a.py'],
                'code': 'from b import B'
            },
            {
                'title': 'FileB',
                'files_to_generate': ['b.py'],
                'code': 'from c import C'
            },
            {
                'title': 'FileC',
                'files_to_generate': ['c.py'],
                'code': 'from a import A'
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        
        # Should detect cycle
        cycles = analyzer._detect_cycles()
        assert len(cycles) > 0
        
        # Should break cycle and sort successfully
        batches = analyzer.topological_sort()
        assert len(batches) >= 1


# ============================================================================
# Critical Path Analysis Tests
# ============================================================================

class TestCriticalPath:
    """Test critical path analysis."""
    
    def test_linear_critical_path(self):
        """Test finding critical path in linear dependency chain."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {'title': 'A', 'files_to_generate': ['a.py'], 'code': ''},
            {'title': 'B', 'files_to_generate': ['b.py'], 'code': 'from a import A'},
            {'title': 'C', 'files_to_generate': ['c.py'], 'code': 'from b import B'},
            {'title': 'D', 'files_to_generate': ['d.py'], 'code': 'from c import C'}
        ]
        
        analyzer.build_dependency_graph(tasks)
        analyzer.topological_sort()
        
        critical_path, path_length = analyzer.analyze_critical_path()
        
        # Path length should be 4 (all files in sequence)
        assert path_length >= 3
    
    def test_branching_critical_path(self):
        """Test finding longest path in branching structure."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {'title': 'Base', 'files_to_generate': ['base.py'], 'code': ''},
            {'title': 'Short', 'files_to_generate': ['short.py'], 'code': 'from base import Base'},
            {'title': 'Long1', 'files_to_generate': ['long1.py'], 'code': 'from base import Base'},
            {'title': 'Long2', 'files_to_generate': ['long2.py'], 'code': 'from long1 import Long1'},
            {'title': 'Long3', 'files_to_generate': ['long3.py'], 'code': 'from long2 import Long2'}
        ]
        
        analyzer.build_dependency_graph(tasks)
        analyzer.topological_sort()
        
        critical_path, path_length = analyzer.analyze_critical_path()
        
        # Longest path should be base → long1 → long2 → long3
        assert path_length >= 3


# ============================================================================
# Statistics Tests
# ============================================================================

class TestStatistics:
    """Test dependency analysis statistics."""
    
    def test_basic_statistics(self):
        """Test collecting basic statistics."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'Utils',
                'files_to_generate': ['utils.py'],
                'code': ''
            },
            {
                'title': 'Model1',
                'files_to_generate': ['model1.py'],
                'code': 'from utils import helper'
            },
            {
                'title': 'Model2',
                'files_to_generate': ['model2.py'],
                'code': 'from utils import helper'
            },
            {
                'title': 'Main',
                'files_to_generate': ['main.py'],
                'code': 'from model1 import Model1\nfrom model2 import Model2'
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        analyzer.topological_sort()
        
        stats = analyzer.get_statistics()
        
        assert stats['total_files'] == 4
        assert stats['total_dependencies'] > 0
        assert 'critical_path_length' in stats
        assert 'most_dependent_files' in stats
        assert 'most_required_files' in stats
    
    def test_most_required_file(self):
        """Test identifying most required file."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {'title': 'Base', 'files_to_generate': ['base.py'], 'code': ''},
            {'title': 'File1', 'files_to_generate': ['file1.py'], 'code': 'from base import Base'},
            {'title': 'File2', 'files_to_generate': ['file2.py'], 'code': 'from base import Base'},
            {'title': 'File3', 'files_to_generate': ['file3.py'], 'code': 'from base import Base'}
        ]
        
        analyzer.build_dependency_graph(tasks)
        stats = analyzer.get_statistics()
        
        # base.py should be the most required file
        most_required = stats['most_required_files'][0]
        assert most_required['file'] == 'base.py'
        assert most_required['required_by'] == 3


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test full dependency analysis workflow."""
    
    def test_analyze_plan_dependencies(self):
        """Test analyzing dependencies from a complete plan."""
        plan = {
            'subtasks': [
                {
                    'title': 'Configuration',
                    'description': 'App configuration',
                    'files_to_generate': ['config.py'],
                    'code': 'import os'
                },
                {
                    'title': 'Database Models',
                    'description': 'Data models',
                    'files_to_generate': ['models.py'],
                    'code': 'from config import settings'
                },
                {
                    'title': 'API Routes',
                    'description': 'REST API',
                    'files_to_generate': ['routes.py'],
                    'code': 'from models import User'
                },
                {
                    'title': 'Main Application',
                    'description': 'Entry point',
                    'files_to_generate': ['main.py'],
                    'code': 'from routes import app'
                }
            ]
        }
        
        batches = analyze_plan_dependencies(plan)
        
        # Should produce multiple batches
        assert len(batches) >= 3
        
        # First batch should include config.py
        batch0_files = {f.file_path for f in batches[0].files}
        assert 'config.py' in batch0_files
    
    def test_real_world_flask_app(self):
        """Test analyzing a realistic Flask application structure."""
        analyzer = DependencyAnalyzer()
        
        tasks = [
            {
                'title': 'Config',
                'files_to_generate': ['config.py'],
                'code': 'import os\nfrom pathlib import Path'
            },
            {
                'title': 'Database',
                'files_to_generate': ['database.py'],
                'code': 'from flask_sqlalchemy import SQLAlchemy\nfrom config import DATABASE_URL'
            },
            {
                'title': 'Models',
                'files_to_generate': ['models.py'],
                'code': 'from database import db\nfrom config import settings'
            },
            {
                'title': 'Schemas',
                'files_to_generate': ['schemas.py'],
                'code': 'from marshmallow import Schema\nfrom models import User'
            },
            {
                'title': 'Routes',
                'files_to_generate': ['routes.py'],
                'code': 'from flask import Blueprint\nfrom schemas import UserSchema\nfrom models import User'
            },
            {
                'title': 'App Factory',
                'files_to_generate': ['app.py'],
                'code': 'from flask import Flask\nfrom database import db\nfrom routes import api_blueprint'
            },
            {
                'title': 'Main',
                'files_to_generate': ['main.py'],
                'code': 'from app import create_app\nfrom config import PORT'
            }
        ]
        
        analyzer.build_dependency_graph(tasks)
        batches = analyzer.topological_sort()
        
        # Should group independent files in same batch
        assert len(batches) >= 3
        
        # Config should be in first batch
        assert batches[0].files[0].file_path == 'config.py'
        
        # Verify parallelism where possible
        total_files = sum(len(batch.files) for batch in batches)
        assert total_files == 7


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance with large dependency graphs."""
    
    def test_large_graph_performance(self):
        """Test analyzing a large dependency graph (100 files)."""
        import time
        
        analyzer = DependencyAnalyzer()
        
        # Generate 100 tasks with random dependencies
        tasks = []
        for i in range(100):
            code = ''
            if i > 0 and i % 10 != 0:  # Every 10th file has no deps
                # Depend on previous file
                code = f'from file{i-1} import Mod{i-1}'
            
            tasks.append({
                'title': f'File{i}',
                'files_to_generate': [f'file{i}.py'],
                'code': code
            })
        
        start_time = time.time()
        analyzer.build_dependency_graph(tasks)
        batches = analyzer.topological_sort()
        duration = time.time() - start_time
        
        # Should complete in reasonable time
        assert duration < 1.0  # Less than 1 second
        
        # Should produce valid batches
        assert len(batches) > 0
        total_files = sum(len(batch.files) for batch in batches)
        assert total_files == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
