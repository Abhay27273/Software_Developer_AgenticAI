"""
Quick WebSocket Connection Test
Tests that WebSocket endpoint is responsive
"""
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:7860/ws"
    print(f"🔌 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected!")
            
            # Wait for welcome message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📨 Received: {json.dumps(data, indent=2)}")
            
            if data.get("type") == "connection":
                print("✅ Connection confirmed!")
                print(f"   Mode: {data.get('mode')}")
                print(f"   Version: {data.get('version')}")
                return True
            else:
                print("❌ Unexpected message type")
                return False
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_websocket())
    exit(0 if result else 1)
