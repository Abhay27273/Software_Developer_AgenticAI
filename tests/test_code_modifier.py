"""
Tests for the CodeModifier module with LangGraph workflow.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from utils.code_modifier import (
    CodeModifier,
    ModificationResult,
    ModificationPlan,
    ModificationState,
    modify_code_file
)


# Sample code for testing
SAMPLE_PYTHON_CODE = '''
def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    return a + b

def calculate_product(a, b):
    """Calculate the product of two numbers."""
    return a * b

class Calculator:
    """A simple calculator class."""
    
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
'''

MODIFIED_PYTHON_CODE = '''
def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Arguments must be numbers")
    return a + b

def calculate_product(a, b):
    """Calculate the product of two numbers."""
    return a * b

def calculate_difference(a, b):
    """Calculate the difference of two numbers."""
    return a - b

class Calculator:
    """A simple calculator class."""
    
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
    
    def subtract(self, a, b):
        result = a - b
        self.history.append(f"{a} - {b} = {result}")
        return result
'''


class TestCodeModifier:
    """Test suite for CodeModifier class."""
    
    @pytest.fixture
    def code_modifier(self):
        """Create a CodeModifier instance for testing."""
        return CodeModifier(model="gemini-2.5-pro")
    
    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM responses for testing."""
        return {
            "parse": {
                "functions": ["calculate_sum", "calculate_product"],
                "classes": ["Calculator"],
                "imports": [],
                "language": "python"
            },
            "plan": {
                "changes": [
                    {
                        "type": "modify_function",
                        "target": "calculate_sum",
                        "action": "Add input validation",
                        "new_code": "def calculate_sum(a, b):\n    if not isinstance(a, (int, float)):\n        raise TypeError('a must be a number')\n    return a + b"
                    },
                    {
                        "type": "add_function",
                        "target": "calculate_difference",
                        "action": "Add subtraction function",
                        "new_code": "def calculate_difference(a, b):\n    return a - b"
                    }
                ],
                "rationale": "Adding input validation and new functionality",
                "risk_level": "low",
                "affected_functions": ["calculate_sum"],
                "affected_classes": [],
                "dependencies": []
            },
            "modified_code": MODIFIED_PYTHON_CODE
        }
    
    def test_code_modifier_initialization(self, code_modifier):
        """Test CodeModifier initialization."""
        assert code_modifier.model == "gemini-2.5-pro"
        assert code_modifier.workflow is not None
    
    def test_detect_language(self, code_modifier):
        """Test language detection from file extensions."""
        assert code_modifier._detect_language("test.py") == "python"
        assert code_modifier._detect_language("test.js") == "javascript"
        assert code_modifier._detect_language("test.ts") == "typescript"
        assert code_modifier._detect_language("test.java") == "java"
        assert code_modifier._detect_language("test.unknown") == "unknown"
    
    def test_parse_python_code(self, code_modifier):
        """Test Python code parsing with AST."""
        tree, structure = code_modifier._parse_python_code(SAMPLE_PYTHON_CODE)
        
        assert tree is not None
        assert "calculate_sum" in structure["functions"]
        assert "calculate_product" in structure["functions"]
        assert "Calculator" in structure["classes"]
        assert structure["language"] == "python"
    
    def test_parse_invalid_python_code(self, code_modifier):
        """Test parsing invalid Python code."""
        invalid_code = "def broken_function(\n    pass"
        tree, structure = code_modifier._parse_python_code(invalid_code)
        
        assert tree is None
        assert structure["functions"] == []
        assert structure["classes"] == []
    
    def test_clean_code_response(self, code_modifier):
        """Test cleaning code response from LLM."""
        # Test with markdown code block
        response_with_markdown = "```python\nprint('hello')\n```"
        cleaned = code_modifier._clean_code_response(response_with_markdown)
        assert cleaned == "print('hello')"
        
        # Test without markdown
        response_without_markdown = "print('hello')"
        cleaned = code_modifier._clean_code_response(response_without_markdown)
        assert cleaned == "print('hello')"
    
    def test_parse_json_response(self, code_modifier):
        """Test parsing JSON from LLM response."""
        # Test with markdown code block
        json_with_markdown = '```json\n{"key": "value"}\n```'
        parsed = code_modifier._parse_json_response(json_with_markdown)
        assert parsed == {"key": "value"}
        
        # Test without markdown
        json_without_markdown = '{"key": "value"}'
        parsed = code_modifier._parse_json_response(json_without_markdown)
        assert parsed == {"key": "value"}
        
        # Test with json language identifier
        json_with_identifier = 'json\n{"key": "value"}'
        parsed = code_modifier._parse_json_response(json_with_identifier)
        assert parsed == {"key": "value"}
    
    def test_parse_json_response_invalid(self, code_modifier):
        """Test parsing invalid JSON raises error."""
        invalid_json = "not valid json"
        
        with pytest.raises(ValueError, match="Invalid JSON response"):
            code_modifier._parse_json_response(invalid_json)
    
    @pytest.mark.asyncio
    async def test_modify_code_success(self, code_modifier, mock_llm_response):
        """Test successful code modification workflow."""
        with patch('utils.code_modifier.ask_llm') as mock_llm:
            # Setup mock responses
            mock_llm.side_effect = [
                # Parse response (for non-Python, but we're using Python so this won't be called)
                None,
                # Plan response
                f'```json\n{json.dumps(mock_llm_response["plan"])}\n```',
                # Apply response
                mock_llm_response["modified_code"]
            ]
            
            result = await code_modifier.modify_code(
                file_path="test.py",
                original_content=SAMPLE_PYTHON_CODE,
                modification_request="Add input validation to calculate_sum and add a subtract function"
            )
            
            assert result.success
            assert "test.py" in result.modified_files
            assert result.diff != ""
            assert len(result.validation_errors) == 0
            assert result.rollback_available
    
    @pytest.mark.asyncio
    async def test_modify_code_syntax_error(self, code_modifier):
        """Test code modification with syntax error in result."""
        with patch('utils.code_modifier.ask_llm') as mock_llm:
            # Setup mock to return invalid Python code
            mock_llm.side_effect = [
                # Plan response
                '''```json
                {
                    "changes": [{"type": "modify_function", "target": "test", "action": "test", "new_code": "test"}],
                    "rationale": "test",
                    "risk_level": "low",
                    "affected_functions": [],
                    "affected_classes": [],
                    "dependencies": []
                }
                ```''',
                # Apply response with syntax error
                "def broken_function(\n    pass"
            ]
            
            result = await code_modifier.modify_code(
                file_path="test.py",
                original_content=SAMPLE_PYTHON_CODE,
                modification_request="Break the code"
            )
            
            assert not result.success
            assert len(result.validation_errors) > 0
            assert not result.rollback_available
    
    @pytest.mark.asyncio
    async def test_modify_code_plan_validation_failure(self, code_modifier):
        """Test code modification with plan validation failure."""
        with patch('utils.code_modifier.ask_llm') as mock_llm:
            # Setup mock to return invalid plan
            mock_llm.return_value = '''```json
            {
                "changes": [{"type": "invalid_type", "target": "test"}],
                "rationale": "test",
                "risk_level": "low",
                "affected_functions": [],
                "affected_classes": [],
                "dependencies": []
            }
            ```'''
            
            result = await code_modifier.modify_code(
                file_path="test.py",
                original_content=SAMPLE_PYTHON_CODE,
                modification_request="Invalid modification"
            )
            
            assert not result.success
            assert len(result.validation_errors) > 0
    
    @pytest.mark.asyncio
    async def test_modify_code_file_convenience_function(self):
        """Test the convenience function for code modification."""
        with patch('utils.code_modifier.ask_llm') as mock_llm:
            mock_llm.side_effect = [
                '''```json
                {
                    "changes": [{"type": "add_function", "target": "new_func", "action": "add", "new_code": "def new_func(): pass"}],
                    "rationale": "test",
                    "risk_level": "low",
                    "affected_functions": [],
                    "affected_classes": [],
                    "dependencies": []
                }
                ```''',
                MODIFIED_PYTHON_CODE
            ]
            
            result = await modify_code_file(
                file_path="test.py",
                original_content=SAMPLE_PYTHON_CODE,
                modification_request="Add a new function"
            )
            
            assert isinstance(result, ModificationResult)
    
    def test_create_planning_prompt(self, code_modifier):
        """Test creation of planning prompt."""
        code_structure = {
            "functions": ["func1", "func2"],
            "classes": ["Class1"],
            "language": "python"
        }
        
        prompt = code_modifier._create_planning_prompt(
            modification_request="Add error handling",
            code_structure=code_structure,
            original_content=SAMPLE_PYTHON_CODE
        )
        
        assert "Add error handling" in prompt
        assert "func1" in prompt
        assert "Class1" in prompt
        assert "python" in prompt
    
    def test_create_application_prompt(self, code_modifier):
        """Test creation of application prompt."""
        plan = ModificationPlan(
            file_path="test.py",
            changes=[
                {"type": "modify_function", "action": "Add validation"}
            ],
            rationale="Improve code quality",
            risk_level="low"
        )
        
        prompt = code_modifier._create_application_prompt(
            original_content=SAMPLE_PYTHON_CODE,
            modification_plan=plan
        )
        
        assert "Add validation" in prompt
        assert "Improve code quality" in prompt
        assert SAMPLE_PYTHON_CODE in prompt


class TestModificationPlan:
    """Test suite for ModificationPlan dataclass."""
    
    def test_modification_plan_creation(self):
        """Test creating a ModificationPlan."""
        plan = ModificationPlan(
            file_path="test.py",
            changes=[{"type": "modify_function", "target": "test"}],
            rationale="Test modification",
            risk_level="low",
            affected_functions=["test_func"],
            affected_classes=["TestClass"],
            dependencies=["pytest"]
        )
        
        assert plan.file_path == "test.py"
        assert len(plan.changes) == 1
        assert plan.risk_level == "low"
        assert "test_func" in plan.affected_functions
        assert "TestClass" in plan.affected_classes
        assert "pytest" in plan.dependencies


class TestModificationResult:
    """Test suite for ModificationResult dataclass."""
    
    def test_modification_result_success(self):
        """Test creating a successful ModificationResult."""
        result = ModificationResult(
            success=True,
            modified_files={"test.py": "modified content"},
            diff="+ new line\n- old line",
            validation_errors=[],
            rollback_available=True,
            metadata={"timestamp": "2024-01-01"}
        )
        
        assert result.success
        assert "test.py" in result.modified_files
        assert result.diff != ""
        assert len(result.validation_errors) == 0
        assert result.rollback_available
    
    def test_modification_result_failure(self):
        """Test creating a failed ModificationResult."""
        result = ModificationResult(
            success=False,
            modified_files={},
            diff="",
            validation_errors=["Syntax error", "Validation failed"],
            rollback_available=False,
            metadata={"error": "Failed to modify"}
        )
        
        assert not result.success
        assert len(result.modified_files) == 0
        assert len(result.validation_errors) == 2
        assert not result.rollback_available


class TestWorkflowStates:
    """Test suite for workflow state transitions."""
    
    @pytest.mark.asyncio
    async def test_parse_state(self):
        """Test the parse state in workflow."""
        modifier = CodeModifier()
        
        state = {
            "modification_request": "test",
            "file_path": "test.py",
            "original_content": SAMPLE_PYTHON_CODE,
            "parsed_ast": None,
            "code_structure": None,
            "modification_plan": None,
            "plan_validation": None,
            "modified_content": None,
            "syntax_valid": False,
            "validation_errors": [],
            "diff": None,
            "current_state": "parse",
            "should_rollback": False,
            "error_message": None,
            "result": None
        }
        
        result_state = await modifier._parse_code(state)
        
        assert result_state["code_structure"] is not None
        assert result_state["current_state"] == ModificationState.PLAN.value
    
    def test_should_proceed_with_modification(self):
        """Test conditional edge for proceeding with modification."""
        modifier = CodeModifier()
        
        # Test with safe plan
        state_safe = {
            "should_rollback": False,
            "plan_validation": {"is_safe": True}
        }
        assert modifier._should_proceed_with_modification(state_safe) == "apply"
        
        # Test with unsafe plan
        state_unsafe = {
            "should_rollback": False,
            "plan_validation": {"is_safe": False}
        }
        assert modifier._should_proceed_with_modification(state_unsafe) == "rollback"
        
        # Test with rollback flag
        state_rollback = {
            "should_rollback": True,
            "plan_validation": {"is_safe": True}
        }
        assert modifier._should_proceed_with_modification(state_rollback) == "rollback"
    
    def test_is_code_valid(self):
        """Test conditional edge for code validation."""
        modifier = CodeModifier()
        
        # Test with valid code
        state_valid = {"syntax_valid": True}
        assert modifier._is_code_valid(state_valid) == "generate_diff"
        
        # Test with invalid code
        state_invalid = {"syntax_valid": False}
        assert modifier._is_code_valid(state_invalid) == "rollback"


class TestIntegrationScenarios:
    """Integration tests for complete modification scenarios."""
    
    @pytest.mark.asyncio
    async def test_add_function_scenario(self):
        """Test adding a new function to existing code."""
        modifier = CodeModifier()
        
        with patch('utils.code_modifier.ask_llm') as mock_llm:
            mock_llm.side_effect = [
                '''```json
                {
                    "changes": [{
                        "type": "add_function",
                        "target": "calculate_difference",
                        "action": "Add subtraction function",
                        "new_code": "def calculate_difference(a, b):\\n    return a - b"
                    }],
                    "rationale": "Adding subtraction functionality",
                    "risk_level": "low",
                    "affected_functions": [],
                    "affected_classes": [],
                    "dependencies": []
                }
                ```''',
                MODIFIED_PYTHON_CODE
            ]
            
            result = await modifier.modify_code(
                file_path="calculator.py",
                original_content=SAMPLE_PYTHON_CODE,
                modification_request="Add a function to calculate the difference between two numbers"
            )
            
            assert result.success
            assert "calculate_difference" in result.modified_files["calculator.py"]
    
    @pytest.mark.asyncio
    async def test_modify_function_scenario(self):
        """Test modifying an existing function."""
        modifier = CodeModifier()
        
        with patch('utils.code_modifier.ask_llm') as mock_llm:
            mock_llm.side_effect = [
                '''```json
                {
                    "changes": [{
                        "type": "modify_function",
                        "target": "calculate_sum",
                        "action": "Add input validation",
                        "new_code": "def calculate_sum(a, b):\\n    if not isinstance(a, (int, float)):\\n        raise TypeError('Invalid input')\\n    return a + b"
                    }],
                    "rationale": "Improving input validation",
                    "risk_level": "medium",
                    "affected_functions": ["calculate_sum"],
                    "affected_classes": [],
                    "dependencies": []
                }
                ```''',
                MODIFIED_PYTHON_CODE
            ]
            
            result = await modifier.modify_code(
                file_path="calculator.py",
                original_content=SAMPLE_PYTHON_CODE,
                modification_request="Add input validation to calculate_sum function"
            )
            
            assert result.success
            assert "TypeError" in result.modified_files["calculator.py"]


# Import json for test
import json


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
