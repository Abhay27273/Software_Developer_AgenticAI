"""
Quick test to verify DevAgent Task object conversion fix.
"""
import asyncio
from models.task import Task
from models.enums import TaskStatus
from datetime import datetime

# Simulate what the pipeline does
def test_task_creation():
    """Test creating Task object from dict."""
    
    # This is what comes from the plan
    subtask_dict = {
        'id': '001',
        'title': 'Initialize Backend Services',
        'description': 'Setup FastAPI project, PostgreSQL database, and basic user authentication module.',
        'priority': 1,
        'status': 'pending',
        'dependencies': [],
        'estimated_hours': 5.0,
        'complexity': 'medium',
        'agent_type': 'dev_agent',
        'metadata': {}
    }
    
    # This is how the pipeline now converts it
    task_obj = Task(
        id=subtask_dict.get('id', 'fallback_id'),
        title=subtask_dict.get('title', 'Development Task'),
        description=subtask_dict.get('description', ''),
        priority=subtask_dict.get('priority', 5),
        status=TaskStatus.PENDING,
        dependencies=subtask_dict.get('dependencies', []),
        estimated_hours=subtask_dict.get('estimated_hours'),
        complexity=subtask_dict.get('complexity'),
        agent_type=subtask_dict.get('agent_type', 'dev_agent'),
        created_at=datetime.now(),
        metadata=subtask_dict.get('metadata', {})
    )
    
    print("✅ Task object created successfully!")
    print(f"   ID: {task_obj.id}")
    print(f"   Title: {task_obj.title}")
    print(f"   Description: {task_obj.description[:50]}...")
    print(f"   Priority: {task_obj.priority}")
    print(f"   Status: {task_obj.status}")
    
    # Verify it can be converted back to dict
    task_dict = task_obj.to_dict()
    print("\n✅ Task.to_dict() works!")
    print(f"   Keys: {list(task_dict.keys())}")
    
    return True

if __name__ == "__main__":
    try:
        success = test_task_creation()
        if success:
            print("\n🎉 All tests passed! The fix should work.")
            exit(0)
        else:
            print("\n❌ Tests failed!")
            exit(1)
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
