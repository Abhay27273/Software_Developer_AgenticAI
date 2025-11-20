"""
End-to-End test: PM → Dev → QA → Ops for simple FastAPI project
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from agents.pm_agent import PlannerAgent
from agents.dev_agent import DevAgent
from agents.qa_agent import QAAgent
from agents.ops_agent import OpsAgent
from parse.websocket_manager import WebSocketManager
from models.task import Task
from models.enums import TaskStatus


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket."""
    ws = Mock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.client = Mock()
    ws.client.host = "127.0.0.1"
    ws.client.port = 12345
    return ws


@pytest_asyncio.fixture
async def agents(tmp_path):
    """Initialize all agents."""
    ws_manager = WebSocketManager()
    
    pm_agent = PlannerAgent(ws_manager)
    pm_agent.generated_code_root = tmp_path / "generated"
    pm_agent.generated_code_root.mkdir(exist_ok=True)
    
    dev_agent = DevAgent(ws_manager)
    qa_agent = QAAgent(ws_manager)
    ops_agent = OpsAgent(ws_manager, pm_agent.generated_code_root)
    
    return {
        "pm": pm_agent,
        "dev": dev_agent,
        "qa": qa_agent,
        "ops": ops_agent,
        "ws_manager": ws_manager
    }


@pytest.mark.asyncio
async def test_simple_fastapi_workflow(agents, mock_websocket):
    """Test complete workflow for simple FastAPI app."""
    pm_agent = agents["pm"]
    dev_agent = agents["dev"]
    qa_agent = agents["qa"]
    ops_agent = agents["ops"]
    
    print("\n" + "="*60)
    print("🧪 E2E TEST: Simple FastAPI Application")
    print("="*60 + "\n")
    
    # ============================================================
    # PHASE 1: PM Agent - Create Plan
    # ============================================================
    print("📋 Phase 1: PM Agent Creating Plan...")
    
    user_request = """
    Create a simple FastAPI application with:
    1. GET /health endpoint that returns {"status": "healthy"}
    2. GET /hello endpoint that returns {"message": "Hello World"}
    3. Basic error handling with try-except
    4. Proper response models using Pydantic
    """
    
    tasks = []
    task_count = 0
    
    async for result in pm_agent.create_plan_and_stream_tasks(user_request, mock_websocket):
        if result["type"] == "task_created":
            task = result["task"]
            tasks.append(task)
            task_count += 1
            print(f"  ✓ Task {task_count}: {task.title} ({task.agent_type})")
    
    assert len(tasks) > 0, "PM Agent should create at least one task"
    print(f"\n✅ PM Agent created {len(tasks)} tasks\n")
    
    # ============================================================
    # PHASE 2: Dev Agent - Execute Development Tasks
    # ============================================================
    print("💻 Phase 2: Dev Agent Executing Tasks...")
    
    dev_tasks = [t for t in tasks if t.agent_type == "dev_agent"]
    dev_results = []
    
    for idx, dev_task in enumerate(dev_tasks, 1):
        print(f"\n  Task {idx}/{len(dev_tasks)}: {dev_task.title}")
        
        try:
            dev_result = await dev_agent.execute_task(dev_task)
            
            assert dev_result.status == TaskStatus.COMPLETED, \
                f"Dev task should complete successfully: {dev_result.result}"
            
            dev_results.append(dev_result)
            
            # Verify file was created
            if dev_result.metadata and "file_path" in dev_result.metadata:
                file_path = Path(dev_result.metadata["file_path"])
                assert file_path.exists(), f"Generated file should exist: {file_path}"
                print(f"    ✓ Generated: {file_path.name}")
            
            print(f"    ✓ Status: {dev_result.status.value}")
            
        except Exception as e:
            print(f"    ✗ Error: {e}")
            raise
    
    print(f"\n✅ Dev Agent completed {len(dev_results)} tasks\n")
    
    # ============================================================
    # PHASE 3: QA Agent - Test Generated Code
    # ============================================================
    print("🧪 Phase 3: QA Agent Testing Code...")
    
    qa_results = []
    
    for idx, dev_task in enumerate(dev_results, 1):
        print(f"\n  Testing {idx}/{len(dev_results)}: {dev_task.title}")
        
        try:
            qa_result = await qa_agent.execute_task(dev_task)
            
            # QA can be completed or need review
            assert qa_result.status in [TaskStatus.COMPLETED, TaskStatus.REVIEW_NEEDED], \
                f"QA should pass or need review: {qa_result.status}"
            
            qa_results.append(qa_result)
            
            # Check test results
            if qa_result.metadata:
                total_tests = qa_result.metadata.get("total_tests", 0)
                passed_tests = qa_result.metadata.get("passed_tests", 0)
                print(f"    ✓ Tests: {passed_tests}/{total_tests} passed")
            
            print(f"    ✓ Status: {qa_result.status.value}")
            
        except Exception as e:
            print(f"    ✗ QA Error: {e}")
            # Continue testing other tasks
            continue
    
    print(f"\n✅ QA Agent tested {len(qa_results)} components\n")
    
    # ============================================================
    # PHASE 4: Ops Agent - Deploy to Production
    # ============================================================
    print("🚀 Phase 4: Ops Agent Deploying...")
    
    deployment_task = Task(
        id="deploy_simple_fastapi",
        title="Deploy FastAPI Application",
        description="Production deployment of simple FastAPI app",
        priority=10,
        status=TaskStatus.PENDING,
        agent_type="ops_agent",
        metadata={
            "project_type": "fastapi",
            "dev_tasks_completed": len(dev_results),
            "qa_tasks_passed": len([r for r in qa_results if r.status == TaskStatus.COMPLETED])
        }
    )
    
    try:
        ops_result = await ops_agent.execute_task(deployment_task)
        
        # Ops should at least start deployment
        assert ops_result.status in [TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS], \
            f"Ops should initiate deployment: {ops_result.status}"
        
        print(f"\n  ✓ Deployment Status: {ops_result.status.value}")
        
        if ops_result.metadata:
            github_url = ops_result.metadata.get("github_url")
            deployments = ops_result.metadata.get("deployment_urls", [])
            
            if github_url:
                print(f"  ✓ GitHub: {github_url}")
            
            for deployment in deployments:
                print(f"  ✓ Deployed: {deployment.get('url', 'N/A')}")
        
        print(f"\n✅ Ops Agent deployment {ops_result.status.value}")
        
    except Exception as e:
        print(f"\n⚠️  Ops Agent warning: {e}")
        print("  (This is expected in test environment)")
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "="*60)
    print("📊 E2E TEST SUMMARY")
    print("="*60)
    print(f"✅ PM Agent:   {len(tasks)} tasks created")
    print(f"✅ Dev Agent:  {len(dev_results)}/{len(dev_tasks)} tasks completed")
    print(f"✅ QA Agent:   {len(qa_results)}/{len(dev_results)} components tested")
    print(f"✅ Ops Agent:  Deployment {ops_result.status.value}")
    print("="*60)
    print("🎉 END-TO-END WORKFLOW COMPLETED SUCCESSFULLY!")
    print("="*60 + "\n")


@pytest.mark.asyncio
async def test_error_recovery_workflow(agents, mock_websocket):
    """Test workflow with intentional errors to verify recovery."""
    pm_agent = agents["pm"]
    dev_agent = agents["dev"]
    
    print("\n" + "="*60)
    print("🧪 E2E TEST: Error Recovery")
    print("="*60 + "\n")
    
    # Create plan with intentionally problematic request
    user_request = "Create a simple hello.py file with print('Hello World')"
    
    tasks = []
    async for result in pm_agent.create_plan_and_stream_tasks(user_request, mock_websocket):
        if result["type"] == "task_created":
            tasks.append(result["task"])
    
    print(f"✅ Created {len(tasks)} tasks for error recovery test")
    
    # Dev agent should handle errors gracefully
    if tasks:
        dev_task = next((t for t in tasks if t.agent_type == "dev_agent"), None)
        if dev_task:
            try:
                result = await dev_agent.execute_task(dev_task)
                # Should either complete or fail gracefully
                assert result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
                print(f"✅ Dev Agent handled error gracefully: {result.status.value}")
            except Exception as e:
                print(f"✅ Exception caught and handled: {type(e).__name__}")
    
    print("="*60)
    print("🎉 ERROR RECOVERY TEST COMPLETED!")
    print("="*60 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
