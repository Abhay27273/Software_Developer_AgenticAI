"""
Tests for Dev Agent code modification integration.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import tempfile
import shutil

from agents.dev_agent import DevAgent
from utils.code_modifier import ModificationResult
from parse.websocket_manager import WebSocketManager


SAMPLE_CODE = '''
def hello_world():
    """Print hello world."""
    print("Hello, World!")

def goodbye_world():
    """Print goodbye world."""
    print("Goodbye, World!")
'''

MODIFIED_CODE = '''
def hello_world(name="World"):
    """Print hello with custom name."""
    print(f"Hello, {name}!")

def goodbye_world(name="World"):
    """Print goodbye with custom name."""
    print(f"Goodbye, {name}!")

def greet(name, greeting="Hello"):
    """Generic greeting function."""
    print(f"{greeting}, {name}!")
'''


class TestDevAgentCodeModification:
    """Test suite for Dev Agent code modification functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """Create a mock WebSocket manager."""
        manager = Mock(spec=WebSocketManager)
        manager.broadcast_message = AsyncMock()
        return manager
    
    @pytest.fixture
    def dev_agent(self, mock_websocket_manager):
        """Create a Dev Agent instance for testing."""
        agent = DevAgent(websocket_manager=mock_websocket_manager)
        return agent
    
    @pytest.fixture
    def test_file(self, temp_dir):
        """Create a test file with sample code."""
        test_file = temp_dir / "test_module.py"
        test_file.write_text(SAMPLE_CODE, encoding="utf-8")
        return test_file
    
    @pytest.mark.asyncio
    async def test_modify_code_success(self, dev_agent, test_file, mock_websocket_manager):
        """Test successful code modification through Dev Agent."""
        # Mock the CodeModifier
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            mock_modify.return_value = ModificationResult(
                success=True,
                modified_files={str(test_file): MODIFIED_CODE},
                diff="+ def greet(name, greeting='Hello'):\n+     print(f'{greeting}, {name}!')",
                validation_errors=[],
                rollback_available=True,
                metadata={"timestamp": "2024-01-01"}
            )
            
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(test_file),
                modification_request="Add a generic greet function and make functions accept name parameter"
            )
            
            # Verify result
            assert result.success
            assert str(test_file) in result.modified_files
            assert result.diff != ""
            
            # Verify file was modified
            modified_content = test_file.read_text(encoding="utf-8")
            assert modified_content == MODIFIED_CODE
            
            # Verify backup was created
            backup_file = test_file.with_suffix(test_file.suffix + ".backup")
            assert backup_file.exists()
            assert backup_file.read_text(encoding="utf-8") == SAMPLE_CODE
            
            # Verify WebSocket messages were sent
            assert mock_websocket_manager.broadcast_message.call_count >= 3
            
            # Check for specific message types
            calls = mock_websocket_manager.broadcast_message.call_args_list
            message_types = [call[0][0]["type"] for call in calls]
            
            assert "code_modification_started" in message_types
            assert "code_modification_analyzing" in message_types
            assert "code_modification_completed" in message_types
    
    @pytest.mark.asyncio
    async def test_modify_code_file_not_found(self, dev_agent, temp_dir, mock_websocket_manager):
        """Test code modification with non-existent file."""
        non_existent_file = temp_dir / "non_existent.py"
        
        result = await dev_agent.modify_code(
            project_id="test_project",
            file_path=str(non_existent_file),
            modification_request="Modify non-existent file"
        )
        
        # Verify result indicates failure
        assert not result.success
        assert len(result.validation_errors) > 0
        assert "File not found" in result.validation_errors[0]
        
        # Verify error message was sent
        calls = mock_websocket_manager.broadcast_message.call_args_list
        message_types = [call[0][0]["type"] for call in calls]
        assert "code_modification_failed" in message_types
    
    @pytest.mark.asyncio
    async def test_modify_code_modification_failure(self, dev_agent, test_file, mock_websocket_manager):
        """Test code modification when modification fails."""
        original_content = test_file.read_text(encoding="utf-8")
        
        # Mock the CodeModifier to return failure
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            mock_modify.return_value = ModificationResult(
                success=False,
                modified_files={},
                diff="",
                validation_errors=["Syntax error in modified code"],
                rollback_available=True,
                metadata={"error": "Modification failed"}
            )
            
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(test_file),
                modification_request="Break the code"
            )
            
            # Verify result indicates failure
            assert not result.success
            assert len(result.validation_errors) > 0
            
            # Verify file was restored to original content
            current_content = test_file.read_text(encoding="utf-8")
            assert current_content == original_content
            
            # Verify failure message was sent
            calls = mock_websocket_manager.broadcast_message.call_args_list
            message_types = [call[0][0]["type"] for call in calls]
            assert "code_modification_failed" in message_types
    
    @pytest.mark.asyncio
    async def test_modify_code_with_relative_path(self, dev_agent, temp_dir, mock_websocket_manager):
        """Test code modification with relative file path."""
        # Create a file in a subdirectory
        subdir = temp_dir / "src"
        subdir.mkdir()
        test_file = subdir / "module.py"
        test_file.write_text(SAMPLE_CODE, encoding="utf-8")
        
        # Mock the CodeModifier
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            mock_modify.return_value = ModificationResult(
                success=True,
                modified_files={str(test_file): MODIFIED_CODE},
                diff="+ new code",
                validation_errors=[],
                rollback_available=True,
                metadata={}
            )
            
            # Use relative path
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(test_file),
                modification_request="Modify the code"
            )
            
            assert result.success
    
    @pytest.mark.asyncio
    async def test_modify_code_exception_handling(self, dev_agent, test_file, mock_websocket_manager):
        """Test exception handling during code modification."""
        # Mock the CodeModifier to raise an exception
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            mock_modify.side_effect = Exception("Unexpected error")
            
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(test_file),
                modification_request="Cause an error"
            )
            
            # Verify result indicates failure
            assert not result.success
            assert len(result.validation_errors) > 0
            assert "Unexpected error" in result.validation_errors[0]
            
            # Verify error message was sent
            calls = mock_websocket_manager.broadcast_message.call_args_list
            message_types = [call[0][0]["type"] for call in calls]
            assert "code_modification_failed" in message_types
    
    @pytest.mark.asyncio
    async def test_modify_code_diff_generation(self, dev_agent, test_file, mock_websocket_manager):
        """Test that diff is properly generated and sent."""
        expected_diff = """--- a/test_module.py
+++ b/test_module.py
@@ -1,5 +1,8 @@
-def hello_world():
-    print("Hello, World!")
+def hello_world(name="World"):
+    print(f"Hello, {name}!")
+
+def greet(name, greeting="Hello"):
+    print(f"{greeting}, {name}!")
"""
        
        # Mock the CodeModifier
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            mock_modify.return_value = ModificationResult(
                success=True,
                modified_files={str(test_file): MODIFIED_CODE},
                diff=expected_diff,
                validation_errors=[],
                rollback_available=True,
                metadata={}
            )
            
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(test_file),
                modification_request="Modify functions"
            )
            
            assert result.success
            assert result.diff == expected_diff
            
            # Verify diff was sent via WebSocket
            calls = mock_websocket_manager.broadcast_message.call_args_list
            diff_messages = [
                call[0][0] for call in calls 
                if call[0][0].get("type") == "code_modification_diff"
            ]
            
            assert len(diff_messages) > 0
            assert diff_messages[0]["content"] == expected_diff
    
    @pytest.mark.asyncio
    async def test_modify_code_backup_creation(self, dev_agent, test_file, mock_websocket_manager):
        """Test that backup file is created before modification."""
        original_content = test_file.read_text(encoding="utf-8")
        
        # Mock the CodeModifier
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            mock_modify.return_value = ModificationResult(
                success=True,
                modified_files={str(test_file): MODIFIED_CODE},
                diff="+ changes",
                validation_errors=[],
                rollback_available=True,
                metadata={}
            )
            
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(test_file),
                modification_request="Modify the code"
            )
            
            # Verify backup file exists
            backup_file = test_file.with_suffix(test_file.suffix + ".backup")
            assert backup_file.exists()
            
            # Verify backup contains original content
            backup_content = backup_file.read_text(encoding="utf-8")
            assert backup_content == original_content
            
            # Verify backup path was sent in completion message
            calls = mock_websocket_manager.broadcast_message.call_args_list
            completion_messages = [
                call[0][0] for call in calls 
                if call[0][0].get("type") == "code_modification_completed"
            ]
            
            assert len(completion_messages) > 0
            assert "backup_path" in completion_messages[0]


class TestDevAgentCodeModificationIntegration:
    """Integration tests for Dev Agent code modification with real scenarios."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        project_dir = Path(temp_dir) / "test_project"
        project_dir.mkdir()
        
        # Create a simple project structure
        src_dir = project_dir / "src"
        src_dir.mkdir()
        
        # Create main.py
        main_file = src_dir / "main.py"
        main_file.write_text('''
def main():
    print("Hello from main")

if __name__ == "__main__":
    main()
''', encoding="utf-8")
        
        # Create utils.py
        utils_file = src_dir / "utils.py"
        utils_file.write_text('''
def helper_function(x):
    return x * 2
''', encoding="utf-8")
        
        yield project_dir
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_modify_multiple_files_scenario(self, temp_project_dir):
        """Test modifying multiple files in a project."""
        mock_ws = Mock(spec=WebSocketManager)
        mock_ws.broadcast_message = AsyncMock()
        
        dev_agent = DevAgent(websocket_manager=mock_ws)
        
        main_file = temp_project_dir / "src" / "main.py"
        
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            mock_modify.return_value = ModificationResult(
                success=True,
                modified_files={str(main_file): "# Modified main.py"},
                diff="+ # Modified main.py",
                validation_errors=[],
                rollback_available=True,
                metadata={}
            )
            
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(main_file),
                modification_request="Add logging to main function"
            )
            
            assert result.success
    
    @pytest.mark.asyncio
    async def test_modify_code_preserves_project_structure(self, temp_project_dir):
        """Test that code modification preserves project structure."""
        mock_ws = Mock(spec=WebSocketManager)
        mock_ws.broadcast_message = AsyncMock()
        
        dev_agent = DevAgent(websocket_manager=mock_ws)
        
        utils_file = temp_project_dir / "src" / "utils.py"
        original_content = utils_file.read_text(encoding="utf-8")
        
        with patch.object(dev_agent.code_modifier, 'modify_code') as mock_modify:
            modified_content = original_content + "\n\ndef new_helper():\n    pass\n"
            mock_modify.return_value = ModificationResult(
                success=True,
                modified_files={str(utils_file): modified_content},
                diff="+ def new_helper():\n+     pass",
                validation_errors=[],
                rollback_available=True,
                metadata={}
            )
            
            result = await dev_agent.modify_code(
                project_id="test_project",
                file_path=str(utils_file),
                modification_request="Add a new helper function"
            )
            
            assert result.success
            
            # Verify project structure is intact
            assert (temp_project_dir / "src").exists()
            assert (temp_project_dir / "src" / "main.py").exists()
            assert (temp_project_dir / "src" / "utils.py").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
