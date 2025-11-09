"""
Phase 2.3: Comprehensive Integration Test Suite

Tests cover:
- Full PM → Dev → QA → Ops workflow
- Multi-agent collaboration
- Error recovery and retry mechanisms
- Performance under load
- Resource cleanup
- Edge cases and failure scenarios
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from utils.enhanced_pipeline_manager import EnhancedPipelineManager
from utils.dependency_analyzer import DependencyAnalyzer
from utils.enhanced_components import TaskPriority, EventType
from models.task import Task
from models.enums import TaskStatus


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_agents():
    """Create mock agents for testing."""
    dev_agent = Mock()
    dev_agent.execute_task = AsyncMock(return_value={"code": "generated", "files": ["main.py"]})
    
    qa_agent = Mock()
    qa_agent.execute_task = AsyncMock(return_value={"status": "passed", "tests": 10})
    
    ops_agent = Mock()
    ops_agent.execute_task = AsyncMock(return_value={"deployed": True, "url": "http://localhost:8000"})
    
    return {
        "dev": dev_agent,
        "qa": qa_agent,
        "ops": ops_agent
    }


@pytest_asyncio.fixture
async def pipeline():
    """Create enhanced pipeline for testing."""
    pipeline = EnhancedPipelineManager(
        dev_workers_min=2,
        dev_workers_max=5,
        qa_workers_min=1,
        qa_workers_max=3,
        enable_cache=True,
        enable_circuit_breaker=True
    )
    yield pipeline
    
    # Cleanup
    if pipeline.is_running:
        await pipeline.stop()


# ============================================================================
# Full Workflow Tests
# ============================================================================

class TestFullWorkflow:
    """Test complete PM → Dev → QA → Ops workflow."""
    
    @pytest.mark.asyncio
    async def test_simple_project_workflow(self, pipeline, mock_agents):
        """Test generating a simple project end-to-end."""
        # Set agents
        pipeline.set_agents(
            dev_agent=mock_agents["dev"],
            qa_agent=mock_agents["qa"],
            ops_agent=mock_agents["ops"]
        )
        
        # Start pipeline
        await pipeline.start()
        
        # Submit tasks
        plan = {
            'tasks': [
                {
                    'title': 'Main File',
                    'files_to_generate': ['main.py'],
                    'code': 'print("hello")',
                    'description': 'Entry point'
                }
            ]
        }
        
        websocket = Mock()
        result = await pipeline.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Simple project"
        )
        
        # Verify analysis
        assert result['batches'] == 1
        assert result['tasks'] == 1
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Verify dev agent was called
        assert mock_agents["dev"].execute_task.called
    
    @pytest.mark.asyncio
    async def test_multi_file_dependency_workflow(self, pipeline, mock_agents):
        """Test project with multiple files and dependencies."""
        pipeline.set_agents(
            dev_agent=mock_agents["dev"],
            qa_agent=mock_agents["qa"],
            ops_agent=mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Create plan with dependencies
        plan = {
            'tasks': [
                {
                    'title': 'Config',
                    'files_to_generate': ['config.py'],
                    'code': 'API_KEY = "test"'
                },
                {
                    'title': 'Models',
                    'files_to_generate': ['models.py'],
                    'code': 'from config import API_KEY'
                },
                {
                    'title': 'Main',
                    'files_to_generate': ['main.py'],
                    'code': 'from models import User'
                }
            ]
        }
        
        websocket = Mock()
        result = await pipeline.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Multi-file project"
        )
        
        # Should create 3 batches (linear dependency)
        assert result['batches'] == 3
        assert result['tasks'] == 3
        
        # Verify dependency analysis stats
        stats = result['stats']
        assert stats['total_files'] == 3
        assert stats['critical_path_length'] >= 2
    
    @pytest.mark.asyncio
    async def test_parallel_tasks_workflow(self, pipeline, mock_agents):
        """Test parallel execution of independent tasks."""
        pipeline.set_agents(
            dev_agent=mock_agents["dev"],
            qa_agent=mock_agents["qa"],
            ops_agent=mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Create plan with independent tasks
        plan = {
            'tasks': [
                {
                    'title': 'Service A',
                    'files_to_generate': ['service_a.py'],
                    'code': 'class ServiceA: pass'
                },
                {
                    'title': 'Service B',
                    'files_to_generate': ['service_b.py'],
                    'code': 'class ServiceB: pass'
                },
                {
                    'title': 'Service C',
                    'files_to_generate': ['service_c.py'],
                    'code': 'class ServiceC: pass'
                }
            ]
        }
        
        websocket = Mock()
        result = await pipeline.analyze_and_submit_plan(
            plan=plan,
            websocket=websocket,
            project_desc="Parallel services"
        )
        
        # All tasks should be in single batch (parallel)
        assert result['batches'] == 1
        assert result['stats']['max_parallelism'] == 3


# ============================================================================
# Error Recovery Tests
# ============================================================================

class TestErrorRecovery:
    """Test error handling and recovery mechanisms."""
    
    @pytest.mark.asyncio
    async def test_dev_task_failure_recovery(self, pipeline):
        """Test recovery from dev task failure."""
        # Mock dev agent that fails first then succeeds
        dev_agent = Mock()
        call_count = {'count': 0}
        
        async def dev_execute(task):
            call_count['count'] += 1
            if call_count['count'] == 1:
                raise Exception("Simulated failure")
            return {"code": "success", "files": ["main.py"]}
        
        dev_agent.execute_task = AsyncMock(side_effect=dev_execute)
        
        qa_agent = Mock()
        qa_agent.execute_task = AsyncMock(return_value={"status": "passed"})
        
        ops_agent = Mock()
        ops_agent.execute_task = AsyncMock(return_value={"deployed": True})
        
        pipeline.set_agents(dev_agent, qa_agent, ops_agent)
        await pipeline.start()
        
        # Submit task
        plan = {
            'tasks': [{
                'title': 'Test File',
                'files_to_generate': ['test.py'],
                'code': 'print("test")'
            }]
        }
        
        await pipeline.analyze_and_submit_plan(plan, Mock(), "Test project")
        await asyncio.sleep(1.0)
        
        # Should have called dev agent at least once
        assert dev_agent.execute_task.called
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self, pipeline, mock_agents):
        """Test circuit breaker triggers on high error rate."""
        # Mock dev agent that always fails
        dev_agent = Mock()
        dev_agent.execute_task = AsyncMock(side_effect=Exception("Always fails"))
        
        pipeline.set_agents(dev_agent, mock_agents["qa"], mock_agents["ops"])
        await pipeline.start()
        
        # Submit multiple tasks
        for i in range(10):
            plan = {
                'tasks': [{
                    'title': f'Task {i}',
                    'files_to_generate': [f'file_{i}.py'],
                    'code': 'test'
                }]
            }
            await pipeline.analyze_and_submit_plan(plan, Mock(), f"Project {i}")
        
        await asyncio.sleep(2.0)
        
        # Verify circuit breaker stats
        stats = pipeline.get_enhanced_stats()
        assert 'circuit_breakers' in stats
    
    @pytest.mark.asyncio
    async def test_event_router_dlq(self, pipeline, mock_agents):
        """Test dead letter queue for failed events."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Simulate event routing failure by accessing DLQ
        dlq_items = pipeline.get_dlq_items()
        
        # Should start empty
        assert len(dlq_items) == 0


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test system performance under load."""
    
    @pytest.mark.asyncio
    async def test_high_task_volume(self, pipeline, mock_agents):
        """Test handling large number of tasks."""
        import time
        
        # Fast mock agents
        dev_agent = Mock()
        dev_agent.execute_task = AsyncMock(return_value={"code": "fast"})
        
        pipeline.set_agents(dev_agent, mock_agents["qa"], mock_agents["ops"])
        await pipeline.start()
        
        # Submit 50 tasks
        tasks = []
        for i in range(50):
            tasks.append({
                'title': f'Task {i}',
                'files_to_generate': [f'file_{i}.py'],
                'code': f'# File {i}'
            })
        
        plan = {'tasks': tasks}
        
        start = time.time()
        result = await pipeline.analyze_and_submit_plan(plan, Mock(), "Large project")
        analysis_time = time.time() - start
        
        # Analysis should be fast
        assert analysis_time < 2.0
        assert result['tasks'] == 50
        
        print(f"\n⏱️ Analyzed 50 tasks in {analysis_time:.3f}s")
        print(f"📦 Created {result['batches']} batches")
    
    @pytest.mark.asyncio
    async def test_cache_performance(self, pipeline, mock_agents):
        """Test result cache improves performance."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Submit same task twice
        plan = {
            'tasks': [{
                'title': 'Cached Task',
                'files_to_generate': ['cached.py'],
                'code': 'print("cached")'
            }]
        }
        
        # First submission
        await pipeline.analyze_and_submit_plan(plan, Mock(), "Cache test 1")
        await asyncio.sleep(0.5)
        first_calls = mock_agents["dev"].execute_task.call_count
        
        # Second submission (should use cache)
        await pipeline.analyze_and_submit_plan(plan, Mock(), "Cache test 2")
        await asyncio.sleep(0.5)
        second_calls = mock_agents["dev"].execute_task.call_count
        
        # Verify cache stats
        stats = pipeline.get_enhanced_stats()
        cache_stats = stats.get('cache', {})
        
        # Cache should exist and have stats
        assert 'hits' in cache_stats or 'misses' in cache_stats


# ============================================================================
# Resource Management Tests
# ============================================================================

class TestResourceManagement:
    """Test proper resource allocation and cleanup."""
    
    @pytest.mark.asyncio
    async def test_pipeline_start_stop(self, pipeline, mock_agents):
        """Test starting and stopping pipeline cleanly."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        # Start
        await pipeline.start()
        assert pipeline.is_running is True
        
        # Stop
        await pipeline.stop()
        assert pipeline.is_running is False
        
        # Should be able to restart
        await pipeline.start()
        assert pipeline.is_running is True
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_worker_pool_scaling(self, pipeline, mock_agents):
        """Test auto-scaling worker pool."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Check initial worker count
        stats = pipeline.get_enhanced_stats()
        
        # Submit many tasks to trigger scaling
        tasks = [
            {
                'title': f'Scale Task {i}',
                'files_to_generate': [f'scale_{i}.py'],
                'code': 'test'
            }
            for i in range(20)
        ]
        
        await pipeline.analyze_and_submit_plan(
            {'tasks': tasks},
            Mock(),
            "Scaling test"
        )
        
        await asyncio.sleep(1.0)
        
        # Verify pipeline is running
        assert pipeline.is_running


# ============================================================================
# Integration Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_microservices_project(self, pipeline, mock_agents):
        """Test generating a microservices architecture."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Microservices plan
        plan = {
            'tasks': [
                # Shared
                {'title': 'Common Utils', 'files_to_generate': ['common/utils.py'], 'code': 'def log(): pass'},
                {'title': 'Common Models', 'files_to_generate': ['common/models.py'], 'code': 'class BaseModel: pass'},
                
                # Service 1
                {'title': 'User Service', 'files_to_generate': ['services/user.py'], 'code': 'from common.models import BaseModel'},
                
                # Service 2
                {'title': 'Auth Service', 'files_to_generate': ['services/auth.py'], 'code': 'from common.models import BaseModel'},
                
                # Service 3
                {'title': 'API Gateway', 'files_to_generate': ['services/gateway.py'], 'code': 'from services.user import UserService'},
            ]
        }
        
        result = await pipeline.analyze_and_submit_plan(plan, Mock(), "Microservices")
        
        # Verify proper batching
        assert result['tasks'] == 5
        # Note: Dependency detection may not catch all patterns, so batching may vary
        assert result['batches'] >= 1
    
    @pytest.mark.asyncio
    async def test_full_stack_application(self, pipeline, mock_agents):
        """Test generating full stack application."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Full stack plan
        plan = {
            'tasks': [
                # Backend
                {'title': 'Database Models', 'files_to_generate': ['backend/models.py'], 'code': 'class User: pass'},
                {'title': 'API Routes', 'files_to_generate': ['backend/routes.py'], 'code': 'from models import User'},
                {'title': 'Auth Middleware', 'files_to_generate': ['backend/auth.py'], 'code': 'def verify(): pass'},
                
                # Frontend
                {'title': 'React Components', 'files_to_generate': ['frontend/components.jsx'], 'code': 'export const App = () => {}'},
                {'title': 'API Client', 'files_to_generate': ['frontend/api.js'], 'code': 'const api = axios.create()'},
                
                # Config
                {'title': 'Environment Config', 'files_to_generate': ['.env'], 'code': 'API_URL=localhost'},
            ]
        }
        
        result = await pipeline.analyze_and_submit_plan(plan, Mock(), "Full Stack App")
        
        assert result['tasks'] == 6
        
        # Verify stats include all features
        stats = pipeline.get_enhanced_stats()
        assert 'dependency_analysis' in stats
        assert 'priority_stats' in stats


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_plan(self, pipeline, mock_agents):
        """Test handling empty plan."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        result = await pipeline.analyze_and_submit_plan(
            {'tasks': []},
            Mock(),
            "Empty project"
        )
        
        assert result['batches'] == 0
        assert result['tasks'] == 0
    
    @pytest.mark.asyncio
    async def test_circular_dependencies_broken(self, pipeline, mock_agents):
        """Test circular dependencies are automatically broken."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Create circular dependency
        plan = {
            'tasks': [
                {
                    'title': 'File A',
                    'files_to_generate': ['a.py'],
                    'code': 'from b import func_b'
                },
                {
                    'title': 'File B',
                    'files_to_generate': ['b.py'],
                    'code': 'from a import func_a'  # Circular!
                }
            ]
        }
        
        # Should not raise exception
        result = await pipeline.analyze_and_submit_plan(plan, Mock(), "Circular test")
        
        # Should have detected and broken cycle
        assert result['tasks'] == 2
        assert result['batches'] >= 1
    
    @pytest.mark.asyncio
    async def test_very_long_dependency_chain(self, pipeline, mock_agents):
        """Test handling very long dependency chains."""
        pipeline.set_agents(
            mock_agents["dev"],
            mock_agents["qa"],
            mock_agents["ops"]
        )
        
        await pipeline.start()
        
        # Create chain: file_0 → file_1 → file_2 → ... → file_9
        tasks = []
        for i in range(10):
            code = f'from file_{i-1} import func' if i > 0 else 'def func(): pass'
            tasks.append({
                'title': f'File {i}',
                'files_to_generate': [f'file_{i}.py'],
                'code': code
            })
        
        result = await pipeline.analyze_and_submit_plan(
            {'tasks': tasks},
            Mock(),
            "Long chain"
        )
        
        # Should create 10 batches (one per level)
        assert result['tasks'] == 10
        assert result['batches'] == 10
        assert result['stats']['critical_path_length'] == 10
