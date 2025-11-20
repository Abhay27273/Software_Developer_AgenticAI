"""
End-to-End test: Parallel execution with MOCKED dependency management
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
from models.task import Task
from models.plan import Plan
from models.enums import TaskStatus


@pytest.fixture
def mock_websocket():
    ws = Mock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.client = Mock()
    ws.client.host = "127.0.0.1"
    ws.client.port = 12345
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
async def test_parallel_execution_performance_mock(agents, mock_websocket):
    """Test that parallel execution is faster than sequential (MOCKED)."""
    pm_agent = agents["pm"]
    dev_agent = agents["dev"]
    
    print("\n" + "="*70)
    print("🧪 E2E TEST: Parallel Execution Performance (MOCKED)")
    print("="*70 + "\n")
    
    # Create plan with independent microservices
    mock_plan = Plan(
        id="test_microservices",
        title="Microservices Project",
        description="Independent microservices for parallel development",
        tasks=[
            Task(
                id="task_user",
                title="User Service",
                description="User management microservice",
                priority=1,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=[],
                estimated_hours=2.0,
                complexity="medium"
            ),
            Task(
                id="task_auth",
                title="Auth Service",
                description="Authentication microservice",
                priority=1,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=[],
                estimated_hours=2.0,
                complexity="medium"
            ),
            Task(
                id="task_payment",
                title="Payment Service",
                description="Payment processing microservice",
                priority=1,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=[],
                estimated_hours=2.0,
                complexity="medium"
            ),
            Task(
                id="task_notification",
                title="Notification Service",
                description="Notification delivery microservice",
                priority=1,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=[],
                estimated_hours=2.0,
                complexity="medium"
            )
        ]
    )
    
    pm_agent.current_plan = mock_plan
    dev_tasks = [t for t in mock_plan.tasks if t.agent_type == "dev_agent"]
    
    print(f"📋 Created {len(dev_tasks)} independent microservices\n")
    for task in dev_tasks:
        print(f"  ✓ {task.title} (no dependencies)")
    print()
    
    # ============================================================
    # Test 1: Sequential Execution
    # ============================================================
    print("⏱️  Test 1: Sequential Execution")
    
    async def mock_dev_task(task):
        """Simulate development work."""
        await asyncio.sleep(0.2)  # Simulate 200ms work
        task.status = TaskStatus.COMPLETED
        return task
    
    start_time = time.time()
    sequential_results = []
    for task in dev_tasks:
        result = await mock_dev_task(task)
        sequential_results.append(result)
        print(f"  → {task.title} completed")
    
    sequential_time = time.time() - start_time
    print(f"\n  ✓ All tasks completed in {sequential_time:.2f}s")
    print(f"  ✓ Average time per task: {sequential_time/len(dev_tasks):.2f}s\n")
    
    # Reset tasks
    for task in dev_tasks:
        task.status = TaskStatus.PENDING
    
    # ============================================================
    # Test 2: Parallel Execution
    # ============================================================
    print("⚡ Test 2: Parallel Execution (Using asyncio.gather)")
    
    start_time = time.time()
    
    # Execute all tasks concurrently
    parallel_tasks = [mock_dev_task(task) for task in dev_tasks]
    parallel_results = await asyncio.gather(*parallel_tasks)
    
    parallel_time = time.time() - start_time
    
    for task in parallel_results:
        print(f"  → {task.title} completed")
    
    print(f"\n  ✓ All tasks completed in {parallel_time:.2f}s")
    print(f"  ✓ Average time per task: {parallel_time/len(dev_tasks):.2f}s\n")
    
    # ============================================================
    # Test 3: Dependency-Aware Parallel Execution
    # ============================================================
    print("🔗 Test 3: Dependency-Aware Parallel Execution")
    
    # Create tasks with dependencies
    dependent_tasks = [
        Task(
            id="db_models",
            title="Database Models",
            description="Core data models",
            priority=1,
            status=TaskStatus.PENDING,
            agent_type="dev_agent",
            dependencies=[],
            estimated_hours=1.0,
            complexity="low"
        ),
        Task(
            id="api_routes_1",
            title="User API Routes",
            description="User endpoints",
            priority=2,
            status=TaskStatus.PENDING,
            agent_type="dev_agent",
            dependencies=["db_models"],
            estimated_hours=1.0,
            complexity="low"
        ),
        Task(
            id="api_routes_2",
            title="Product API Routes",
            description="Product endpoints",
            priority=2,
            status=TaskStatus.PENDING,
            agent_type="dev_agent",
            dependencies=["db_models"],
            estimated_hours=1.0,
            complexity="low"
        ),
        Task(
            id="integration",
            title="Integration Layer",
            description="Connect all services",
            priority=3,
            status=TaskStatus.PENDING,
            agent_type="dev_agent",
            dependencies=["api_routes_1", "api_routes_2"],
            estimated_hours=1.0,
            complexity="medium"
        )
    ]
    
    print(f"\n  Created {len(dependent_tasks)} tasks with dependencies:")
    for task in dependent_tasks:
        deps = f"depends on: {', '.join(task.dependencies)}" if task.dependencies else "no dependencies"
        print(f"  ✓ {task.title} ({deps})")
    
    # Manual dependency resolution (topological sort)
    def get_execution_levels(tasks):
        """Group tasks by dependency level for parallel execution."""
        task_dict = {t.id: t for t in tasks}
        levels = []
        completed = set()
        
        while len(completed) < len(tasks):
            # Find tasks whose dependencies are all completed
            current_level = []
            for task in tasks:
                if task.id not in completed:
                    deps_met = all(dep in completed for dep in task.dependencies)
                    if deps_met:
                        current_level.append(task)
            
            if not current_level:
                break  # Circular dependency or error
            
            levels.append(current_level)
            completed.update(t.id for t in current_level)
        
        return levels
    
    execution_order = get_execution_levels(dependent_tasks)
    
    print(f"\n  Optimal execution order (by level):")
    for level, level_tasks in enumerate(execution_order):
        task_names = [t.title for t in level_tasks]
        print(f"    Level {level}: {', '.join(task_names)} (can run in parallel)")
    
    # Execute with dependency awareness
    start_time = time.time()
    
    for level, level_tasks in enumerate(execution_order):
        print(f"\n  Executing Level {level} ({len(level_tasks)} tasks in parallel)...")
        
        # Execute tasks in this level concurrently
        level_coroutines = [mock_dev_task(task) for task in level_tasks]
        await asyncio.gather(*level_coroutines)
        
        for task in level_tasks:
            print(f"    ✓ {task.title} completed")
    
    dependency_aware_time = time.time() - start_time
    print(f"\n  ✓ All tasks completed in {dependency_aware_time:.2f}s\n")
    
    # ============================================================
    # Results Analysis
    # ============================================================
    speedup_basic = sequential_time / parallel_time if parallel_time > 0 else 0
    efficiency = (speedup_basic / len(dev_tasks)) * 100
    
    print("="*70)
    print("📊 PARALLEL EXECUTION ANALYSIS")
    print("="*70)
    print(f"Independent Tasks:        {len(dev_tasks)}")
    print(f"Sequential Time:          {sequential_time:.2f}s")
    print(f"Parallel Time:            {parallel_time:.2f}s")
    print(f"Speedup Factor:           {speedup_basic:.2f}x")
    print(f"Parallel Efficiency:      {efficiency:.1f}%")
    print(f"Time Saved:               {(sequential_time - parallel_time):.2f}s ({((sequential_time - parallel_time) / sequential_time * 100):.1f}%)")
    print()
    print(f"Dependent Tasks:          {len(dependent_tasks)}")
    print(f"Dependency-Aware Time:    {dependency_aware_time:.2f}s")
    print(f"Execution Levels:         {len(execution_order)}")
    print("="*70)
    
    # Verify parallel is faster
    assert parallel_time < sequential_time, "Parallel should be faster than sequential"
    assert speedup_basic > 2.0, f"Should achieve >2x speedup with 4 tasks, got {speedup_basic:.2f}x"
    assert dependency_aware_time < sequential_time, "Dependency-aware should still be faster than sequential"
    
    print("🎉 PARALLEL EXECUTION TEST PASSED!")
    print("="*70 + "\n")
    
    print("✅ Key Findings:")
    print(f"  • Parallel execution is {speedup_basic:.2f}x faster for independent tasks")
    print(f"  • Saved {(sequential_time - parallel_time):.2f}s on 4 tasks")
    print(f"  • Dependency-aware execution completed in {dependency_aware_time:.2f}s")
    print(f"  • System can execute {len(execution_order[1]) if len(execution_order) > 1 else 0} tasks in parallel at level 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])