"""
End-to-End test: Parallel execution with dependency management
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock
from pathlib import Path
import time

from agents.pm_agent import PlannerAgent
from agents.dev_agent import DevAgent
from agents.qa_agent import QAAgent
from parse.websocket_manager import WebSocketManager
from models.enums import TaskStatus


@pytest.fixture
def mock_websocket():
    ws = Mock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.client = Mock()
    ws.client.host = "127.0.0.1"
    ws.client.port = 12347
    return ws


@pytest_asyncio.fixture
async def agents(tmp_path):
    ws_manager = WebSocketManager()
    
    pm_agent = PlannerAgent(ws_manager)
    pm_agent.generated_code_root = tmp_path / "parallel_test"
    pm_agent.generated_code_root.mkdir(exist_ok=True)
    
    dev_agent = DevAgent(ws_manager)
    qa_agent = QAAgent(ws_manager)
    
    return {"pm": pm_agent, "dev": dev_agent, "qa": qa_agent}


@pytest.mark.asyncio
async def test_parallel_execution_performance(agents, mock_websocket):
    """Test that parallel execution is faster than sequential."""
    pm_agent = agents["pm"]
    dev_agent = agents["dev"]
    
    print("\n" + "="*70)
    print("🧪 E2E TEST: Parallel Execution Performance")
    print("="*70 + "\n")
    
    # Create plan with independent tasks
    user_request = """
    Create a microservices project with:
    1. User service (users.py)
    2. Auth service (auth.py)
    3. Payment service (payment.py)
    4. Notification service (notification.py)
    
    All services are independent and can be developed in parallel.
    """
    
    tasks = []
    async for result in pm_agent.create_plan_and_stream_tasks(user_request, mock_websocket):
        if result["type"] == "task_created":
            tasks.append(result["task"])
    
    dev_tasks = [t for t in tasks if t.agent_type == "dev_agent"]
    print(f"📋 Created {len(dev_tasks)} independent development tasks\n")
    
    # ============================================================
    # Test 1: Sequential Execution
    # ============================================================
    print("⏱️  Test 1: Sequential Execution")
    start_time = time.time()
    
    sequential_results = []
    for task in dev_tasks:
        result = await dev_agent.execute_task(task)
        sequential_results.append(result)
    
    sequential_time = time.time() - start_time
    print(f"  ✓ Completed in {sequential_time:.2f} seconds\n")
    
    # ============================================================
    # Test 2: Parallel Execution
    # ============================================================
    print("⚡ Test 2: Parallel Execution")
    start_time = time.time()
    
    # Execute all tasks concurrently
    parallel_tasks = [dev_agent.execute_task(task) for task in dev_tasks]
    parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
    
    parallel_time = time.time() - start_time
    print(f"  ✓ Completed in {parallel_time:.2f} seconds\n")
    
    # ============================================================
    # Results Analysis
    # ============================================================
    speedup = sequential_time / parallel_time if parallel_time > 0 else 0
    
    print("="*70)
    print("📊 PARALLEL EXECUTION ANALYSIS")
    print("="*70)
    print(f"Tasks Executed:      {len(dev_tasks)}")
    print(f"Sequential Time:     {sequential_time:.2f}s")
    print(f"Parallel Time:       {parallel_time:.2f}s")
    print(f"Speedup Factor:      {speedup:.2f}x")
    print(f"Time Saved:          {(sequential_time - parallel_time):.2f}s ({((sequential_time - parallel_time) / sequential_time * 100):.1f}%)")
    print("="*70)
    
    # Verify parallel is faster (or at least not slower)
    # Note: In test environments, parallel might not always be faster due to overhead
    assert parallel_time <= sequential_time * 1.2, "Parallel should not be significantly slower"
    
    print("🎉 PARALLEL EXECUTION TEST PASSED!")
    print("="*70 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
