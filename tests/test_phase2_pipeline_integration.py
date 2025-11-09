"""
Unit tests for Phase 2.1: Pipeline Integration with Dependency Analyzer.

Tests cover:
- Dependency analysis integration with EnhancedPipelineManager
- Batch submission and execution
- Priority assignment based on critical path
- Statistics and monitoring
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from utils.enhanced_pipeline_manager import EnhancedPipelineManager
from utils.enhanced_components import TaskPriority


# ============================================================================
# Integration Tests
# ============================================================================

class TestPipelineIntegration:
    """Test integration of DependencyAnalyzer with EnhancedPipelineManager."""
    
    @pytest.fixture
    def pipeline_manager(self):
        """Create pipeline manager for testing."""
        manager = EnhancedPipelineManager(
            dev_workers_min=2,
            dev_workers_max=4,
            qa_workers_min=1,
            qa_workers_max=2,
            enable_cache=False,  # Disable cache for testing
            enable_circuit_breaker=False  # Disable circuit breaker for testing
        )
        
        # Mock agents
        manager.dev_agent = Mock()
        manager.qa_agent = Mock()
        manager.ops_agent = Mock()
        
        return manager
    
    def test_dependency_analyzer_initialization(self, pipeline_manager):
        """Test that dependency analyzer is properly initialized."""
        assert pipeline_manager.dependency_analyzer is not None
        assert pipeline_manager.use_dependency_analysis is True
        assert pipeline_manager.dependency_batches == []
    
    @pytest.mark.asyncio
    async def test_analyze_simple_plan(self, pipeline_manager):
        """Test dependency analysis of a simple plan."""
        plan = {
            'tasks': [
                {
                    'title': 'Config File',
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
        }
        
        websocket = Mock()
        result = await pipeline_manager.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Test project"
        )
        
        # Should create 3 batches (linear dependency)
        assert result['batches'] == 3
        assert result['tasks'] == 3
        assert 'stats' in result
    
    @pytest.mark.asyncio
    async def test_analyze_parallel_tasks(self, pipeline_manager):
        """Test analysis of independent tasks that can run in parallel."""
        plan = {
            'tasks': [
                {
                    'title': 'Service A',
                    'files_to_generate': ['service_a.py'],
                    'code': 'import os'
                },
                {
                    'title': 'Service B',
                    'files_to_generate': ['service_b.py'],
                    'code': 'import sys'
                },
                {
                    'title': 'Service C',
                    'files_to_generate': ['service_c.py'],
                    'code': 'import json'
                }
            ]
        }
        
        websocket = Mock()
        result = await pipeline_manager.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Test project"
        )
        
        # Should create 1 batch (all parallel)
        assert result['batches'] == 1
        assert result['tasks'] == 3
        
        # Check max parallelism
        stats = result['stats']
        assert stats['max_parallelism'] == 3
    
    @pytest.mark.asyncio
    async def test_critical_path_priority_assignment(self, pipeline_manager):
        """Test that critical path tasks get HIGH priority."""
        plan = {
            'tasks': [
                {
                    'title': 'Base Module',
                    'files_to_generate': ['base.py'],
                    'code': ''
                },
                {
                    'title': 'Dependent Module A',
                    'files_to_generate': ['module_a.py'],
                    'code': 'from base import BaseClass'
                },
                {
                    'title': 'Dependent Module B',
                    'files_to_generate': ['module_b.py'],
                    'code': 'from base import BaseClass'
                },
                {
                    'title': 'Final Module',
                    'files_to_generate': ['final.py'],
                    'code': 'from module_a import ClassA'
                }
            ]
        }
        
        websocket = Mock()
        await pipeline_manager.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Test project"
        )
        
        # Verify batches were created
        assert len(pipeline_manager.dependency_batches) > 0
        
        # Check that critical path was identified
        stats = pipeline_manager.dependency_analyzer.get_stats()
        assert stats['critical_path_length'] > 0
    
    def test_find_task_by_file(self, pipeline_manager):
        """Test task lookup by file path."""
        plan = {
            'tasks': [
                {
                    'title': 'Config Setup',
                    'files_to_generate': ['config.py', 'settings.json'],
                    'code': ''
                },
                {
                    'title': 'Database Models',
                    'files_to_generate': ['models/user.py'],
                    'code': ''
                }
            ]
        }
        
        # Find by exact match
        task = pipeline_manager._find_task_by_file(plan, 'config.py')
        assert task is not None
        assert task['title'] == 'Config Setup'
        
        # Find by partial match
        task = pipeline_manager._find_task_by_file(plan, 'models/user.py')
        assert task is not None
        assert task['title'] == 'Database Models'
        
        # Not found
        task = pipeline_manager._find_task_by_file(plan, 'nonexistent.py')
        assert task is None
    
    def test_enhanced_stats_include_dependency_info(self, pipeline_manager):
        """Test that enhanced stats include dependency analysis metrics."""
        stats = pipeline_manager.get_enhanced_stats()
        
        assert 'dependency_analysis' in stats
        assert 'enabled' in stats['dependency_analysis']
        assert 'batches' in stats['dependency_analysis']
        assert 'analyzer_stats' in stats['dependency_analysis']
        
        # Verify it's enabled
        assert stats['dependency_analysis']['enabled'] is True
    
    @pytest.mark.asyncio
    async def test_empty_plan_handling(self, pipeline_manager):
        """Test handling of empty plan."""
        plan = {'tasks': []}
        websocket = Mock()
        
        result = await pipeline_manager.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Empty project"
        )
        
        assert result['batches'] == 0
        assert result['tasks'] == 0
    
    @pytest.mark.asyncio
    async def test_complex_dependency_graph(self, pipeline_manager):
        """Test analysis of complex dependency graph with multiple levels."""
        plan = {
            'tasks': [
                # Level 0: No dependencies
                {'title': 'Utils', 'files_to_generate': ['utils.py'], 'code': ''},
                {'title': 'Constants', 'files_to_generate': ['constants.py'], 'code': ''},
                
                # Level 1: Depend on level 0
                {
                    'title': 'Models',
                    'files_to_generate': ['models.py'],
                    'code': 'from utils import helper\nfrom constants import VERSION'
                },
                
                # Level 2: Depend on level 1
                {
                    'title': 'Services',
                    'files_to_generate': ['services.py'],
                    'code': 'from models import User'
                },
                
                # Level 3: Depend on level 2
                {
                    'title': 'API',
                    'files_to_generate': ['api.py'],
                    'code': 'from services import UserService'
                }
            ]
        }
        
        websocket = Mock()
        result = await pipeline_manager.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Complex project"
        )
        
        # Should have multiple batches
        assert result['batches'] >= 3
        assert result['tasks'] == 5
        
        # Verify critical path
        stats = result['stats']
        assert stats['critical_path_length'] >= 3


# ============================================================================
# Performance Tests
# ============================================================================

class TestPipelinePerformance:
    """Test performance of dependency-aware pipeline."""
    
    @pytest.mark.asyncio
    async def test_large_plan_analysis_performance(self):
        """Test analysis performance with large plan."""
        # Create a large plan with many tasks
        tasks = []
        for i in range(100):
            tasks.append({
                'title': f'Task {i}',
                'files_to_generate': [f'file_{i}.py'],
                'code': f'import os\n# Task {i}'
            })
        
        plan = {'tasks': tasks}
        
        manager = EnhancedPipelineManager(
            dev_workers_min=2,
            dev_workers_max=10,
            enable_cache=False,
            enable_circuit_breaker=False
        )
        
        websocket = Mock()
        
        # Measure analysis time
        import time
        start = time.time()
        result = await manager.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Large project"
        )
        duration = time.time() - start
        
        # Should complete in reasonable time
        assert duration < 5.0  # Less than 5 seconds
        assert result['tasks'] == 100
        
        print(f"\n⏱️ Analyzed {result['tasks']} tasks in {duration:.3f}s")
        print(f"📦 Created {result['batches']} batches")
        print(f"🔄 Max parallelism: {result['stats']['max_parallelism']}")
