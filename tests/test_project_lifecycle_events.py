"""
Tests for Project Lifecycle WebSocket Events (Task 9.1)

This module tests the WebSocket event broadcasting for project lifecycle events:
- project_created
- project_updated
- project_deleted
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import WebSocket

from parse.websocket_manager import WebSocketManager
from models.project_context import ProjectContext, ProjectType, ProjectStatus


class TestProjectLifecycleEvents:
    """Test suite for project lifecycle WebSocket events."""
    
    @pytest.fixture
    def websocket_manager(self):
        """Create a WebSocketManager instance for testing."""
        return WebSocketManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket connection."""
        ws = Mock(spec=WebSocket)
        ws.client = Mock()
        ws.client.host = "127.0.0.1"
        ws.client.port = 8000
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        return ws
    
    @pytest.fixture
    def sample_project_data(self):
        """Create sample project data for testing."""
        return {
            "id": "proj_20231119_120000",
            "name": "Test Project",
            "type": "api",
            "status": "created",
            "owner_id": "test_user",
            "description": "A test project",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @pytest.mark.asyncio
    async def test_broadcast_project_created(self, websocket_manager, mock_websocket, sample_project_data):
        """Test broadcasting project_created event."""
        # Connect mock websocket
        await websocket_manager.connect(mock_websocket)
        
        # Broadcast project_created event
        await websocket_manager.broadcast_project_created(sample_project_data)
        
        # Verify the event was sent
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        
        # Verify event structure
        assert call_args["event_type"] == "project_created"
        assert "timestamp" in call_args
        assert "data" in call_args
        
        # Verify event data
        data = call_args["data"]
        assert data["project_id"] == sample_project_data["id"]
        assert data["name"] == sample_project_data["name"]
        assert data["type"] == sample_project_data["type"]
        assert data["status"] == sample_project_data["status"]
        assert data["owner_id"] == sample_project_data["owner_id"]
    
    @pytest.mark.asyncio
    async def test_broadcast_project_updated(self, websocket_manager, mock_websocket, sample_project_data):
        """Test broadcasting project_updated event."""
        # Connect mock websocket
        await websocket_manager.connect(mock_websocket)
        
        # Updated fields
        updated_fields = ["name", "status"]
        
        # Broadcast project_updated event
        await websocket_manager.broadcast_project_updated(sample_project_data, updated_fields)
        
        # Verify the event was sent
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        
        # Verify event structure
        assert call_args["event_type"] == "project_updated"
        assert "timestamp" in call_args
        assert "data" in call_args
        
        # Verify event data
        data = call_args["data"]
        assert data["project_id"] == sample_project_data["id"]
        assert data["name"] == sample_project_data["name"]
        assert data["updated_fields"] == updated_fields
    
    @pytest.mark.asyncio
    async def test_broadcast_project_deleted(self, websocket_manager, mock_websocket):
        """Test broadcasting project_deleted event."""
        # Connect mock websocket
        await websocket_manager.connect(mock_websocket)
        
        project_id = "proj_20231119_120000"
        project_name = "Test Project"
        
        # Broadcast project_deleted event
        await websocket_manager.broadcast_project_deleted(project_id, project_name)
        
        # Verify the event was sent
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        
        # Verify event structure
        assert call_args["event_type"] == "project_deleted"
        assert "timestamp" in call_args
        assert "data" in call_args
        
        # Verify event data
        data = call_args["data"]
        assert data["project_id"] == project_id
        assert data["name"] == project_name
    
    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, websocket_manager, sample_project_data):
        """Test broadcasting events to multiple connected clients."""
        # Create multiple mock websockets
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.client = Mock(host="127.0.0.1", port=8001)
        mock_ws1.send_json = AsyncMock()
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.client = Mock(host="127.0.0.1", port=8002)
        mock_ws2.send_json = AsyncMock()
        
        # Connect both websockets
        await websocket_manager.connect(mock_ws1)
        await websocket_manager.connect(mock_ws2)
        
        # Broadcast event
        await websocket_manager.broadcast_project_created(sample_project_data)
        
        # Verify both clients received the event
        assert mock_ws1.send_json.called
        assert mock_ws2.send_json.called
    
    @pytest.mark.asyncio
    async def test_no_broadcast_when_no_clients(self, websocket_manager, sample_project_data):
        """Test that broadcasting with no connected clients doesn't raise errors."""
        # Broadcast without any connected clients
        await websocket_manager.broadcast_project_created(sample_project_data)
        
        # Should complete without errors
        assert True
    
    @pytest.mark.asyncio
    async def test_event_with_minimal_data(self, websocket_manager, mock_websocket):
        """Test broadcasting events with minimal required data."""
        # Connect mock websocket
        await websocket_manager.connect(mock_websocket)
        
        # Minimal project data
        minimal_data = {
            "id": "proj_123",
            "name": "Minimal Project"
        }
        
        # Should not raise errors
        await websocket_manager.broadcast_project_created(minimal_data)
        
        assert mock_websocket.send_json.called


class TestAPIRoutesIntegration:
    """Test integration of WebSocket events with API routes."""
    
    @pytest.mark.asyncio
    async def test_set_websocket_manager(self):
        """Test setting the WebSocket manager in API routes."""
        from api.routes import set_websocket_manager
        
        manager = WebSocketManager()
        set_websocket_manager(manager)
        
        # Import after setting to get the updated value
        from api import routes
        assert routes.websocket_manager is not None
        assert routes.websocket_manager == manager


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
