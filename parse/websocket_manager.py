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
        Accepts a new WebSocket connection and adds it to the active list.
        """
        await websocket.accept()
        with self.lock:
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Removes a WebSocket connection from the active list.
        """
        with self.lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast_message(self, message: Dict[str, Any]):
        """
        Broadcasts a JSON-serialized message to all connected clients.

        If a connection is dead, it is safely removed from the list.
        """
        if not self.active_connections:
            return
            
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting message to a client: {e}")
                disconnected_clients.append(connection)
        
        # Clean up any connections that failed during broadcast
        if disconnected_clients:
            with self.lock:
                for client in disconnected_clients:
                    if client in self.active_connections:
                        self.active_connections.remove(client)