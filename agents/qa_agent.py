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
from utils.llm_setup import ask_llm, LLMError
from utils.cache_manager import load_cached_content, save_cached_content
from utils.qa_config import QAConfig
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
        self.qa_config = QAConfig.from_env()
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
        Execute QA workflow based on configured mode (fast or deep).
        """
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_start",
            "task_id": task.id,
            "message": f"🧪 QA Agent: Starting {self.qa_config.mode.upper()} mode testing for '{task.title}'",
            "timestamp": datetime.now().isoformat()
        })

        try:
            if self.qa_config.mode == "fast":
                return await self._fast_qa_mode(task)
            else:
                return await self._deep_qa_mode(task)

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

    async def _fast_qa_mode(self, task: Task) -> Task:
        """
        Fast QA mode: Iterates through each file, performs a quick LLM logic review,
        and broadcasts the result for each file in real-time.
        """
        all_passed = True
        all_issues = []

        try:
            async with asyncio.timeout(self.qa_config.fast_timeout):
                code_files = await self._load_generated_code(task)
                
                if not code_files:
                    task.status = TaskStatus.FAILED
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id, "type": "qa_failed", "task_id": task.id,
                        "message": f"⚠️ No code files found for '{task.title}'", "timestamp": datetime.now().isoformat()
                    })
                    return task

                for filename, content in code_files.items():
                    await self.websocket_manager.broadcast_message({
                        "type": "qa_testing_file", "agent_id": self.agent_id, "task_id": task.id,
                        "file_name": filename, "timestamp": datetime.now().isoformat()
                    })

                    review_result = await self._review_single_file(task, filename, content)
                    
                    file_passed = review_result.get("passed", False)
                    issues = review_result.get("issues", [])
                    
                    if not file_passed:
                        all_passed = False
                        all_issues.extend(issues)

                    await self.websocket_manager.broadcast_message({
                        "type": "qa_file_result", "agent_id": self.agent_id, "task_id": task.id,
                        "file_name": filename, "passed": file_passed,
                        "message": f"{len(issues)} issue(s) found" if issues else "No issues found",
                        "details": "\n".join([i['description'] for i in issues]) if issues else "Clean.",
                        "timestamp": datetime.now().isoformat()
                    })

                # Final task status
                if all_passed:
                    task.status = TaskStatus.COMPLETED
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id, "type": "qa_completed", "task_id": task.id,
                        "message": f"✅ QA Agent (Fast): All files passed logic review for '{task.title}'.",
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    task.status = TaskStatus.FAILED
                    task.metadata["qa_issues"] = all_issues
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id, "type": "qa_failed", "task_id": task.id,
                        "message": f"❌ QA Agent (Fast): Found {len(all_issues)} issues in '{task.title}'. Sending for revision.",
                        "issues": all_issues, "timestamp": datetime.now().isoformat()
                    })
                
                return task
                
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            logger.error(f"Fast QA timeout for task {task.id}")
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id, "type": "qa_timeout", "task_id": task.id,
                "message": f"⏱️ QA Agent (Fast): Timeout after {self.qa_config.fast_timeout}s for '{task.title}'",
                "timestamp": datetime.now().isoformat()
            })
            return task

    async def _review_single_file(self, task: Task, filename: str, code_content: str) -> Dict:
        """Performs LLM logic review on a single file."""
        prompt = f"""You are a code quality reviewer. Review the following Python file.

Task: {task.title}
File: {filename}
```python
{code_content}
```

Provide a FAST logic review focusing on critical bugs, security issues, and major structure problems.

Return your review as JSON with this exact structure:
{{
    "passed": <boolean>,
    "issues": [
        {{"type": "bug|security|structure", "description": "..."}}
    ]
}}

- If the code is good, return "passed": true and an empty issues list.
- If issues are found, return "passed": false and describe them.
Focus on critical issues only. Be concise."""

        try:
            response = await ask_llm(
                prompt, 
                model="gemini-2.5-flash",
                metadata={"agent": self.agent_id, "prompt_name": "fast_qa_single_file_review"}
            )
            
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                # Ensure keys exist
                result.setdefault("passed", not result.get("issues"))
                result.setdefault("issues", [])
                return result
            else:
                logger.warning(f"No JSON found in LLM response for file {filename}")
                return {"passed": False, "issues": [{"type": "parse_error", "description": "Failed to parse LLM review"}]}
                
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"LLM review error for file {filename}: {e}")
            return {"passed": False, "issues": [{"type": "error", "description": f"Review failed: {str(e)}"}]}

    def _truncate_code_for_review(self, code_files: Dict[str, str]) -> Dict[str, str]:
        """Truncate code files to stay within token limits."""
        truncated = {}
        total_chars = 0
        
        for file_path, content in code_files.items():
            if total_chars >= self.qa_config.total_code_limit:
                break
                
            # Truncate individual file
            if len(content) > self.qa_config.max_code_chars_per_file:
                truncated[file_path] = content[:self.qa_config.max_code_chars_per_file] + "\n... (truncated)"
                total_chars += self.qa_config.max_code_chars_per_file
            else:
                truncated[file_path] = content
                total_chars += len(content)
        
        return truncated

    async def _llm_logic_review(self, task: Task, code_files: Dict[str, str]) -> Dict:
        """
        Single LLM call for logic review with structured JSON output.
        Returns: {"confidence": float, "issues": [{"type": str, "description": str, "file": str}]}
        """
        # Format code for review
        code_context = "\n\n".join([
            f"File: {file_path}\n```python\n{content}\n```"
            for file_path, content in code_files.items()
        ])
        
        prompt = f"""You are a code quality reviewer. Review the following code for a task:

Task: {task.title}
Description: {task.description}

Code files:
{code_context}

Provide a FAST logic review focusing on:
1. Critical bugs (syntax errors, runtime errors, logic flaws)
2. Security issues
3. Code structure and organization

Return your review as JSON with this exact structure:
{{
    "confidence": <float 0.0-1.0>,
    "issues": [
        {{"type": "bug|security|structure", "description": "...", "file": "filename.py"}}
    ]
}}

Guidelines:
- confidence 0.9-1.0: Excellent code, no issues
- confidence 0.8-0.9: Good code, minor improvements possible
- confidence 0.5-0.8: Acceptable code with some concerns
- confidence 0.0-0.5: Serious issues requiring fixes

Focus on critical issues only. Be concise."""

        try:
            response = await ask_llm(
                prompt, 
                model="gemini-2.5-flash",
                metadata={"agent": self.agent_id, "prompt_name": "fast_qa_review"}
            )
            
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                return result
            else:
                logger.warning(f"No JSON found in LLM response for task {task.id}")
                return {"confidence": 0.5, "issues": [{"type": "parse_error", "description": "Failed to parse LLM review", "file": "unknown"}]}
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in LLM review for task {task.id}: {e}")
            return {"confidence": 0.5, "issues": [{"type": "parse_error", "description": f"JSON error: {str(e)}", "file": "unknown"}]}
        except Exception as e:
            logger.error(f"LLM review error for task {task.id}: {e}")
            return {"confidence": 0.3, "issues": [{"type": "error", "description": f"Review error: {str(e)}", "file": "unknown"}]}

    async def _deep_qa_mode(self, task: Task) -> Task:
        """
        Deep QA mode: Fast QA + focused pytest generation + execution + one fix attempt.
        Target: <90 seconds with hard timeout.
        """
        try:
            async with asyncio.timeout(self.qa_config.deep_timeout):
                # Start with fast QA
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_progress",
                    "task_id": task.id,
                    "message": f"🔍 Deep QA: Starting fast logic review...",
                    "timestamp": datetime.now().isoformat()
                })
                
                fast_task = await self._fast_qa_mode(task)
                confidence = fast_task.metadata.get("qa_confidence", 0.5) if fast_task.metadata else 0.5
                
                # If fast QA confidence is high enough, skip expensive testing
                if confidence >= 0.9:
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id,
                        "type": "qa_skip_tests",
                        "task_id": task.id,
                        "message": f"⚡ Deep QA: High confidence ({confidence:.2f}), skipping test execution",
                        "timestamp": datetime.now().isoformat()
                    })
                    fast_task.metadata["qa_mode"] = "deep"
                    return fast_task
                
                # Continue with original deep workflow for lower confidence
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "qa_progress",
                    "task_id": task.id,
                    "message": f"🧪 Deep QA: Running comprehensive tests (confidence: {confidence:.2f})...",
                    "timestamp": datetime.now().isoformat()
                })
                
                # Use existing LangGraph workflow with reduced max attempts
                initial_state: QAState = {
                    "task": task,
                    "code_files": {},
                    "test_results": [],
                    "issues_found": [],
                    "fix_attempts": 0,
                    "max_fix_attempts": 1,  # Only one fix attempt in deep mode
                    "current_file": "",
                    "messages": [HumanMessage(content=f"Starting Deep QA for task: {task.title}")],
                    "qa_status": "testing"
                }
                
                final_state = await self._run_workflow(initial_state)
                
                # Update task status
                if final_state["qa_status"] == "completed":
                    task.status = TaskStatus.COMPLETED
                    task.metadata["qa_mode"] = "deep"
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id,
                        "type": "qa_completed",
                        "task_id": task.id,
                        "message": f"✅ QA Agent (Deep): All tests passed for '{task.title}'",
                        "fixes_applied": final_state["fix_attempts"],
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    task.status = TaskStatus.FAILED
                    task.metadata["qa_mode"] = "deep"
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id,
                        "type": "qa_failed",
                        "task_id": task.id,
                        "message": f"❌ QA Agent (Deep): Testing failed for '{task.title}'",
                        "issues": final_state["issues_found"],
                        "timestamp": datetime.now().isoformat()
                    })
                
                return task
                
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            logger.error(f"Deep QA timeout for task {task.id}")
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_timeout",
                "task_id": task.id,
                "message": f"⏱️ QA Agent (Deep): Timeout after {self.qa_config.deep_timeout}s for '{task.title}'",
                "timestamp": datetime.now().isoformat()
            })
            return task

    async def _load_generated_code(self, task: Task) -> Dict[str, str]:
        """Load generated code files for the task."""
        code_files = {}
        
        try:
            # Clean task title to match dev agent's directory naming convention
            clean_title = task.title.lower()
            # Remove common task prefixes (same logic as dev_agent)
            prefixes_to_remove = ['define', 'create', 'implement', 'develop', 'build', 'setup', 'configure']
            for prefix in prefixes_to_remove:
                if clean_title.startswith(prefix + ' '):
                    clean_title = clean_title[len(prefix) + 1:]
                    break
            
            # Clean the title for use as folder name (same logic as dev_agent)
            safe_task_title = "".join(c if c.isalnum() else "_" for c in clean_title).strip('_')
            safe_task_title = "_".join(filter(None, safe_task_title.split('_')))[:50]
            
            # Look for directory matching the pattern
            task_output_dir = Path(DEV_OUTPUT_DIR) / f"plan_{safe_task_title}"
            
            if not task_output_dir.exists():
                logger.warning(f"Task output directory not found: {task_output_dir}")
                return code_files
            
            # Load all Python files from the directory
            for py_file in task_output_dir.glob("*.py"):
                try:
                    content = py_file.read_text(encoding="utf-8")
                    code_files[str(py_file.relative_to(DEV_OUTPUT_DIR))] = content
                except Exception as e:
                    logger.error(f"Error reading file {py_file}: {e}")
            
            logger.info(f"Loaded {len(code_files)} code files for task {task.id}")
            
        except Exception as e:
            logger.error(f"Error loading generated code for task {task.id}: {e}")
        
        return code_files

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
            # Announce testing this file
            await self.websocket_manager.broadcast_message({
                "type": "qa_testing_file",
                "agent_id": self.agent_id,
                "task_id": task.id,
                "file_name": filename,
                "timestamp": datetime.now().isoformat()
            })
            
            file_results = {
                "filename": filename,
                "syntax_check": await self._check_syntax(filename, code_content),
                "style_check": await self._check_style(filename, code_content),
                "runtime_check": await self._check_runtime(filename, code_content),
                "unit_tests": await self._run_generated_tests(filename, code_content, task)
            }
            test_results.append(file_results)
            
            # Determine if file passed
            passed = (
                file_results["syntax_check"].get("passed", False) and
                file_results["style_check"].get("passed", True) and
                file_results["runtime_check"].get("passed", True)
            )
            
            # Get summary of issues
            issues = []
            if not file_results["syntax_check"].get("passed", False):
                issues.extend(file_results["syntax_check"].get("issues", []))
            if not file_results["style_check"].get("passed", True):
                issues.extend(file_results["style_check"].get("issues", []))
            if not file_results["runtime_check"].get("passed", True):
                issues.extend(file_results["runtime_check"].get("issues", []))
            
            issue_summary = f"{len(issues)} issue(s) found" if issues else "No issues found"
            
            # Send result message
            await self.websocket_manager.broadcast_message({
                "type": "qa_file_result",
                "agent_id": self.agent_id,
                "task_id": task.id,
                "file_name": filename,
                "passed": passed,
                "message": issue_summary,
                "details": issue_summary,
                "timestamp": datetime.now().isoformat()
            })
            
            # Report progress (original)
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
        """
        Communicate with Dev Agent for one-time fix.
        After fix, file goes directly to Ops without retesting.
        """
        task = state["task"]
        state["fix_attempts"] += 1
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "qa_dev_communication",
            "task_id": task.id,
            "message": "📞 QA Agent: Requesting ONE-TIME fix from Dev Agent (no retest after fix)...",
            "issues": state["issues_found"],
            "issues_count": len(state["issues_found"]),
            "timestamp": datetime.now().isoformat()
        })
        
        # Log detailed issues for Dev
        logger.info(f"🐛 QA found {len(state['issues_found'])} issues in {task.id}")
        for idx, issue in enumerate(state["issues_found"], 1):
            logger.info(
                f"  Issue {idx}: {issue.get('issue_type', 'unknown')} - "
                f"{issue.get('description', 'No description')}"
            )
        
        try:
            # NOTE: We're NOT actually calling DevAgent.handle_qa_feedback here
            # because the event router will handle routing to the fix queue.
            # This method just communicates the issues to the system.
            
            # Mark that issues have been communicated to Dev
            state["qa_status"] = "communicated_to_dev"
            
            # Store issues in task metadata for Dev to access
            task.metadata['qa_issues'] = state["issues_found"]
            task.metadata['qa_test_results'] = state["test_results"]
            task.metadata['requires_dev_fix'] = True
            
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "qa_dev_fix_requested",
                "task_id": task.id,
                "message": (
                    f"📋 QA Agent: Documented {len(state['issues_found'])} issues for Dev fix. "
                    f"File will go to Ops after fix (no retest)."
                ),
                "issues_summary": [
                    {
                        'type': issue.get('issue_type', 'unknown'),
                        'file': issue.get('file_path', 'unknown'),
                        'description': issue.get('description', '')[:100]  # Truncate for display
                    }
                    for issue in state["issues_found"][:5]  # Show first 5 issues
                ],
                "total_issues": len(state["issues_found"]),
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(
                f"✅ QA Agent: Communicated issues for {task.id} to Dev. "
                f"After fix, file will go directly to Ops."
            )
                
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
        """
        Finalize QA results with new workflow:
        - No issues: PASS (go to Ops)
        - Issues found: FAIL (go to Dev for fix, then directly to Ops)
        """
        if not state["issues_found"]:
            state["qa_status"] = "completed"
            logger.info(f"✅ QA passed for {state['task'].id} - sending to Ops")
        elif state["qa_status"] == "communicated_to_dev":
            # Issues communicated to Dev - mark as failed so pipeline routes to fix
            state["qa_status"] = "failed"
            logger.info(
                f"📋 QA found issues in {state['task'].id}, communicated to Dev. "
                f"After fix, file goes directly to Ops (no retest)"
            )
        else:
            # Unable to handle issues
            state["qa_status"] = "failed"
            logger.warning(
                f"❌ QA unable to handle issues for {state['task'].id}, "
                f"marking as failed"
            )
        
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
        """
        Determine fix strategy: QA only attempts ONE fix, then communicates with Dev.
        After Dev fix, file goes directly to Ops without retesting.
        """
        # If we've already attempted a fix, communicate with Dev (no second attempt)
        if state["fix_attempts"] >= 1:
            logger.info(
                f"🔄 QA already attempted fix. Communicating remaining issues to Dev "
                f"(file will go to Ops after Dev fix, no retest)"
            )
            return "communicate"
        
        if any(issue.get("llm_failed") for issue in state["issues_found"]):
            logger.info("🤖 LLM-related issues found, communicating with Dev")
            return "communicate"

        # Check if issues are simple enough for QA to auto-fix (only once)
        simple_issues = ["syntax", "style"]
        complex_issues = ["runtime", "test_failure", "logic_error"]
        
        has_simple_issues = any(
            issue.get("issue_type") in simple_issues 
            for issue in state["issues_found"]
        )
        has_complex_issues = any(
            issue.get("issue_type") in complex_issues 
            for issue in state["issues_found"]
        )
        
        # Only attempt simple fixes if this is our first attempt
        if has_simple_issues and not has_complex_issues and state["fix_attempts"] == 0:
            logger.info("🔧 QA attempting ONE-TIME simple fix (syntax/style only)")
            return "apply"
        elif has_complex_issues or state["fix_attempts"] > 0:
            logger.info(
                "📞 Complex issues or retry detected, communicating with Dev "
                "(no further QA testing after Dev fix)"
            )
            return "communicate"
        else:
            logger.warning("❌ Unable to categorize issues, failing QA")
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
        prompt_type = "qa_unit_tests"
        cache_task_id = task.id or "unknown_task"
        cached_tests = load_cached_content(cache_task_id, prompt_type, extension="py")

        if cached_tests:
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "info",
                "task_id": task.id,
                "message": "QA Agent: Reusing cached test scaffold for this task.",
                "timestamp": datetime.now().isoformat(),
                "cache_hit": True
            })
            return cached_tests

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
                model="gemini-2.5-flash",
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
            save_cached_content(
                cache_task_id,
                prompt_type,
                test_code,
                extension="py",
                metadata={
                    "agent": self.agent_id,
                    "stored_at": datetime.now().isoformat()
                }
            )
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
                model="gemini-2.5-flash",
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