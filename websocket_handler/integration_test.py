"""
Integration test for WebSocket handler

This script tests the WebSocket server with real connections.
Run the server first, then run this script.

Usage:
    python integration_test.py ws://localhost:8080
"""

import asyncio
import json
import sys
import websockets
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def log(message, color=Colors.BLUE):
    """Print colored log message"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"{color}[{timestamp}] {message}{Colors.END}")


async def test_connection(uri):
    """Test basic WebSocket connection"""
    log("Testing connection...", Colors.YELLOW)
    
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for welcome message
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'connected':
                log("✓ Connection established", Colors.GREEN)
                return True
            else:
                log(f"✗ Unexpected welcome message: {data}", Colors.RED)
                return False
    except Exception as e:
        log(f"✗ Connection failed: {e}", Colors.RED)
        return False


async def test_ping_pong(uri):
    """Test ping/pong functionality"""
    log("Testing ping/pong...", Colors.YELLOW)
    
    try:
        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()
            
            # Send ping
            await websocket.send(json.dumps({"action": "ping"}))
            
            # Wait for pong
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'pong':
                log("✓ Ping/pong working", Colors.GREEN)
                return True
            else:
                log(f"✗ Expected pong, got: {data}", Colors.RED)
                return False
    except Exception as e:
        log(f"✗ Ping/pong failed: {e}", Colors.RED)
        return False


async def test_subscribe(uri):
    """Test project subscription"""
    log("Testing project subscription...", Colors.YELLOW)
    
    try:
        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()
            
            # Subscribe to project
            project_id = "test_proj_123"
            await websocket.send(json.dumps({
                "action": "subscribe",
                "project_id": project_id
            }))
            
            # Wait for confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'subscription_confirmed' and data.get('project_id') == project_id:
                log(f"✓ Subscribed to project: {project_id}", Colors.GREEN)
                return True
            else:
                log(f"✗ Subscription failed: {data}", Colors.RED)
                return False
    except Exception as e:
        log(f"✗ Subscription test failed: {e}", Colors.RED)
        return False


async def test_unsubscribe(uri):
    """Test project unsubscription"""
    log("Testing project unsubscription...", Colors.YELLOW)
    
    try:
        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()
            
            # Subscribe first
            project_id = "test_proj_456"
            await websocket.send(json.dumps({
                "action": "subscribe",
                "project_id": project_id
            }))
            await websocket.recv()  # Skip confirmation
            
            # Unsubscribe
            await websocket.send(json.dumps({
                "action": "unsubscribe",
                "project_id": project_id
            }))
            
            # Wait for confirmation
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'unsubscription_confirmed' and data.get('project_id') == project_id:
                log(f"✓ Unsubscribed from project: {project_id}", Colors.GREEN)
                return True
            else:
                log(f"✗ Unsubscription failed: {data}", Colors.RED)
                return False
    except Exception as e:
        log(f"✗ Unsubscription test failed: {e}", Colors.RED)
        return False


async def test_invalid_json(uri):
    """Test handling of invalid JSON"""
    log("Testing invalid JSON handling...", Colors.YELLOW)
    
    try:
        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()
            
            # Send invalid JSON
            await websocket.send("invalid json {")
            
            # Wait for error response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'error' and 'JSON' in data.get('message', ''):
                log("✓ Invalid JSON handled correctly", Colors.GREEN)
                return True
            else:
                log(f"✗ Unexpected response to invalid JSON: {data}", Colors.RED)
                return False
    except Exception as e:
        log(f"✗ Invalid JSON test failed: {e}", Colors.RED)
        return False


async def test_unknown_action(uri):
    """Test handling of unknown action"""
    log("Testing unknown action handling...", Colors.YELLOW)
    
    try:
        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()
            
            # Send unknown action
            await websocket.send(json.dumps({"action": "unknown_action"}))
            
            # Wait for error response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'error' and 'Unknown action' in data.get('message', ''):
                log("✓ Unknown action handled correctly", Colors.GREEN)
                return True
            else:
                log(f"✗ Unexpected response to unknown action: {data}", Colors.RED)
                return False
    except Exception as e:
        log(f"✗ Unknown action test failed: {e}", Colors.RED)
        return False


async def test_multiple_connections(uri):
    """Test multiple concurrent connections"""
    log("Testing multiple concurrent connections...", Colors.YELLOW)
    
    try:
        connections = []
        
        # Create 5 concurrent connections
        for i in range(5):
            ws = await websockets.connect(uri)
            connections.append(ws)
            await ws.recv()  # Skip welcome message
        
        log(f"✓ Created {len(connections)} concurrent connections", Colors.GREEN)
        
        # Send ping from each connection
        for i, ws in enumerate(connections):
            await ws.send(json.dumps({"action": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') != 'pong':
                log(f"✗ Connection {i} failed ping test", Colors.RED)
                return False
        
        log("✓ All connections responded to ping", Colors.GREEN)
        
        # Close all connections
        for ws in connections:
            await ws.close()
        
        log("✓ Multiple connections test passed", Colors.GREEN)
        return True
        
    except Exception as e:
        log(f"✗ Multiple connections test failed: {e}", Colors.RED)
        return False


async def test_connection_with_project_id(uri):
    """Test connection with project_id in URL"""
    log("Testing connection with project_id in URL...", Colors.YELLOW)
    
    try:
        project_id = "test_proj_789"
        uri_with_project = f"{uri}?project_id={project_id}"
        
        async with websockets.connect(uri_with_project) as websocket:
            # Wait for welcome message
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'connected':
                log(f"✓ Connected with project_id: {project_id}", Colors.GREEN)
                return True
            else:
                log(f"✗ Connection with project_id failed: {data}", Colors.RED)
                return False
    except Exception as e:
        log(f"✗ Connection with project_id test failed: {e}", Colors.RED)
        return False


async def run_all_tests(uri):
    """Run all integration tests"""
    log("=" * 60, Colors.BLUE)
    log("WebSocket Handler Integration Tests", Colors.BLUE)
    log(f"Target: {uri}", Colors.BLUE)
    log("=" * 60, Colors.BLUE)
    
    tests = [
        ("Connection", test_connection),
        ("Ping/Pong", test_ping_pong),
        ("Subscribe", test_subscribe),
        ("Unsubscribe", test_unsubscribe),
        ("Invalid JSON", test_invalid_json),
        ("Unknown Action", test_unknown_action),
        ("Multiple Connections", test_multiple_connections),
        ("Connection with Project ID", test_connection_with_project_id),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = await test_func(uri)
            results.append((name, result))
        except Exception as e:
            log(f"✗ Test '{name}' crashed: {e}", Colors.RED)
            results.append((name, False))
        
        # Small delay between tests
        await asyncio.sleep(0.5)
    
    # Print summary
    log("=" * 60, Colors.BLUE)
    log("Test Summary", Colors.BLUE)
    log("=" * 60, Colors.BLUE)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        color = Colors.GREEN if result else Colors.RED
        log(f"{status}: {name}", color)
    
    log("=" * 60, Colors.BLUE)
    log(f"Results: {passed}/{total} tests passed", 
        Colors.GREEN if passed == total else Colors.YELLOW)
    log("=" * 60, Colors.BLUE)
    
    return passed == total


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python integration_test.py <websocket_uri>")
        print("Example: python integration_test.py ws://localhost:8080")
        sys.exit(1)
    
    uri = sys.argv[1]
    
    # Remove trailing slash if present
    uri = uri.rstrip('/')
    
    try:
        success = await run_all_tests(uri)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\nTests interrupted by user", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        log(f"\nFatal error: {e}", Colors.RED)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
