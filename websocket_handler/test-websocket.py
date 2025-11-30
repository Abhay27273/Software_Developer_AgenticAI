#!/usr/bin/env python3
"""
WebSocket Connection Test Script

Usage:
    python test-websocket.py ws://your-alb-dns/ws
"""

import asyncio
import json
import sys
import websockets


async def test_websocket(uri: str):
    """Test WebSocket connection with various operations."""
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected successfully")
            
            # Test 1: Receive welcome message
            print("\n[Test 1] Waiting for welcome message...")
            welcome = await asyncio.wait_for(websocket.recv(), timeout=5)
            welcome_data = json.loads(welcome)
            print(f"✓ Received: {welcome_data.get('type')} - {welcome_data.get('message')}")
            
            # Test 2: Send ping
            print("\n[Test 2] Sending ping...")
            await websocket.send(json.dumps({"action": "ping"}))
            pong = await asyncio.wait_for(websocket.recv(), timeout=5)
            pong_data = json.loads(pong)
            print(f"✓ Received: {pong_data.get('type')}")
            
            # Test 3: Subscribe to project
            print("\n[Test 3] Subscribing to project...")
            await websocket.send(json.dumps({
                "action": "subscribe",
                "project_id": "test_project_123"
            }))
            sub_response = await asyncio.wait_for(websocket.recv(), timeout=5)
            sub_data = json.loads(sub_response)
            print(f"✓ Received: {sub_data.get('type')} for project {sub_data.get('project_id')}")
            
            # Test 4: Forward message to SQS
            print("\n[Test 4] Forwarding message to SQS...")
            await websocket.send(json.dumps({
                "action": "forward",
                "type": "dev",
                "message_id": "test_msg_123",
                "project_id": "test_project_123",
                "data": {
                    "task": "test_task",
                    "parameters": {"test": "value"}
                }
            }))
            forward_response = await asyncio.wait_for(websocket.recv(), timeout=5)
            forward_data = json.loads(forward_response)
            print(f"✓ Received: {forward_data.get('type')} for message {forward_data.get('message_id')}")
            
            # Test 5: Unsubscribe from project
            print("\n[Test 5] Unsubscribing from project...")
            await websocket.send(json.dumps({
                "action": "unsubscribe",
                "project_id": "test_project_123"
            }))
            unsub_response = await asyncio.wait_for(websocket.recv(), timeout=5)
            unsub_data = json.loads(unsub_response)
            print(f"✓ Received: {unsub_data.get('type')} for project {unsub_data.get('project_id')}")
            
            # Test 6: Invalid action
            print("\n[Test 6] Testing error handling...")
            await websocket.send(json.dumps({
                "action": "invalid_action"
            }))
            error_response = await asyncio.wait_for(websocket.recv(), timeout=5)
            error_data = json.loads(error_response)
            print(f"✓ Received error: {error_data.get('type')} - {error_data.get('message')}")
            
            print("\n" + "="*50)
            print("All tests passed! ✓")
            print("="*50)
            
    except asyncio.TimeoutError:
        print("✗ Timeout waiting for response")
        sys.exit(1)
    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


async def test_connection_only(uri: str):
    """Simple connection test."""
    print(f"Testing connection to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connection successful")
            
            # Wait for welcome message
            welcome = await asyncio.wait_for(websocket.recv(), timeout=5)
            print(f"✓ Received welcome: {welcome}")
            
            # Send ping
            await websocket.send(json.dumps({"action": "ping"}))
            pong = await asyncio.wait_for(websocket.recv(), timeout=5)
            print(f"✓ Received pong: {pong}")
            
            print("\nConnection test passed! ✓")
            
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test-websocket.py <websocket-uri> [--simple]")
        print("\nExample:")
        print("  python test-websocket.py ws://your-alb-dns/ws")
        print("  python test-websocket.py ws://your-alb-dns/ws --simple")
        sys.exit(1)
    
    uri = sys.argv[1]
    simple_mode = "--simple" in sys.argv
    
    if simple_mode:
        asyncio.run(test_connection_only(uri))
    else:
        asyncio.run(test_websocket(uri))


if __name__ == "__main__":
    main()
