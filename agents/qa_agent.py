import asyncio
import logging
import subprocess
from pathlib import Path

from models.task import Task
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from utils.llm_setup import ask_llm

# Configure logging
logger = logging.getLogger(__name__)

class QAAgent:
    """
    The QA Agent is responsible for automatically verifying the code produced by the DevAgent.
    It performs syntax checks, style checks (linting), and generates/runs unit tests.
    """
    def __init__(self, websocket_manager: WebSocketManager):
        self.agent_id = "qa_agent"
        self.websocket_manager = websocket_manager

    async def execute_task(self, task: Task) -> Task:
        """
        Executes a series of QA checks on the code associated with a given task.
        """
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_start",
            "task_id": task.id,
            "message": f"🧪 QA started for task: {task.title}",
        })

        try:
            # Match DevAgent output directory and file naming
            task_dir = Path(f"generated_code/dev_outputs/{task.id}_{''.join(c if c.isalnum() else '_' for c in task.title).lower()[:50]}")
            code_path = task_dir / "implementation.py"
            if not code_path.exists():
                raise FileNotFoundError(f"Code file not found at: {code_path}")

            # 1. Run syntax check
            await self._syntax_check(code_path, task)

            # 2. Run flake8 style check
            await self._style_check(code_path, task)

            # 3. Run pre-existing pytest file if it exists
            await self._pytest_check(task)

            # 4. Use LLM to generate and run new unit tests
            await self._llm_autotest(code_path, task)

            # If all checks pass, mark the task as completed
            task.status = TaskStatus.COMPLETED
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_passed",
                "task_id": task.id,
                "message": f"✅ All QA checks passed for {task.title}",
            })

        except Exception as e:
            # If any check fails, mark the task as failed and report the error
            task.status = TaskStatus.FAILED
            logger.error(f"QA failed for task {task.id}: {e}")
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_failed",
                "task_id": task.id,
                "message": f"❌ QA failed for {task.title}",
                "error": str(e),
            })

        return task

    async def _syntax_check(self, code_path: Path, task: Task):
        """Checks the Python code for syntax errors."""
        try:
            with open(code_path, "r", encoding="utf-8") as f:
                code = f.read()
            compile(code, filename=code_path.name, mode='exec')
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_syntax",
                "task_id": task.id,
                "message": "✅ Syntax check passed",
            })
        except SyntaxError as e:
            raise Exception(f"SyntaxError: {str(e)}")

    async def _style_check(self, code_path: Path, task: Task):
        """Runs flake8 to check for PEP8 style compliance."""
        try:
            result = subprocess.run(
                ["flake8", str(code_path)], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if result.returncode == 0:
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_lint",
                    "task_id": task.id,
                    "message": "✅ Code style passed (flake8)",
                })
            else:
                raise Exception(f"flake8 style issues:\n{result.stdout}")
        except FileNotFoundError:
            raise Exception("flake8 is not installed or not in PATH. Please run 'pip install flake8'.")
        except Exception as e:
            raise Exception(f"Style Check Failed: {str(e)}")

    async def _pytest_check(self, task: Task):
        """Runs any pre-existing pytest files for the task."""
        test_file = task_dir / f"test_{task.id}.py"
        if test_file.exists():
            result = subprocess.run(
                ["pytest", str(test_file)], 
                capture_output=True, 
                text=True, 
                check=False
            )
            if result.returncode == 0:
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_pytest",
                    "task_id": task.id,
                    "message": "✅ Pre-existing pytest unit tests passed",
                })
            else:
                raise Exception(f"Pre-existing Pytest failed:\n{result.stdout}\n{result.stderr}")
        else:
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_pytest",
                "task_id": task.id,
                "message": "⚠️ No pre-existing pytest file found, skipping",
            })

    def _get_autotest_prompt(self, code: str, task_description: str) -> str:
        """Creates a detailed prompt for the LLM to generate a pytest test suite."""
        return f"""
You are a Senior QA Engineer tasked with writing a comprehensive and robust unit test suite using pytest.

Your goal is to validate the provided Python code against its original requirements.

**Original Task Description:**
---
{task_description}
---

**Code to Test:**
```python
{code}
```
"""