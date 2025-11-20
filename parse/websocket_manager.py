import json
import logging
import threading
from typing import Dict, List, Any

from fastapi import WebSocket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time streaming.
    This class handles connecting, disconnecting, and broadcasting messages
    to all active WebSocket clients. It is thread-safe.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        """
        Adds a WebSocket connection to the active list.
        The connection should already be accepted before calling this method.
        """
        with self.lock:
            self.active_connections.append(websocket)
            logger.info(f"WebSocket connected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """
        Removes a WebSocket connection from the active list.
        """
        with self.lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                logger.info(f"WebSocket disconnected: {websocket.client.host}:{websocket.client.port}. Total active connections: {len(self.active_connections)}")
            else:
                logger.warning(f"Attempted to disconnect a non-active WebSocket: {websocket.client.host}:{websocket.client.port}")


    async def broadcast_message(self, message: Dict[str, Any]):
        """
        Broadcasts a JSON-serialized dictionary message to all connected clients.
        Useful for general events that all clients might be interested in.
        If a connection is dead, it is safely removed from the list.
        """
        if not self.active_connections:
            return
            
        disconnected_clients = []
        # Create a copy to iterate safely while modifying the original list
        connections_copy = self.active_connections[:] 
        for connection in connections_copy:
            try:
                # Use send_json for dictionary messages
                await connection.send_json(message) 
            except Exception as e:
                logger.error(f"Error broadcasting JSON message to client {connection.client.host}:{connection.client.port}: {e}")
                disconnected_clients.append(connection)
        
        # Clean up any connections that failed during broadcast
        if disconnected_clients:
            with self.lock:
                for client in disconnected_clients:
                    if client in self.active_connections:
                        self.active_connections.remove(client)
                logger.info(f"Cleaned up {len(disconnected_clients)} disconnected clients during broadcast. Remaining: {len(self.active_connections)}")


    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Sends a JSON-serialized dictionary message to a specific WebSocket client.
        
        Args:
            message: The dictionary message to send (will be converted to JSON).
            websocket: The specific WebSocket connection to send the message to.
        """
        if websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending personal JSON message to client {websocket.client.host}:{websocket.client.port}: {e}")
                self.disconnect(websocket)
        else:
            logger.warning(f"Attempted to send personal message to a non-active WebSocket: {websocket.client.host}:{websocket.client.port}")

    async def stream_chunk(self, chunk: str, websocket: WebSocket):
        """
        Sends a raw string chunk of data to a specific WebSocket client.
        This is optimized for streaming text from LLMs.
        Args:
            chunk: The string chunk of data to send.
            websocket: The specific WebSocket connection to send the chunk to.
        """
        if websocket in self.active_connections:
            try:
                await websocket.send_text(chunk)
            except Exception as e:
                logger.error(f"Error streaming chunk to client {websocket.client.host}:{websocket.client.port}: {e}")
                self.disconnect(websocket)
        else:
            logger.warning(f"Attempted to stream chunk to a non-active WebSocket: {websocket.client.host}:{websocket.client.port}")

    # ============================================================================
    # PROJECT LIFECYCLE EVENTS (Task 9.1)
    # ============================================================================

    async def broadcast_project_created(self, project_data: Dict[str, Any]):
        """
        Broadcast a project_created event to all connected clients.
        
        Args:
            project_data: Dictionary containing project details (id, name, type, status, etc.)
        
        Requirements: 1.1
        """
        event = {
            "event_type": "project_created",
            "timestamp": project_data.get("created_at", ""),
            "data": {
                "project_id": project_data.get("id"),
                "name": project_data.get("name"),
                "type": project_data.get("type"),
                "status": project_data.get("status"),
                "owner_id": project_data.get("owner_id"),
                "description": project_data.get("description", "")
            }
        }
        
        logger.info(f"Broadcasting project_created event for project: {project_data.get('id')}")
        await self.broadcast_message(event)

    async def broadcast_project_updated(self, project_data: Dict[str, Any], updated_fields: list = None):
        """
        Broadcast a project_updated event to all connected clients.
        
        Args:
            project_data: Dictionary containing updated project details
            updated_fields: List of field names that were updated (optional)
        
        Requirements: 1.1
        """
        event = {
            "event_type": "project_updated",
            "timestamp": project_data.get("updated_at", ""),
            "data": {
                "project_id": project_data.get("id"),
                "name": project_data.get("name"),
                "type": project_data.get("type"),
                "status": project_data.get("status"),
                "updated_fields": updated_fields or [],
                "description": project_data.get("description", "")
            }
        }
        
        logger.info(f"Broadcasting project_updated event for project: {project_data.get('id')}")
        await self.broadcast_message(event)

    async def broadcast_project_deleted(self, project_id: str, project_name: str = None):
        """
        Broadcast a project_deleted event to all connected clients.
        
        Args:
            project_id: ID of the deleted project
            project_name: Name of the deleted project (optional)
        
        Requirements: 1.1
        """
        from datetime import datetime
        
        event = {
            "event_type": "project_deleted",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "project_id": project_id,
                "name": project_name
            }
        }
        
        logger.info(f"Broadcasting project_deleted event for project: {project_id}")
        await self.broadcast_message(event)