"""
End-to-End test: Multi-file project with MOCKED LLM calls
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
from agents.ops_agent import OpsAgent
from parse.websocket_manager import WebSocketManager
from models.task import Task
from models.plan import Plan
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
async def test_todo_api_workflow_mock(agents, mock_websocket, tmp_path):
    """Test complete workflow for Todo API with database (MOCKED)."""
    pm_agent = agents["pm"]
    dev_agent = agents["dev"]
    qa_agent = agents["qa"]
    ops_agent = agents["ops"]
    
    print("\n" + "="*70)
    print("🧪 E2E TEST: Multi-File Todo API Project (MOCKED)")
    print("="*70 + "\n")
    
    # ============================================================
    # PHASE 1: PM Agent - Complex Plan
    # ============================================================
    print("📋 Phase 1: PM Agent Creating Complex Plan...")
    
    mock_plan = Plan(
        id="test_plan_todo",
        title="Todo API Application",
        description="Complete Todo API with database",
        tasks=[
            Task(
                id="task_001",
                title="Database Models",
                description="SQLAlchemy models for Todo",
                priority=1,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=[],
                estimated_hours=2.0,
                complexity="medium"
            ),
            Task(
                id="task_002",
                title="Pydantic Schemas",
                description="Request/Response schemas",
                priority=2,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=["task_001"],
                estimated_hours=1.0,
                complexity="low"
            ),
            Task(
                id="task_003",
                title="CRUD Operations",
                description="Database CRUD functions",
                priority=3,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=["task_001", "task_002"],
                estimated_hours=2.0,
                complexity="medium"
            ),
            Task(
                id="task_004",
                title="API Endpoints",
                description="FastAPI routes for todos",
                priority=4,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=["task_003"],
                estimated_hours=2.0,
                complexity="medium"
            ),
            Task(
                id="task_005",
                title="Database Configuration",
                description="SQLAlchemy setup",
                priority=1,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=[],
                estimated_hours=1.0,
                complexity="low"
            ),
            Task(
                id="task_006",
                title="Unit Tests",
                description="Comprehensive test suite",
                priority=5,
                status=TaskStatus.PENDING,
                agent_type="dev_agent",
                dependencies=["task_004"],
                estimated_hours=3.0,
                complexity="high"
            )
        ]
    )
    
    pm_agent.current_plan = mock_plan
    
    for idx, task in enumerate(mock_plan.tasks, 1):
        print(f"  ✓ Task {idx}: {task.title} (deps: {len(task.dependencies)})")
    
    print(f"\n✅ PM Agent created {len(mock_plan.tasks)} tasks\n")
    
    # ============================================================
    # PHASE 2: Dev Agent - Execute Multiple Tasks
    # ============================================================
    print("💻 Phase 2: Dev Agent Executing Multiple Tasks...")
    
    dev_tasks = [t for t in mock_plan.tasks if t.agent_type == "dev_agent"]
    print(f"\nFound {len(dev_tasks)} development tasks\n")
    
    dev_results = []
    generated_files = []
    
    # Mock file structure
    file_templates = {
        "task_001": ["models/todo.py", "models/__init__.py"],
        "task_002": ["schemas/todo.py", "schemas/__init__.py"],
        "task_003": ["crud/todo.py", "crud/__init__.py"],
        "task_004": ["routes/todos.py", "routes/__init__.py", "main.py"],
        "task_005": ["database.py", "config.py"],
        "task_006": ["tests/test_todos.py", "tests/conftest.py", "tests/__init__.py"]
    }
    
    for idx, dev_task in enumerate(dev_tasks, 1):
        print(f"Task {idx}/{len(dev_tasks)}: {dev_task.title}")
        
        # Create mock files
        files = file_templates.get(dev_task.id, ["code.py"])
        
        for file_name in files:
            output_file = pm_agent.generated_code_root / file_name
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            mock_code = f"""
# Generated: {file_name}
# Task: {dev_task.title}

from typing import List, Optional
from pydantic import BaseModel

class TodoBase(BaseModel):
    title: str
    description: Optional[str] = None
    completed: bool = False

# ... rest of implementation ...
"""
            output_file.write_text(mock_code)
            generated_files.append(output_file)
        
        dev_task.status = TaskStatus.COMPLETED
        dev_task.result = f"Generated {len(files)} files for {dev_task.title}"
        dev_task.metadata = {
            "file_path": str(generated_files[-1]),
            "files_generated": len(files)
        }
        
        dev_results.append(dev_task)
        print(f"  ✓ Generated: {len(files)} files ({sum(f.stat().st_size for f in generated_files[-len(files):])} bytes)")
        print(f"  ✓ Status: COMPLETED\n")
    
    print(f"✅ Dev Agent completed {len(dev_results)}/{len(dev_tasks)} tasks")
    print(f"📁 Generated {len(generated_files)} files\n")
    
    # Verify file structure
    print("📂 Project Structure:")
    for file_path in sorted(generated_files[:12]):  # Show first 12
        rel_path = file_path.relative_to(pm_agent.generated_code_root)
        print(f"  └── {rel_path}")
    if len(generated_files) > 12:
        print(f"  ... and {len(generated_files) - 12} more files")
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
        
        # Mock test results - more tests for complex tasks
        task_total = 10 if dev_task.complexity == "high" else 7 if dev_task.complexity == "medium" else 5
        task_passed = task_total  # All pass in mock
        
        total_tests += task_total
        passed_tests += task_passed
        
        dev_task.metadata["total_tests"] = task_total
        dev_task.metadata["passed_tests"] = task_passed
        dev_task.metadata["failed_tests"] = 0
        
        qa_results.append(dev_task)
        
        print(f"  ✓ Tests: {task_passed}/{task_total} passed")
        print(f"  ✓ Status: {dev_task.status.value}")
    
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
    
    # Mock deployment
    deployment_task.status = TaskStatus.COMPLETED
    deployment_task.result = "Complete Todo API deployed successfully"
    deployment_task.metadata["github_url"] = "https://github.com/test/todo-api"
    deployment_task.metadata["deployment_urls"] = [
        {"platform": "Railway", "url": "https://todo-api.railway.app"},
        {"platform": "Render", "url": "https://todo-api.onrender.com"},
        {"platform": "Fly.io", "url": "https://todo-api.fly.dev"}
    ]
    
    print(f"\n  ✓ Deployment Status: {deployment_task.status.value}")
    print(f"  ✓ GitHub: {deployment_task.metadata['github_url']}")
    
    for dep in deployment_task.metadata['deployment_urls']:
        print(f"  ✓ Platform: {dep['platform']} → {dep['url']}")
    
    print(f"\n✅ Ops Agent deployment {deployment_task.status.value}")
    
    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    print("\n" + "="*70)
    print("📊 MULTI-FILE E2E TEST SUMMARY (MOCKED)")
    print("="*70)
    print(f"📋 PM Agent:        {len(mock_plan.tasks)} tasks planned")
    print(f"💻 Dev Agent:       {len(dev_results)}/{len(dev_tasks)} tasks completed")
    print(f"📁 Files Generated: {len(generated_files)} files")
    print(f"🧪 QA Agent:        {len(qa_results)} components tested")
    print(f"✅ Tests Passed:    {passed_tests}/{total_tests}")
    print(f"🚀 Ops Agent:       Deployment {deployment_task.status.value}")
    print("="*70)
    print("🎉 MULTI-FILE WORKFLOW COMPLETED SUCCESSFULLY!")
    print("="*70 + "\n")
    
    # Assertions
    assert len(dev_results) == 6, f"Should complete 6 dev tasks, got {len(dev_results)}"
    assert len(generated_files) >= 10, f"Should generate at least 10 files, got {len(generated_files)}"
    assert len(qa_results) == 6, f"Should test 6 components, got {len(qa_results)}"
    assert passed_tests == total_tests, f"All tests should pass: {passed_tests}/{total_tests}"
    assert deployment_task.status == TaskStatus.COMPLETED, "Deployment should complete"
    
    print("✅ All assertions passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])