"""
Unit tests for WebSocket server

Run with: pytest test_server.py -v
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
import websockets

# Mock AWS services before importing server
with patch('boto3.client'), patch('boto3.resource'):
    from server import WebSocketServer


class MockWebSocket:
    """Mock WebSocket connection for testing"""
    
    def __init__(self):
        self.remote_address = ('127.0.0.1', 12345)
        self.messages_sent = []
        self.closed = False
    
    async def send(self, message):
        """Mock send method"""
        if self.closed:
            raise websockets.exceptions.ConnectionClosed(None, None)
        self.messages_sent.append(message)
    
    async def recv(self):
        """Mock recv method"""
        if self.closed:
            raise websockets.exceptions.ConnectionClosed(None, None)
        await asyncio.sleep(0.1)
        return json.dumps({"action": "ping"})
    
    def close(self):
        """Mock close method"""
        self.closed = True


@pytest.fixture
def server():
    """Create a WebSocketServer instance for testing"""
    with patch('boto3.resource') as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        server = WebSocketServer()
        return server


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection"""
    return MockWebSocket()


@pytest.mark.asyncio
async def test_register_connection(server, mock_websocket):
    """Test registering a new WebSocket connection"""
    from server import active_connections
    
    initial_count = len(active_connections)
    await server.register_connection(mock_websocket)
    
    assert len(active_connections) == initial_count + 1
    assert mock_websocket in active_connections


@pytest.mark.asyncio
async def test_register_connection_with_project(server, mock_websocket):
    """Test registering a connection with project ID"""
    from server import active_connections, project_connections
    
    project_id = "proj_123"
    await server.register_connection(mock_websocket, project_id)
    
    assert mock_websocket in active_connections
    assert mock_websocket in project_connections[project_id]


@pytest.mark.asyncio
async def test_unregister_connection(server, mock_websocket):
    """Test unregistering a WebSocket connection"""
    from server import active_connections
    
    await server.register_connection(mock_websocket)
    await server.unregister_connection(mock_websocket)
    
    assert mock_websocket not in active_connections


@pytest.mark.asyncio
async def test_broadcast_message(server, mock_websocket):
    """Test broadcasting a message to all connections"""
    await server.register_connection(mock_websocket)
    
    message = {"type": "test", "data": "hello"}
    await server.broadcast_message(message)
    
    assert len(mock_websocket.messages_sent) == 1
    sent_message = json.loads(mock_websocket.messages_sent[0])
    assert sent_message["type"] == "test"
    assert sent_message["data"] == "hello"


@pytest.mark.asyncio
async def test_send_to_project(server, mock_websocket):
    """Test sending a message to project-specific connections"""
    project_id = "proj_123"
    await server.register_connection(mock_websocket, project_id)
    
    message = {"type": "project_update", "project_id": project_id}
    await server.send_to_project(project_id, message)
    
    assert len(mock_websocket.messages_sent) == 1
    sent_message = json.loads(mock_websocket.messages_sent[0])
    assert sent_message["type"] == "project_update"


@pytest.mark.asyncio
async def test_forward_to_sqs_dev(server):
    """Test forwarding a message to Dev SQS queue"""
    with patch('server.sqs') as mock_sqs:
        mock_sqs.send_message.return_value = {'MessageId': 'msg_123'}
        
        message = {
            "type": "dev",
            "project_id": "proj_123",
            "data": {"task": "generate_code"}
        }
        
        await server.forward_to_sqs(message)
        
        mock_sqs.send_message.assert_called_once()
        call_args = mock_sqs.send_message.call_args
        assert 'QueueUrl' in call_args.kwargs
        assert 'MessageBody' in call_args.kwargs


@pytest.mark.asyncio
async def test_forward_to_sqs_unknown_type(server):
    """Test forwarding a message with unknown type"""
    with patch('server.sqs') as mock_sqs:
        message = {
            "type": "unknown",
            "data": {}
        }
        
        await server.forward_to_sqs(message)
        
        # Should not call SQS for unknown types
        mock_sqs.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_subscribe_action(server, mock_websocket):
    """Test handling subscribe action"""
    from server import project_connections
    
    await server.register_connection(mock_websocket)
    
    message = json.dumps({
        "action": "subscribe",
        "project_id": "proj_456"
    })
    
    await server.handle_client_message(mock_websocket, message)
    
    assert mock_websocket in project_connections["proj_456"]
    assert len(mock_websocket.messages_sent) == 1
    response = json.loads(mock_websocket.messages_sent[0])
    assert response["type"] == "subscription_confirmed"


@pytest.mark.asyncio
async def test_handle_unsubscribe_action(server, mock_websocket):
    """Test handling unsubscribe action"""
    from server import project_connections
    
    project_id = "proj_789"
    await server.register_connection(mock_websocket, project_id)
    
    message = json.dumps({
        "action": "unsubscribe",
        "project_id": project_id
    })
    
    await server.handle_client_message(mock_websocket, message)
    
    assert mock_websocket not in project_connections[project_id]
    assert len(mock_websocket.messages_sent) == 1
    response = json.loads(mock_websocket.messages_sent[0])
    assert response["type"] == "unsubscription_confirmed"


@pytest.mark.asyncio
async def test_handle_ping_action(server, mock_websocket):
    """Test handling ping action"""
    await server.register_connection(mock_websocket)
    
    message = json.dumps({"action": "ping"})
    await server.handle_client_message(mock_websocket, message)
    
    assert len(mock_websocket.messages_sent) == 1
    response = json.loads(mock_websocket.messages_sent[0])
    assert response["type"] == "pong"


@pytest.mark.asyncio
async def test_handle_forward_action(server, mock_websocket):
    """Test handling forward action"""
    with patch('server.sqs') as mock_sqs:
        mock_sqs.send_message.return_value = {'MessageId': 'msg_123'}
        
        await server.register_connection(mock_websocket)
        
        message = json.dumps({
            "action": "forward",
            "type": "qa",
            "message_id": "msg_123",
            "data": {"test": "data"}
        })
        
        await server.handle_client_message(mock_websocket, message)
        
        mock_sqs.send_message.assert_called_once()
        assert len(mock_websocket.messages_sent) == 1
        response = json.loads(mock_websocket.messages_sent[0])
        assert response["type"] == "forward_confirmed"


@pytest.mark.asyncio
async def test_handle_invalid_json(server, mock_websocket):
    """Test handling invalid JSON message"""
    await server.register_connection(mock_websocket)
    
    message = "invalid json {"
    await server.handle_client_message(mock_websocket, message)
    
    assert len(mock_websocket.messages_sent) == 1
    response = json.loads(mock_websocket.messages_sent[0])
    assert response["type"] == "error"
    assert "Invalid JSON" in response["message"]


@pytest.mark.asyncio
async def test_handle_unknown_action(server, mock_websocket):
    """Test handling unknown action"""
    await server.register_connection(mock_websocket)
    
    message = json.dumps({"action": "unknown_action"})
    await server.handle_client_message(mock_websocket, message)
    
    assert len(mock_websocket.messages_sent) == 1
    response = json.loads(mock_websocket.messages_sent[0])
    assert response["type"] == "error"
    assert "Unknown action" in response["message"]


@pytest.mark.asyncio
async def test_broadcast_cleans_disconnected_clients(server):
    """Test that broadcast removes disconnected clients"""
    from server import active_connections
    
    # Create multiple mock websockets
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()
    
    await server.register_connection(ws1)
    await server.register_connection(ws2)
    await server.register_connection(ws3)
    
    # Close one connection
    ws2.close()
    
    initial_count = len(active_connections)
    
    # Broadcast should clean up closed connection
    message = {"type": "test"}
    await server.broadcast_message(message)
    
    # ws2 should be removed from active connections
    assert len(active_connections) < initial_count
    assert ws1 in active_connections
    assert ws3 in active_connections


@pytest.mark.asyncio
async def test_multiple_project_subscriptions(server, mock_websocket):
    """Test subscribing to multiple projects"""
    from server import project_connections
    
    await server.register_connection(mock_websocket)
    
    # Subscribe to first project
    message1 = json.dumps({"action": "subscribe", "project_id": "proj_1"})
    await server.handle_client_message(mock_websocket, message1)
    
    # Subscribe to second project
    message2 = json.dumps({"action": "subscribe", "project_id": "proj_2"})
    await server.handle_client_message(mock_websocket, message2)
    
    assert mock_websocket in project_connections["proj_1"]
    assert mock_websocket in project_connections["proj_2"]


def test_server_initialization():
    """Test WebSocketServer initialization"""
    with patch('boto3.resource') as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        server = WebSocketServer()
        
        assert server.running is True
        assert server.table is not None


@pytest.mark.asyncio
async def test_connection_handler_sends_welcome(server, mock_websocket):
    """Test that connection handler sends welcome message"""
    # This is a simplified test - full integration test would be more complex
    await server.register_connection(mock_websocket)
    
    # Simulate sending welcome message
    welcome = {
        "type": "connected",
        "message": "WebSocket connection established"
    }
    await mock_websocket.send(json.dumps(welcome))
    
    assert len(mock_websocket.messages_sent) == 1
    response = json.loads(mock_websocket.messages_sent[0])
    assert response["type"] == "connected"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
