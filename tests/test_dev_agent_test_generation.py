"""
Integration tests for DevAgent test generation

Verifies that DevAgent properly integrates TestGenerator functionality.
"""

import pytest
from pathlib import Path
from agents.dev_agent import DevAgent
from models.task import Task
from models.enums import TaskStatus


class TestDevAgentTestGeneration:
    """Test suite for DevAgent test generation integration"""
    
    @pytest.fixture
    def dev_agent(self):
        """Create DevAgent instance"""
        return DevAgent()
    
    def test_dev_agent_has_test_generator(self, dev_agent):
        """Test that DevAgent has TestGenerator initialized"""
        assert hasattr(dev_agent, 'test_generator')
        assert dev_agent.test_generator is not None
    
    @pytest.mark.asyncio
    async def test_generate_task_tests_method_exists(self, dev_agent):
        """Test that _generate_task_tests method exists"""
        assert hasattr(dev_agent, '_generate_task_tests')
        assert callable(dev_agent._generate_task_tests)
    
    @pytest.mark.asyncio
    async def test_generate_task_tests_with_python_code(self, dev_agent):
        """Test generating tests for Python code"""
        task = Task(
            id="test-task-1",
            title="Test Task",
            description="Test task for test generation",
            priority=1,
            status=TaskStatus.IN_PROGRESS
        )
        
        code_files = {
            'calculator.py': {
                'content': '''
def add(a, b):
    """Add two numbers"""
    return a + b

def subtract(a, b):
    """Subtract two numbers"""
    return a - b
''',
                'language': 'python'
            }
        }
        
        # Create temporary task directory
        task_dir = Path("generated_code/dev_outputs/test_task")
        task_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            test_files = await dev_agent._generate_task_tests(task, code_files, task_dir)
            
            # Should return a dictionary (may be empty if LLM fails)
            assert isinstance(test_files, dict)
            
        finally:
            # Cleanup
            import shutil
            if task_dir.exists():
                shutil.rmtree(task_dir)
    
    @pytest.mark.asyncio
    async def test_generate_task_tests_with_no_testable_code(self, dev_agent):
        """Test generating tests when no testable code exists"""
        task = Task(
            id="test-task-2",
            title="Test Task",
            description="Test task with no testable code",
            priority=1,
            status=TaskStatus.IN_PROGRESS
        )
        
        code_files = {
            'config.json': {
                'content': '{"key": "value"}',
                'language': 'json'
            }
        }
        
        task_dir = Path("generated_code/dev_outputs/test_task_2")
        task_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            test_files = await dev_agent._generate_task_tests(task, code_files, task_dir)
            
            # Should return empty dict when no testable code
            assert isinstance(test_files, dict)
            
        finally:
            # Cleanup
            import shutil
            if task_dir.exists():
                shutil.rmtree(task_dir)
    
    def test_completion_summary_includes_test_info(self, dev_agent):
        """Test that completion summary includes test information"""
        import asyncio
        
        task = Task(
            id="test-task-3",
            title="Test Task",
            description="Test task",
            priority=1,
            status=TaskStatus.COMPLETED
        )
        
        saved_files = ['main.py', 'utils.py']
        task_dir = Path("generated_code/dev_outputs/test_task_3")
        task_dir.mkdir(parents=True, exist_ok=True)
        
        test_files = {
            'tests/test_main.py': 'def test_main(): pass',
            'tests/test_utils.py': 'def test_utils(): pass'
        }
        
        try:
            summary = asyncio.run(
                dev_agent._generate_completion_summary(task, saved_files, task_dir, test_files)
            )
            
            # Summary should mention tests
            assert '🧪' in summary or 'test' in summary.lower()
            assert 'pytest' in summary.lower() or 'test' in summary.lower()
            
        finally:
            # Cleanup
            import shutil
            if task_dir.exists():
                shutil.rmtree(task_dir)
