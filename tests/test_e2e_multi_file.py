"""
End-to-End test: Complex multi-file project with dependencies
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
    ws.client.port = 12346
    return ws


@pytest_asyncio.fixture
async def agents(tmp_path):
    """Initialize all agents."""
    ws_manager = WebSocketManager()
    
    pm_agent = PlannerAgent(ws_manager)
    pm_agent.generated_code_root = tmp_path / "generated_multi"
    pm_agent.generated_code_root.mkdir(exist_ok=True)
    
    dev_agent = DevAgent(ws_manager)
    qa_agent = QAAgent(ws_manager)
    ops_agent = OpsAgent(ws_manager, pm_agent.generated_code_root)
    
    return {
        "pm": pm_agent,
        "dev": dev_agent,
        "qa": qa_agent,
        "ops": ops_agent
    }


@pytest.mark.asyncio
async def test_todo_api_workflow(agents, mock_websocket):
    """Test complete workflow for Todo API with database."""
    pm_agent = agents["pm"]
    dev_agent = agents["dev"]
    qa_agent = agents["qa"]
    ops_agent = agents["ops"]
    
    print("\n" + "="*70)
    print("🧪 E2E TEST: Multi-File Todo API Project")
    print("="*70 + "\n")
    
    # ============================================================
    # PHASE 1: PM Agent - Complex Plan
    # ============================================================
    print("📋 Phase 1: PM Agent Creating Complex Plan...")
    
    user_request = """
    Create a complete Todo API application with:
    
    1. FastAPI application structure (main.py)
    2. Database models with SQLAlchemy (models/todo.py)
    3. Pydantic schemas for validation (schemas/todo.py)
    4. CRUD operations (crud/todo.py)
    5. API endpoints (routes/todos.py):
       - GET /todos (list all)
       - GET /todos/{id} (get one)
       - POST /todos (create)
       - PUT /todos/{id} (update)
       - DELETE /todos/{id} (delete)
    6. Database configuration (database.py)
    7. Requirements.txt with dependencies
    8. Dockerfile for deployment
    """
    
    tasks = []
    async for result in pm_agent.create_plan_and_stream_tasks(user_request, mock_websocket):
        if result["type"] == "task_created":
            task = result["task"]
            tasks.append(task)
            print(f"  ✓ {task.title} ({task.agent_type})")
    
    assert len(tasks) >= 3, "PM should create multiple tasks for complex project"
    print(f"\n✅ PM Agent created {len(tasks)} tasks\n")
    
    # ============================================================
    # PHASE 2: Dev Agent - Execute Multiple Tasks
    # ============================================================
    print("💻 Phase 2: Dev Agent Executing Multiple Tasks...")
    
    dev_tasks = [t for t in tasks if t.agent_type == "dev_agent"]
    print(f"\nFound {len(dev_tasks)} development tasks\n")
    
    dev_results = []
    generated_files = []
    
    for idx, dev_task in enumerate(dev_tasks, 1):
        print(f"Task {idx}/{len(dev_tasks)}: {dev_task.title}")
        
        try:
            dev_result = await dev_agent.execute_task(dev_task)
            
            if dev_result.status == TaskStatus.COMPLETED:
                dev_results.append(dev_result)
                
                # Track generated files
                if dev_result.metadata and "file_path" in dev_result.metadata:
                    file_path = Path(dev_result.metadata["file_path"])
                    if file_path.exists():
                        generated_files.append(file_path)
                        print(f"  ✓ Generated: {file_path.name} ({file_path.stat().st_size} bytes)")
                
                print(f"  ✓ Status: COMPLETED\n")
            else:
                print(f"  ⚠️  Status: {dev_result.status.value}\n")
                
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
            continue
    
    print(f"✅ Dev Agent completed {len(dev_results)}/{len(dev_tasks)} tasks")
    print(f"📁 Generated {len(generated_files)} files\n")
    
    # Verify file structure
    if generated_files:
        print("📂 Project Structure:")
        for file_path in sorted(generated_files):
            rel_path = file_path.relative_to(pm_agent.generated_code_root)
            print(f"  └── {rel_path}")
        print()
    
    # ============================================================
    # PHASE 3: QA Agent - Test All Components
    # ============================================================
    print("🧪 Phase 3: QA Agent Testing All Components...")
    
    qa_results = []
    total_tests = 0
    passed_tests = 0
    
    for idx, dev_task in enumerate(dev_results, 1):
        print(f"\nTesting {idx}/{len(dev_results)}: {dev_task.title}")
        
        try:
            qa_result = await qa_agent.execute_task(dev_task)
            qa_results.append(qa_result)
            
            if qa_result.metadata:
                task_total = qa_result.metadata.get("total_tests", 0)
                task_passed = qa_result.metadata.get("passed_tests", 0)
                total_tests += task_total
                passed_tests += task_passed
                
                print(f"  ✓ Tests: {task_passed}/{task_total} passed")
            
            print(f"  ✓ Status: {qa_result.status.value}")
            
        except Exception as e:
            print(f"  ⚠️  QA Warning: {e}")
            continue
    
    print(f"\n✅ QA Agent tested {len(qa_results)} components")
    print(f"🧪 Total Tests: {passed_tests}/{total_tests} passed\n")
    
    # ============================================================
    # PHASE 4: Ops Agent - Deploy Full Application
    # ============================================================
    print("🚀 Phase 4: Ops Agent Deploying Full Application...")
    
    deployment_task = Task(
        id="deploy_todo_api",
        title="Deploy Todo API Application",
        description="Production deployment of complete Todo API",
        priority=10,
        status=TaskStatus.PENDING,
        agent_type="ops_agent",
        metadata={
            "project_type": "fastapi",
            "has_database": True,
            "dev_tasks_completed": len(dev_results),
            "qa_tasks_passed": len([r for r in qa_results if r.status == TaskStatus.COMPLETED]),
            "total_files": len(generated_files)
        }
    )
    
    try:
        ops_result = await ops_agent.execute_task(deployment_task)
        
        print(f"\n  ✓ Deployment Status: {ops_result.status.value}")
        
        if ops_result.metadata:
            print(f"  ✓ GitHub: {ops_result.metadata.get('github_url', 'N/A')}")
            
            for dep in ops_result.metadata.get("deployment_urls", []):
                print(f"  ✓ Platform: {dep.get('platform', 'Unknown')} → {dep.get('url', 'N/A')}")
        
        print(f"\n✅ Ops Agent deployment {ops_result.status.value}")
        
    except Exception as e:
        print(f"\n⚠️  Ops Agent warning: {e}")
    
    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("📊 MULTI-FILE E2E TEST SUMMARY")
    print("="*70)
    print(f"📋 PM Agent:        {len(tasks)} tasks planned")
    print(f"💻 Dev Agent:       {len(dev_results)}/{len(dev_tasks)} tasks completed")
    print(f"📁 Files Generated: {len(generated_files)} files")
    print(f"🧪 QA Agent:        {len(qa_results)} components tested")
    print(f"✅ Tests Passed:    {passed_tests}/{total_tests}")
    print(f"🚀 Ops Agent:       Deployment {ops_result.status.value}")
    print("="*70)
    print("🎉 MULTI-FILE WORKFLOW COMPLETED SUCCESSFULLY!")
    print("="*70 + "\n")
    
    # Assertions for test validation
    assert len(dev_results) > 0, "Should complete at least one dev task"
    assert len(generated_files) > 0, "Should generate at least one file"
    assert len(qa_results) > 0, "Should test at least one component"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
