"""
Test Fast QA Mode
"""
import asyncio
import logging
from pathlib import Path

from models.task import Task
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from agents.qa_agent import QAAgent
from utils.qa_config import QAConfig
from config import DEV_OUTPUT_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_test_code():
    """Create sample code for QA testing."""
    # Create a simple test task output
    task_dir = Path(DEV_OUTPUT_DIR) / "plan_test_calculator" / "calculator_functions"
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a simple Python file
    calculator_code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract b from a."""
    return a - b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

def divide(a, b):
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
'''
    
    (task_dir / "calculator.py").write_text(calculator_code)
    logger.info(f"Created test code at {task_dir}")
    
    return task_dir


async def test_fast_qa():
    """Test Fast QA mode execution."""
    logger.info("=" * 60)
    logger.info("Testing Fast QA Mode")
    logger.info("=" * 60)
    
    # Load QA config
    config = QAConfig.from_env()
    logger.info(f"QA Mode: {config.mode}")
    logger.info(f"Fast Timeout: {config.fast_timeout}s")
    logger.info(f"Confidence Thresholds: pass≥{config.confidence_pass}, flag≥{config.confidence_flag}")
    
    # Create test code
    task_dir = await create_test_code()
    
    # Create mock WebSocket manager
    websocket_manager = WebSocketManager()
    
    # Initialize QA Agent
    qa_agent = QAAgent(websocket_manager)
    
    # Create test task
    test_task = Task(
        id="test_calculator_qa",
        title="calculator_functions",
        description="Test QA for calculator functions",
        priority=3,
        status=TaskStatus.PENDING,
        metadata={
            "plan_id": "test_calculator"
        }
    )
    
    # Execute QA
    logger.info("\n🧪 Starting Fast QA execution...")
    start_time = asyncio.get_event_loop().time()
    
    result_task = await qa_agent.execute_task(test_task)
    
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # Report results
    logger.info("\n" + "=" * 60)
    logger.info("Fast QA Results:")
    logger.info("=" * 60)
    logger.info(f"Status: {result_task.status}")
    logger.info(f"Elapsed Time: {elapsed:.2f}s")
    
    if result_task.metadata:
        confidence = result_task.metadata.get("qa_confidence", "N/A")
        issues = result_task.metadata.get("qa_issues", [])
        qa_mode = result_task.metadata.get("qa_mode", "N/A")
        
        logger.info(f"QA Mode: {qa_mode}")
        logger.info(f"Confidence: {confidence}")
        logger.info(f"Issues Found: {len(issues)}")
        
        if issues:
            logger.info("\nIssues:")
            for i, issue in enumerate(issues, 1):
                logger.info(f"  {i}. [{issue.get('type', 'unknown')}] {issue.get('description', 'N/A')}")
                logger.info(f"     File: {issue.get('file', 'N/A')}")
    
    # Verify performance
    if elapsed <= config.fast_timeout:
        logger.info(f"\n✅ Fast QA completed within timeout ({elapsed:.2f}s ≤ {config.fast_timeout}s)")
    else:
        logger.warning(f"\n⚠️  Fast QA exceeded timeout ({elapsed:.2f}s > {config.fast_timeout}s)")
    
    return result_task


if __name__ == "__main__":
    asyncio.run(test_fast_qa())
