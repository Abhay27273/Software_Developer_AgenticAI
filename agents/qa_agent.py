import asyncio
import logging
import subprocess
import json
import tempfile
import sys
from pathlib import Path
from typing import Dict, List, Optional, TypedDict
from datetime import datetime

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from models.task import Task
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from utils.llm_setup import ask_llm_streaming, ask_llm, LLMError
from config import DEV_OUTPUT_DIR

# Configure logging
logger = logging.getLogger(__name__)

class QAState(TypedDict):
    """State for the QA workflow."""
    task: Task
    code_files: Dict[str, str]  # filename -> content
    test_results: List[Dict]
    issues_found: List[Dict]
    fix_attempts: int
    max_fix_attempts: int
    current_file: str
    messages: List[BaseMessage]
    qa_status: str  # 'testing', 'fixing', 'completed', 'failed'

class CodeIssue(TypedDict):
    """Represents a code issue found during testing."""
    file_path: str
    issue_type: str  # 'syntax', 'runtime', 'test_failure', 'style'
    description: str
    line_number: Optional[int]
    suggested_fix: Optional[str]

class QAAgent:
    """
    Enhanced QA Agent with LangGraph workflow for automatic code testing and fixing.
    Creates a feedback loop with the Dev Agent to automatically fix code issues.
    """
    def __init__(self, websocket_manager: WebSocketManager):
        self.agent_id = "qa_agent"
        self.websocket_manager = websocket_manager
        self.workflow = self._create_workflow()
        
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow for QA testing and fixing."""
        workflow = StateGraph(QAState)
        
        # Add nodes
        workflow.add_node("load_code", self._load_code_files)
        workflow.add_node("run_tests", self._run_comprehensive_tests)
        workflow.add_node("analyze_issues", self._analyze_test_results)
        workflow.add_node("generate_fixes", self._generate_code_fixes)
        workflow.add_node("apply_fixes", self._apply_fixes_to_code)
        workflow.add_node("communicate_with_dev", self._communicate_with_dev_agent)
        workflow.add_node("finalize_qa", self._finalize_qa_results)
        
        # Define the workflow edges
        workflow.set_entry_point("load_code")
        
        workflow.add_edge("load_code", "run_tests")
        workflow.add_conditional_edges(
            "run_tests",
            self._should_analyze_issues,
            {
                "analyze": "analyze_issues",
                "pass": "finalize_qa"
            }
        )
        workflow.add_edge("analyze_issues", "generate_fixes")
        workflow.add_conditional_edges(
            "generate_fixes",
            self._should_apply_fixes,
            {
                "apply": "apply_fixes",
                "communicate": "communicate_with_dev",
                "fail": "finalize_qa"
            }
        )
        workflow.add_edge("apply_fixes", "run_tests")
        workflow.add_edge("communicate_with_dev", "finalize_qa")
        workflow.add_edge("finalize_qa", END)
        
        return workflow.compile()

    async def execute_task(self, task: Task) -> Task:
        """
        Execute QA workflow with automatic fixing using LangGraph.
        """
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_start",
            "task_id": task.id,
            "message": f"🧪 QA Agent: Starting comprehensive testing for '{task.title}'",
            "timestamp": datetime.now().isoformat()
        })

        try:
            # Initialize QA state
            initial_state: QAState = {
                "task": task,
                "code_files": {},
                "test_results": [],
                "issues_found": [],
                "fix_attempts": 0,
                "max_fix_attempts": 5,
                "current_file": "",
                "messages": [HumanMessage(content=f"Starting QA for task: {task.title}")],
                "qa_status": "testing"
            }
            
            # Run the LangGraph workflow
            final_state = await self._run_workflow(initial_state)
            
            # Set task status based on final QA results
            if final_state["qa_status"] == "completed":
                task.status = TaskStatus.COMPLETED
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_completed",
                    "task_id": task.id,
                    "message": f"✅ QA Agent: All tests passed for '{task.title}'",
                    "fixes_applied": final_state["fix_attempts"],
                    "timestamp": datetime.now().isoformat()
                })
            else:
                task.status = TaskStatus.FAILED
                failure_message = f"❌ QA Agent: Testing failed for '{task.title}' after {final_state['fix_attempts']} fix attempts"
                if final_state["fix_attempts"] >= final_state["max_fix_attempts"]:
                    failure_message += ". Escalating to human review for final resolution."
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_failed",
                    "task_id": task.id,
                    "message": failure_message,
                    "issues": final_state["issues_found"],
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            task.status = TaskStatus.FAILED
            logger.error(f"QA Agent workflow failed for task {task.id}: {e}", exc_info=True)
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_error",
                "task_id": task.id,
                "message": f"❌ QA Agent: Workflow error for '{task.title}': {str(e)}",
                "timestamp": datetime.now().isoformat()
            })

        return task

    async def _run_workflow(self, initial_state: QAState) -> QAState:
        """Run the LangGraph workflow asynchronously."""
        current_state = await self._load_code_files(initial_state)

        while True:
            current_state = await self._run_comprehensive_tests(current_state)

            if self._should_analyze_issues(current_state) == "pass":
                # All checks passed
                current_state["qa_status"] = "completed"
                break

            if current_state["fix_attempts"] >= current_state["max_fix_attempts"]:
                current_state["qa_status"] = "failed"
                break

            current_state = await self._analyze_test_results(current_state)
            current_state = await self._generate_code_fixes(current_state)

            decision = self._should_apply_fixes(current_state)

            if decision == "apply":
                current_state = await self._apply_fixes_to_code(current_state)
                if current_state["qa_status"] == "failed":
                    break
                # Loop continues to re-run tests
                continue
            elif decision == "communicate":
                current_state = await self._communicate_with_dev_agent(current_state)
                if current_state["qa_status"] == "failed":
                    break
                # Loop continues with reloaded code and re-testing
                continue
            else:
                current_state["qa_status"] = "failed"
                break

        current_state = await self._finalize_qa_results(current_state)
        return current_state

    # LangGraph Workflow Node Methods
    
    async def _load_code_files(self, state: QAState) -> QAState:
        """Load all code files for the task."""
        task = state["task"]
        
        # Find the task directory using the new naming convention
        clean_title = task.title.lower()
        prefixes_to_remove = ['define', 'create', 'implement', 'develop', 'build', 'setup', 'configure']
        for prefix in prefixes_to_remove:
            if clean_title.startswith(prefix + ' '):
                clean_title = clean_title[len(prefix) + 1:]
                break
        
        safe_task_title = "".join(c if c.isalnum() else "_" for c in clean_title).strip('_')
        safe_task_title = "_".join(filter(None, safe_task_title.split('_')))[:50]
        
        task_dir = DEV_OUTPUT_DIR / f"plan_{safe_task_title}"
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_loading_files",
            "task_id": task.id,
            "message": f"📂 QA Agent: Loading code files from {task_dir.name}",
            "timestamp": datetime.now().isoformat()
        })
        
        code_files = {}
        if task_dir.exists():
            for file_path in task_dir.rglob("*.py"):
                try:
                    relative_key = file_path.relative_to(task_dir).as_posix()
                    content = file_path.read_text(encoding="utf-8")
                    code_files[relative_key] = content
                    logger.info(f"QA Agent: Loaded {relative_key}")
                except Exception as e:
                    logger.warning(f"QA Agent: Failed to load {file_path}: {e}")
        
        if not code_files:
            raise FileNotFoundError(f"No Python files found in {task_dir}")
        
        state["code_files"] = code_files
        state["messages"].append(AIMessage(content=f"Loaded {len(code_files)} code files"))
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_files_loaded",
            "task_id": task.id,
            "message": f"📁 QA Agent: Loaded {len(code_files)} files: {', '.join(code_files.keys())}",
            "timestamp": datetime.now().isoformat()
        })
        
        return state

    async def _run_comprehensive_tests(self, state: QAState) -> QAState:
        """Run comprehensive tests on all code files."""
        task = state["task"]
        test_results = []
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_testing",
            "task_id": task.id,
            "message": "🧪 QA Agent: Running comprehensive tests...",
            "timestamp": datetime.now().isoformat()
        })
        
        for filename, code_content in state["code_files"].items():
            file_results = {
                "filename": filename,
                "syntax_check": await self._check_syntax(filename, code_content),
                "style_check": await self._check_style(filename, code_content),
                "runtime_check": await self._check_runtime(filename, code_content),
                "unit_tests": await self._run_generated_tests(filename, code_content, task)
            }
            test_results.append(file_results)
            
            # Report progress
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_file_tested",
                "task_id": task.id,
                "filename": filename,
                "results": file_results,
                "timestamp": datetime.now().isoformat()
            })
        
        state["test_results"] = test_results
        return state

    async def _analyze_test_results(self, state: QAState) -> QAState:
        """Analyze test results and identify issues."""
        issues_found = []
        code_files = state.get("code_files", {})
        
        for file_result in state["test_results"]:
            filename = file_result["filename"]
            file_code = code_files.get(filename, "")
            
            # Check for syntax issues
            if not file_result["syntax_check"]["passed"]:
                issues_found.append({
                    "file_path": filename,
                    "issue_type": "syntax",
                    "description": file_result["syntax_check"]["error"],
                    "line_number": file_result["syntax_check"].get("line_number"),
                    "suggested_fix": None,
                    "code_context": self._extract_code_context(file_code, file_result["syntax_check"].get("line_number"))
                })
            
            # Check for style issues
            if not file_result["style_check"]["passed"]:
                issues_found.append({
                    "file_path": filename,
                    "issue_type": "style",
                    "description": file_result["style_check"]["error"],
                    "line_number": None,
                    "suggested_fix": None,
                    "code_context": self._extract_code_context(file_code)
                })
            
            # Check for runtime issues
            if not file_result["runtime_check"]["passed"]:
                issues_found.append({
                    "file_path": filename,
                    "issue_type": "runtime",
                    "description": file_result["runtime_check"]["error"],
                    "line_number": None,
                    "suggested_fix": None,
                    "code_context": self._extract_code_context(file_code)
                })
            
            # Check for test failures
            if not file_result["unit_tests"]["passed"]:
                issues_found.append({
                    "file_path": filename,
                    "issue_type": "test_failure",
                    "description": file_result["unit_tests"]["error"],
                    "line_number": None,
                    "suggested_fix": None,
                    "code_context": self._extract_code_context(file_code)
                })
        
        state["issues_found"] = issues_found
        
        if issues_found:
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_issues_found",
                "task_id": state["task"].id,
                "message": f"⚠️ QA Agent: Found {len(issues_found)} issues to fix",
                "issues": issues_found,
                "timestamp": datetime.now().isoformat()
            })
        
        return state

    async def _generate_code_fixes(self, state: QAState) -> QAState:
        """Generate fixes for identified issues using LLM."""
        task = state["task"]
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_generating_fixes",
            "task_id": task.id,
            "message": "🔧 QA Agent: Generating fixes for identified issues...",
            "timestamp": datetime.now().isoformat()
        })
        
        for issue in state["issues_found"]:
            if not issue.get("suggested_fix"):
                fix = await self._generate_fix_for_issue(issue, state["code_files"][issue["file_path"]], task)
                issue["suggested_fix"] = fix
        
        return state

    async def _apply_fixes_to_code(self, state: QAState) -> QAState:
        """Apply generated fixes to the code files."""
        task = state["task"]
        state["fix_attempts"] += 1
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_applying_fixes",
            "task_id": task.id,
            "message": f"🔨 QA Agent: Applying fixes (attempt {state['fix_attempts']})...",
            "timestamp": datetime.now().isoformat()
        })
        
        applied_any_fix = False
        for issue in state["issues_found"]:
            if issue.get("suggested_fix"):
                filename = issue["file_path"]
                original_code = state["code_files"][filename]
                fixed_code = await self._apply_fix_to_code(original_code, issue)
                state["code_files"][filename] = fixed_code
                
                # Save the fixed code back to file
                await self._save_fixed_code(filename, fixed_code, task)
                applied_any_fix = True
        
        # Clear issues for re-testing
        state["issues_found"] = []
        state["qa_status"] = "testing" if applied_any_fix else "failed"
        
        return state

    async def _communicate_with_dev_agent(self, state: QAState) -> QAState:
        """Communicate with Dev Agent for complex issues that need manual intervention."""
        task = state["task"]
        state["fix_attempts"] += 1
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_dev_communication",
            "task_id": task.id,
            "message": "📞 QA Agent: Requesting Dev Agent to fix complex issues...",
            "issues": state["issues_found"],
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Import here to avoid circular imports
            from agents.dev_agent import DevAgent
            
            # Create a Dev Agent instance (in a real system, you'd get this from a registry)
            dev_agent = DevAgent(self.websocket_manager)
            
            # Request Dev Agent to fix the issues
            fixed_task = await dev_agent.handle_qa_feedback(task, state["issues_found"])
            
            if fixed_task.status == TaskStatus.COMPLETED:
                # Reload the fixed code files
                state = await self._load_code_files(state)
                state["qa_status"] = "testing"  # Re-test after fixes
                state["issues_found"] = []  # Clear issues for re-testing
                
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_dev_fixes_received",
                    "task_id": task.id,
                    "message": "✅ QA Agent: Received fixes from Dev Agent, re-testing...",
                    "timestamp": datetime.now().isoformat()
                })
            else:
                state["qa_status"] = "failed"
                
        except Exception as e:
            logger.error(f"QA Agent: Failed to communicate with Dev Agent: {e}")
            state["qa_status"] = "failed"
            
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_dev_communication_failed",
                "task_id": task.id,
                "message": f"❌ QA Agent: Failed to communicate with Dev Agent: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        
        return state

    async def _finalize_qa_results(self, state: QAState) -> QAState:
        """Finalize QA results and determine final status."""
        if not state["issues_found"]:
            state["qa_status"] = "completed"
        elif state["fix_attempts"] >= state["max_fix_attempts"]:
            state["qa_status"] = "failed"
        
        return state

    # Conditional edge functions
    
    def _should_analyze_issues(self, state: QAState) -> str:
        """Determine if we should analyze issues or if tests passed."""
        has_failures = any(
            not result["syntax_check"]["passed"] or 
            not result["style_check"]["passed"] or 
            not result["runtime_check"]["passed"] or 
            not result["unit_tests"]["passed"]
            for result in state["test_results"]
        )
        return "analyze" if has_failures else "pass"

    def _should_apply_fixes(self, state: QAState) -> str:
        """Determine if we should apply fixes, communicate with dev, or fail."""
        if state["fix_attempts"] >= state["max_fix_attempts"]:
            return "fail"
        
        if any(issue.get("llm_failed") for issue in state["issues_found"]):
            return "communicate"

        # Check if issues are simple enough to auto-fix
        simple_issues = ["syntax", "style"]
        complex_issues = ["runtime", "test_failure"]
        
        has_simple_issues = any(issue["issue_type"] in simple_issues for issue in state["issues_found"])
        has_complex_issues = any(issue["issue_type"] in complex_issues for issue in state["issues_found"])
        
        if has_simple_issues and not has_complex_issues:
            return "apply"
        elif has_complex_issues:
            return "communicate"
        else:
            return "fail"    
# Helper methods for testing and fixing

    def _extract_code_context(self, code_content: str, line_number: Optional[int] = None, window: int = 6) -> str:
        """Extract a snippet of code around a line number for context."""
        if not code_content:
            return ""

        lines = code_content.splitlines()
        if not lines:
            return ""

        if line_number and 1 <= line_number <= len(lines):
            start = max(0, line_number - window - 1)
            end = min(len(lines), line_number + window)
            snippet = lines[start:end]
        else:
            # Provide the first few lines as context when line number unavailable
            snippet = lines[: min(len(lines), window * 2)]

        return "\n".join(snippet)

    def _is_llm_fallback_response(self, response: Optional[str]) -> bool:
        """Detect whether the LLM response is a fallback/apology instead of real code."""
        if not response:
            return True

        normalized = response.strip().lower()
        if not normalized:
            return True

        fallback_markers = (
            "i apologize",
            "fallback response",
            "llm generation failed"
        )
        return any(marker in normalized for marker in fallback_markers)

    def _flag_issue_for_manual_review(self, issue: Dict, reason: str) -> None:
        """Tag an issue so the workflow escalates to the Dev Agent."""
        issue["llm_failed"] = True
        issue["description"] = f"{issue['description']} (Manual review required: {reason})"

    
    async def _check_syntax(self, filename: str, code_content: str) -> Dict:
        """Check Python syntax."""
        try:
            compile(code_content, filename, 'exec')
            return {"passed": True, "error": None}
        except SyntaxError as e:
            return {
                "passed": False, 
                "error": f"SyntaxError: {str(e)}", 
                "line_number": e.lineno
            }
        except Exception as e:
            return {"passed": False, "error": f"Compilation error: {str(e)}"}

    async def _check_style(self, filename: str, code_content: str) -> Dict:
        """Check code style using flake8."""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code_content)
                temp_path = f.name
            
            result = subprocess.run(
                ["flake8", temp_path, "--max-line-length=100"], 
                capture_output=True, 
                text=True, 
                check=False
            )
            
            Path(temp_path).unlink()  # Clean up temp file
            
            if result.returncode == 0:
                return {"passed": True, "error": None}
            else:
                return {"passed": False, "error": f"Style issues: {result.stdout}"}
                
        except FileNotFoundError:
            return {"passed": True, "error": "flake8 not installed, skipping style check"}
        except Exception as e:
            return {"passed": False, "error": f"Style check failed: {str(e)}"}

    async def _check_runtime(self, filename: str, code_content: str) -> Dict:
        """Check for basic runtime issues."""
        try:
            # Create a temporary file and try to import it
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code_content)
                temp_path = f.name
            
            # Try to execute the code in a subprocess to catch runtime errors
            result = subprocess.run(
                [sys.executable, "-c", f"exec(open('{temp_path}').read())"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            Path(temp_path).unlink()  # Clean up temp file
            
            if result.returncode == 0:
                return {"passed": True, "error": None}
            else:
                return {"passed": False, "error": f"Runtime error: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"passed": False, "error": "Code execution timeout"}
        except Exception as e:
            return {"passed": False, "error": f"Runtime check failed: {str(e)}"}

    async def _run_generated_tests(self, filename: str, code_content: str, task: Task) -> Dict:
        """Generate and run unit tests for the code."""
        try:
            # Generate test code using LLM
            test_code = await self._generate_unit_tests(code_content, task)
            
            if not test_code:
                return {"passed": True, "error": "No tests generated"}
            
            # Write test code to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as f:
                f.write(test_code)
                test_path = f.name
            
            # Write original code to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code_content)
                code_path = f.name
            
            # Run pytest on the test file
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_path, "-v"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            # Clean up temp files
            Path(test_path).unlink()
            Path(code_path).unlink()
            
            if result.returncode == 0:
                return {"passed": True, "error": None, "output": result.stdout}
            else:
                return {"passed": False, "error": f"Test failures: {result.stdout}\n{result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"passed": False, "error": "Test execution timeout"}
        except Exception as e:
            return {"passed": False, "error": f"Test generation/execution failed: {str(e)}"}

    async def _generate_unit_tests(self, code_content: str, task: Task) -> str:
        """Generate unit tests using LLM."""
        prompt = f"""
You are a Senior QA Engineer. Generate comprehensive pytest unit tests for the following Python code.

Task Description: {task.description}
Code to Test:
```python
{code_content}
```

Requirements:
1. Generate complete, runnable pytest test cases
2. Test all public functions and methods
3. Include edge cases and error conditions
4. Use proper assertions and test structure
5. Add docstrings to test functions
6. Mock external dependencies if needed

Return ONLY the test code, no explanations:
"""
        
        try:
            test_code = await ask_llm(
                user_prompt=prompt,
                system_prompt="You are a QA engineer generating pytest unit tests. Return only executable Python test code.",
                model="gemini-2.5-pro",
                temperature=0.3,
                validate_json=False
            )
            if self._is_llm_fallback_response(test_code):
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_llm_warning",
                    "task_id": task.id,
                    "message": "⚠️ QA Agent: LLM could not generate unit tests automatically. Proceeding without tests.",
                    "timestamp": datetime.now().isoformat()
                })
                return ""
            return test_code
        except Exception as e:
            logger.error(f"Failed to generate unit tests: {e}")
            return ""

    async def _generate_fix_for_issue(self, issue: Dict, code_content: str, task: Task) -> str:
        """Generate a fix for a specific issue using LLM."""
        prompt = f"""
You are a Senior Software Developer. Fix the following issue in the Python code.

Issue Type: {issue['issue_type']}
Issue Description: {issue['description']}
File: {issue['file_path']}
{f"Line: {issue['line_number']}" if issue.get('line_number') else ""}

{"Code Context:\n```python\n" + issue.get('code_context', '') + "\n```" if issue.get('code_context') else ""}

Original Code:
```python
{code_content}
```

Task Context: {task.description}

Requirements:
1. Fix ONLY the specific issue mentioned
2. Maintain the original functionality
3. Follow Python best practices
4. Return the complete corrected code
5. Do not add unnecessary changes

Return ONLY the fixed code, no explanations:
"""
        
        try:
            fixed_code = await ask_llm(
                user_prompt=prompt,
                system_prompt="You are a software developer fixing code issues. Return only the corrected Python code.",
                model="gemini-2.5-pro",
                temperature=0.2,
                validate_json=False
            )
            if self._is_llm_fallback_response(fixed_code):
                self._flag_issue_for_manual_review(issue, "LLM returned fallback response while generating fix")
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_llm_warning",
                    "task_id": task.id,
                    "message": f"⚠️ QA Agent: Automated fix unavailable for {issue['file_path']}. Requesting Dev Agent support.",
                    "timestamp": datetime.now().isoformat()
                })
                return code_content
            return fixed_code
        except Exception as e:
            logger.error(f"Failed to generate fix for issue: {e}")
            self._flag_issue_for_manual_review(issue, f"LLM error: {str(e)}")
            return code_content  # Return original if fix generation fails

    async def _apply_fix_to_code(self, original_code: str, issue: Dict) -> str:
        """Apply a suggested fix to the code."""
        if issue.get("suggested_fix"):
            return issue["suggested_fix"]
        return original_code

    async def _save_fixed_code(self, filename: str, fixed_code: str, task: Task):
        """Save the fixed code back to the file system."""
        try:
            # Reconstruct the file path
            clean_title = task.title.lower()
            prefixes_to_remove = ['define', 'create', 'implement', 'develop', 'build', 'setup', 'configure']
            for prefix in prefixes_to_remove:
                if clean_title.startswith(prefix + ' '):
                    clean_title = clean_title[len(prefix) + 1:]
                    break
            
            safe_task_title = "".join(c if c.isalnum() else "_" for c in clean_title).strip('_')
            safe_task_title = "_".join(filter(None, safe_task_title.split('_')))[:50]
            
            task_dir = DEV_OUTPUT_DIR / f"plan_{safe_task_title}"
            file_path = task_dir / filename
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the fixed code
            file_path.write_text(fixed_code, encoding="utf-8")
            
            # Notify about the fix
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_code_fixed",
                "task_id": task.id,
                "filename": filename,
                "message": f"🔧 QA Agent: Applied fix to {filename}",
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"QA Agent: Applied fix to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save fixed code for {filename}: {e}")