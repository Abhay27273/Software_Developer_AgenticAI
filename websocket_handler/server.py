"""
WebSocket Server for ECS Fargate Deployment

This server handles persistent WebSocket connections for real-time updates
in the AI-powered Software Development Agentic System. It runs as a container
in ECS Fargate and integrates with SQS for message forwarding.

Requirements: 1.7
"""

import asyncio
import json
import logging
import os
import signal
import sys
import http
from datetime import datetime
from typing import Dict, Set, Any
from collections import defaultdict

import boto3
import websockets
from websockets.server import WebSocketServerProtocol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS clients
sqs = boto3.client('sqs', region_name=os.getenv('AWS_REGION', 'us-east-1'))
dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))

# Environment variables
SQS_QUEUE_URL_PM = os.getenv('SQS_QUEUE_URL_PM')
SQS_QUEUE_URL_DEV = os.getenv('SQS_QUEUE_URL_DEV')
SQS_QUEUE_URL_QA = os.getenv('SQS_QUEUE_URL_QA')
SQS_QUEUE_URL_OPS = os.getenv('SQS_QUEUE_URL_OPS')
DYNAMODB_TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'agenticai-data')
WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', '8080'))
WEBSOCKET_HOST = os.getenv('WEBSOCKET_HOST', '0.0.0.0')

# Connection management
active_connections: Set[WebSocketServerProtocol] = set()
project_connections: Dict[str, Set[WebSocketServerProtocol]] = defaultdict(set)
connection_lock = asyncio.Lock()


class WebSocketServer:
    """
    WebSocket server for handling real-time connections and message forwarding.
    """
    
    def __init__(self):
        self.running = True
        self.table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    async def register_connection(self, websocket: WebSocketServerProtocol, project_id: str = None):
        """
        Register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            project_id: Optional project ID to associate with this connection
        """
        async with connection_lock:
            active_connections.add(websocket)
            if project_id:
                project_connections[project_id].add(websocket)
            
            client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            logger.info(f"WebSocket connected: {client_info}. Total connections: {len(active_connections)}")
            
            if project_id:
                logger.info(f"Connection associated with project: {project_id}")
    
    async def unregister_connection(self, websocket: WebSocketServerProtocol):
        """
        Unregister a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        async with connection_lock:
            active_connections.discard(websocket)
            
            # Remove from project-specific connections
            for project_id, connections in list(project_connections.items()):
                connections.discard(websocket)
                if not connections:
                    del project_connections[project_id]
            
            client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            logger.info(f"WebSocket disconnected: {client_info}. Total connections: {len(active_connections)}")
    
    async def broadcast_message(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: Dictionary message to broadcast
        """
        if not active_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for connection in active_connections.copy():
            try:
                await connection.send(message_json)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection.remote_address}: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        if disconnected:
            async with connection_lock:
                for conn in disconnected:
                    active_connections.discard(conn)
                    for connections in project_connections.values():
                        connections.discard(conn)
            logger.info(f"Cleaned up {len(disconnected)} disconnected clients")
    
    async def send_to_project(self, project_id: str, message: Dict[str, Any]):
        """
        Send a message to all clients connected to a specific project.
        
        Args:
            project_id: The project ID
            message: Dictionary message to send
        """
        connections = project_connections.get(project_id, set())
        if not connections:
            logger.debug(f"No connections for project {project_id}")
            return
        
        message_json = json.dumps(message)
        disconnected = set()
        
        for connection in connections.copy():
            try:
                await connection.send(message_json)
            except Exception as e:
                logger.error(f"Error sending to {connection.remote_address}: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        if disconnected:
            async with connection_lock:
                for conn in disconnected:
                    active_connections.discard(conn)
                    connections.discard(conn)
            logger.info(f"Cleaned up {len(disconnected)} disconnected clients from project {project_id}")
    
    async def forward_to_sqs(self, message: Dict[str, Any]):
        """
        Forward a message to the appropriate SQS queue based on message type.
        
        Args:
            message: Dictionary message to forward
        """
        message_type = message.get('type', '').lower()
        queue_url = None
        
        # Determine target queue based on message type
        if message_type in ['plan', 'planning', 'pm']:
            queue_url = SQS_QUEUE_URL_PM
        elif message_type in ['code', 'develop', 'dev']:
            queue_url = SQS_QUEUE_URL_DEV
        elif message_type in ['test', 'qa', 'quality']:
            queue_url = SQS_QUEUE_URL_QA
        elif message_type in ['deploy', 'ops', 'operations']:
            queue_url = SQS_QUEUE_URL_OPS
        else:
            logger.warning(f"Unknown message type: {message_type}")
            return
        
        if not queue_url:
            logger.error(f"No SQS queue URL configured for message type: {message_type}")
            return
        
        try:
            response = sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message),
                MessageAttributes={
                    'MessageType': {
                        'StringValue': message_type,
                        'DataType': 'String'
                    },
                    'Timestamp': {
                        'StringValue': datetime.utcnow().isoformat(),
                        'DataType': 'String'
                    }
                }
            )
            logger.info(f"Message forwarded to SQS: {response['MessageId']}")
        except Exception as e:
            logger.error(f"Error forwarding message to SQS: {e}")
            raise
    
    async def handle_client_message(self, websocket: WebSocketServerProtocol, message: str):
        """
        Handle incoming message from a client.
        
        Args:
            websocket: The WebSocket connection
            message: The message string
        """
        try:
            data = json.loads(message)
            action = data.get('action', '')
            
            if action == 'subscribe':
                # Subscribe to project updates
                project_id = data.get('project_id')
                if project_id:
                    async with connection_lock:
                        project_connections[project_id].add(websocket)
                    logger.info(f"Client subscribed to project: {project_id}")
                    await websocket.send(json.dumps({
                        'type': 'subscription_confirmed',
                        'project_id': project_id
                    }))
            
            elif action == 'unsubscribe':
                # Unsubscribe from project updates
                project_id = data.get('project_id')
                if project_id:
                    async with connection_lock:
                        project_connections[project_id].discard(websocket)
                    logger.info(f"Client unsubscribed from project: {project_id}")
                    await websocket.send(json.dumps({
                        'type': 'unsubscription_confirmed',
                        'project_id': project_id
                    }))
            
            elif action == 'ping':
                # Respond to ping with pong
                await websocket.send(json.dumps({'type': 'pong'}))
            
            elif action == 'forward':
                # Forward message to SQS
                await self.forward_to_sqs(data)
                await websocket.send(json.dumps({
                    'type': 'forward_confirmed',
                    'message_id': data.get('message_id')
                }))
            
            else:
                logger.warning(f"Unknown action: {action}")
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': f'Unknown action: {action}'
                }))
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def connection_handler(self, websocket: WebSocketServerProtocol, path: str):
        """
        Handle a WebSocket connection lifecycle.
        
        Args:
            websocket: The WebSocket connection
            path: The connection path
        """
        # Extract project_id from path if present (e.g., /ws?project_id=123)
        project_id = None
        if '?' in path:
            query_string = path.split('?')[1]
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            project_id = params.get('project_id')
        
        await self.register_connection(websocket, project_id)
        
        try:
            # Send welcome message
            await websocket.send(json.dumps({
                'type': 'connected',
                'message': 'WebSocket connection established',
                'timestamp': datetime.utcnow().isoformat()
            }))
            
            # Handle incoming messages
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed normally: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error in connection handler: {e}")
        finally:
            await self.unregister_connection(websocket)
    
    async def sqs_poller(self):
        """
        Poll SQS queues for messages to broadcast to WebSocket clients.
        This runs as a background task.
        """
        # For now, we'll use DynamoDB Streams or EventBridge for push notifications
        # This is a placeholder for future SQS polling implementation
        logger.info("SQS poller started (placeholder)")
        
        while self.running:
            await asyncio.sleep(5)
    
    async def health_check_handler(self, path, request_headers):
        """
        Health check endpoint for ALB.
        """
        if path == "/health":
            return http.HTTPStatus.OK, [], b"OK\n"
    
    async def start(self):
        """
        Start the WebSocket server.
        """
        logger.info(f"Starting WebSocket server on {WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
        
        # Start background tasks
        asyncio.create_task(self.sqs_poller())
        
        # Start WebSocket server
        async with websockets.serve(
            self.connection_handler,
            WEBSOCKET_HOST,
            WEBSOCKET_PORT,
            ping_interval=30,
            ping_timeout=10,
            process_request=self.health_check_handler
        ):
            logger.info(f"WebSocket server running on ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
            await asyncio.Future()  # Run forever
    
    def stop(self):
        """
        Stop the WebSocket server gracefully.
        """
        logger.info("Stopping WebSocket server...")
        self.running = False


# Global server instance
server = WebSocketServer()


def signal_handler(signum, frame):
    """
    Handle shutdown signals gracefully.
    """
    logger.info(f"Received signal {signum}, shutting down...")
    server.stop()
    sys.exit(0)


async def main():
    """
    Main entry point for the WebSocket server.
    """
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Validate environment variables
    required_vars = [
        'SQS_QUEUE_URL_PM',
        'SQS_QUEUE_URL_DEV',
        'SQS_QUEUE_URL_QA',
        'SQS_QUEUE_URL_OPS',
        'DYNAMODB_TABLE_NAME'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    logger.info("Environment variables validated")
    logger.info(f"DynamoDB Table: {DYNAMODB_TABLE_NAME}")
    logger.info(f"PM Queue: {SQS_QUEUE_URL_PM}")
    logger.info(f"Dev Queue: {SQS_QUEUE_URL_DEV}")
    logger.info(f"QA Queue: {SQS_QUEUE_URL_QA}")
    logger.info(f"Ops Queue: {SQS_QUEUE_URL_OPS}")
    
    # Start server
    await server.start()


if __name__ == '__main__':
    asyncio.run(main())
