import os
import json
import uuid
import logging
import re
from datetime import datetime
from pathlib import Path
from config import DEV_OUTPUT_DIR
from typing import Optional, Callable, AsyncGenerator, List, Dict, Set
import shutil
import asyncio
from collections import defaultdict

from models.task import Task
from models.plan import Plan
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from utils.llm_setup import ask_llm_streaming, LLMError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output folder for dev agent results
DEV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class DevAgent:
    def __init__(self, websocket_manager: WebSocketManager = None):
        self.agent_id = "dev_agent"
        self.websocket_manager = websocket_manager or WebSocketManager()
        self.current_plan = None
        self.plan_dir = Path.cwd() / "generated_code" / "plans" / "parsed"

        # Enhanced coordination attributes
        self.pending_tasks: Dict[str, Task] = {}  # All tasks in the plan
        self.completed_tasks: Set[str] = set()    # Completed task IDs
        self.in_progress_tasks: Set[str] = set()  # Currently processing task IDs
        self.task_queue: List[Task] = []          # Queue of ready-to-execute tasks
        self.plan_context: Dict = {}              # Store plan context for better task understanding
        self.dependency_graph: Dict[str, List[str]] = defaultdict(list)  # Task dependencies
        self.waiting_for_dependencies: Dict[str, Set[str]] = defaultdict(set)  # Track what each task is waiting for

        # Communication flags
        self.is_plan_complete = False # Flag from PM Agent that no more tasks will be sent
        self.is_processing_active = False # Flag for dev agent to run task processing
        self.max_concurrent_tasks = 2  # Allow parallel processing where possible

    async def handle_plan_start(self, plan_id: str, plan_title: str, plan_description: str):
        """Handle the start of a new plan from PM Agent."""
        logger.info(f"Dev Agent: New plan started - {plan_title} (ID: {plan_id})")

        # Reset state for new plan
        self.pending_tasks.clear()
        self.completed_tasks.clear()
        self.in_progress_tasks.clear()
        self.task_queue.clear()
        self.dependency_graph.clear()
        self.waiting_for_dependencies.clear()
        self.is_plan_complete = False
        self.is_processing_active = True

        # Store plan context
        self.plan_context = {
            "id": plan_id,
            "title": plan_title,
            "description": plan_description,
            "started_at": datetime.now().isoformat()
        }

        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "plan_acknowledgment",
            "plan_id": plan_id,
            "message": f"Dev Agent: Ready to receive tasks for plan '{plan_title}'",
            "timestamp": datetime.now().isoformat()
        })

    async def handle_task_from_pm(self, task: Task):
        """Handle a new task received from PM Agent."""
        logger.info(f"Dev Agent: Received task '{task.title}' (ID: {task.id})")

        # Store the task
        self.pending_tasks[task.id] = task

        # Build dependency graph
        if task.dependencies:
            self.dependency_graph[task.id] = task.dependencies
            self.waiting_for_dependencies[task.id] = set(task.dependencies)

        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "task_received",
            "task_id": task.id,
            "title": task.title,
            "dependencies": task.dependencies,
            "message": f"Dev Agent: Received task '{task.title}'. Checking dependencies...",
            "timestamp": datetime.now().isoformat()
        })

        # Check if this task can be executed immediately
        await self._evaluate_task_readiness(task)

    async def handle_plan_complete(self, plan_id: str, total_tasks: int):
        """Handle notification that PM Agent has finished generating all tasks."""
        logger.info(f"Dev Agent: Plan generation complete. Total tasks: {total_tasks}")
        self.is_plan_complete = True

        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "plan_complete_ack",
            "plan_id": plan_id,
            "total_tasks": total_tasks,
            "pending_tasks": len(self.pending_tasks),
            "ready_tasks": len(self.task_queue),
            "message": f"Dev Agent: Plan complete. Processing {len(self.task_queue)} ready tasks...",
            "timestamp": datetime.now().isoformat()
        })

        # Process any remaining tasks that might be ready
        await self._process_ready_tasks()
        await self._check_plan_completion_and_consolidate()

    async def _evaluate_task_readiness(self, task: Task):
        """Evaluate if a task is ready to be executed based on dependencies."""
        if not task.dependencies:
            # No dependencies - ready to execute
            await self._add_to_execution_queue(task)
            return

        # Check if all dependencies are completed
        unmet_dependencies = []
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                unmet_dependencies.append(dep_id)

        if not unmet_dependencies:
            # All dependencies met - ready to execute
            await self._add_to_execution_queue(task)
        else:
            # Update waiting list
            self.waiting_for_dependencies[task.id] = set(unmet_dependencies)
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_waiting",
                "task_id": task.id,
                "title": task.title,
                "waiting_for": unmet_dependencies,
                "message": f"Dev Agent: Task '{task.title}' waiting for dependencies: {unmet_dependencies}",
                "timestamp": datetime.now().isoformat()
            })

    async def _add_to_execution_queue(self, task: Task):
        """Add a task to the execution queue."""
        if task.id not in [t.id for t in self.task_queue]:
            self.task_queue.append(task)
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_queued",
                "task_id": task.id,
                "title": task.title,
                "queue_position": len(self.task_queue),
                "message": f"Dev Agent: Task '{task.title}' added to execution queue (position {len(self.task_queue)})",
                "timestamp": datetime.now().isoformat()
            })

            # Try to process tasks immediately
            await self._process_ready_tasks()

    async def _process_ready_tasks(self):
        """Process tasks that are ready for execution."""
        if not self.is_processing_active:
            return

        # Process tasks up to max concurrent limit
        while (len(self.in_progress_tasks) < self.max_concurrent_tasks and
               self.task_queue and
               self.is_processing_active):

            task = self.task_queue.pop(0)
            if task.id not in self.in_progress_tasks:
                # Start processing this task
                asyncio.create_task(self._execute_task_with_coordination(task))

    async def _execute_task_with_coordination(self, task: Task):
        """Execute a task with proper coordination and dependency management."""
        if task.id in self.in_progress_tasks:
            return  # Already processing

        self.in_progress_tasks.add(task.id)

        try:
            # Add plan context to task for better LLM understanding
            enhanced_task = self._enhance_task_with_context(task)

            # Execute the task
            completed_task = await self.execute_task(enhanced_task)

            # Mark as completed
            self.completed_tasks.add(task.id)
            self.in_progress_tasks.discard(task.id)

            # Check if this completion unblocks other tasks
            await self._check_unblocked_tasks(task.id)

            # Check if the entire plan is now complete and needs consolidation
            await self._check_plan_completion_and_consolidate()

        except Exception as e:
            logger.error(f"Dev Agent: Failed to execute task {task.id}: {e}", exc_info=True)
            self.in_progress_tasks.discard(task.id)
            # Mark as failed but continue processing other tasks
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_failed",
                "task_id": task.id,
                "error": str(e),
                "message": f"Dev Agent: Task '{task.title}' failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })

    def _enhance_task_with_context(self, task: Task) -> Task:
        """Enhance task with plan context for better LLM understanding."""
        if not self.plan_context:
            return task

        # Create enhanced description with context
        context_info = f"""
=== PROJECT CONTEXT ===
Project: {self.plan_context.get('title', 'Unknown')}
Description: {self.plan_context.get('description', 'No description')}
Current Task: {len(self.completed_tasks) + 1} of {len(self.pending_tasks)}
=== TASK DEPENDENCIES ===
"""

        if task.dependencies:
            context_info += f"This task depends on: {', '.join(task.dependencies)}\n"
            for dep_id in task.dependencies:
                dep_task = self.pending_tasks.get(dep_id)
                if dep_task:
                    context_info += f"- {dep_id}: {dep_task.title}\n"
        else:
            context_info += "This task has no dependencies.\n"

        # Add information about completed tasks for context
        if self.completed_tasks:
            context_info += f"\n=== COMPLETED TASKS ===\n"
            for completed_id in list(self.completed_tasks)[-3:]:  # Last 3 completed
                completed_task = self.pending_tasks.get(completed_id)
                if completed_task:
                    context_info += f"- {completed_id}: {completed_task.title}\n"

        # Create enhanced task
        enhanced_task = Task(
            id=task.id,
            title=task.title,
            description=task.description + context_info,
            priority=task.priority,
            status=task.status,
            dependencies=task.dependencies,
            estimated_hours=task.estimated_hours,
            complexity=task.complexity,
            agent_type=task.agent_type
        )

        return enhanced_task

    async def _check_unblocked_tasks(self, completed_task_id: str):
        """Check if completing a task unblocks other tasks."""
        unblocked_tasks = []

        for task_id, waiting_deps in self.waiting_for_dependencies.items():
            if completed_task_id in waiting_deps:
                waiting_deps.remove(completed_task_id)

                # If no more dependencies, task is ready
                if not waiting_deps and task_id in self.pending_tasks:
                    task = self.pending_tasks[task_id]
                    unblocked_tasks.append(task)
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id,
                        "type": "task_unblocked",
                        "task_id": task_id,
                        "title": task.title,
                        "unblocked_by": completed_task_id,
                        "message": f"Dev Agent: Task '{task.title}' unblocked by completion of {completed_task_id}",
                        "timestamp": datetime.now().isoformat()
                    })

        # Add unblocked tasks to execution queue
        for task in unblocked_tasks:
            await self._add_to_execution_queue(task)

    async def _check_plan_completion_and_consolidate(self):
        """Check if all tasks are completed and initiate consolidation if so."""
        if (self.is_plan_complete and len(self.completed_tasks) == len(self.pending_tasks)):
            logger.info("All tasks for the plan are complete. Initiating final output consolidation.")
            await self._finalize_plan_output()

    async def _finalize_plan_output(self):
        """Consolidate the final deployable files into a 'dist' folder."""
        dist_dir = DEV_OUTPUT_DIR / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        dist_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Dev Agent: Consolidating final outputs into '{dist_dir}'")

        consolidated_files = []
        for task_dir in DEV_OUTPUT_DIR.iterdir():
            if task_dir.is_dir() and task_dir.name != "dist":
                for file_path in task_dir.iterdir():
                    if file_path.suffix.lower() in ['.html', '.js', '.css']:
                        try:
                            # Use file name as target name (e.g. index.html)
                            target_file = dist_dir / file_path.name
                            shutil.copy(file_path, target_file)
                            consolidated_files.append(str(target_file.relative_to(DEV_OUTPUT_DIR)))
                            logger.info(f"Copied {file_path} to {target_file}")
                        except shutil.SameFileError:
                            logger.warning(f"Skipping copy, source and destination are the same file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to copy file {file_path}: {e}")

        if consolidated_files:
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "plan_finalized",
                "plan_id": self.plan_context.get("id"),
                "message": "Dev Agent: Final output consolidated successfully.",
                "output_directory": str(dist_dir.relative_to(DEV_OUTPUT_DIR.parent)),
                "files": consolidated_files,
                "timestamp": datetime.now().isoformat()
            })
        else:
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "plan_finalization_failed",
                "plan_id": self.plan_context.get("id"),
                "message": "Dev Agent: No final output files found to consolidate.",
                "timestamp": datetime.now().isoformat()
            })

    async def get_execution_status(self) -> dict:
        """Get current execution status."""
        return {
            "agent_id": self.agent_id,
            "plan_id": self.plan_context.get("id"),
            "plan_title": self.plan_context.get("title"),
            "total_tasks": len(self.pending_tasks),
            "completed_tasks": len(self.completed_tasks),
            "in_progress_tasks": len(self.in_progress_tasks),
            "queued_tasks": len(self.task_queue),
            "waiting_tasks": len([t for t in self.waiting_for_dependencies.values() if t]),
            "is_plan_complete": self.is_plan_complete,
            "is_processing_active": self.is_processing_active,
            "timestamp": datetime.now().isoformat()
        }

    async def pause_processing(self):
        """Pause task processing."""
        self.is_processing_active = False
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "processing_paused",
            "message": "Dev Agent: Processing paused",
            "timestamp": datetime.now().isoformat()
        })

    async def resume_processing(self):
        """Resume task processing."""
        self.is_processing_active = True
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "processing_resumed",
            "message": "Dev Agent: Processing resumed",
            "timestamp": datetime.now().isoformat()
        })
        await self._process_ready_tasks()

    def cleanup_all_outputs(self):
        """
        Deletes all files and folders in the dev_outputs directory.
        Ensures the directory is re-created empty if it was deleted.
        """
        logger.info(f"Initiating cleanup of Dev Agent output directory: {DEV_OUTPUT_DIR}")
        if DEV_OUTPUT_DIR.exists():
            try:
                shutil.rmtree(DEV_OUTPUT_DIR)
                logger.info(f"Cleaned directory: {DEV_OUTPUT_DIR}")
            except Exception as e:
                logger.warning(f"Failed to delete directory {DEV_OUTPUT_DIR}: {e}")
        DEV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {DEV_OUTPUT_DIR}")

    def clear_task_output(self, task_id: str):
        """
        Clears output files and directories for a specific task within the dev_outputs folder.
        """
        logger.info(f"Clearing previous output for task ID: {task_id}")
        for item in DEV_OUTPUT_DIR.iterdir():
            if item.name.startswith(f"{task_id}_"):
                try:
                    if item.is_file():
                        item.unlink()
                        logger.debug(f"Deleted file: {item}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        logger.debug(f"Deleted directory: {item}")
                except Exception as e:
                    logger.warning(f"Failed to delete {item} for task {task_id}: {e}")

    def _get_system_prompt(self) -> str:
        return """You are a Senior Full-Stack Software Developer AI Agent with 10+ years of experience in production-grade software development.

Your Core Expertise:
Backend Development: Python (FastAPI, Django, Flask), Node.js, Java, Go
Frontend Development: React, Vue.js, Angular, HTML/CSS, JavaScript/TypeScript
Database Systems: PostgreSQL, MySQL, MongoDB, Redis, SQLite
Cloud & DevOps: AWS, Docker, Kubernetes, CI/CD pipelines
Architecture Patterns: Microservices, REST APIs, GraphQL, Event-driven architecture
Security: Authentication, authorization, input validation, SQL injection prevention
Performance: Caching, database optimization, async programming, load balancing
Testing: Unit tests, integration tests, mocking, test-driven development

Code Quality Standards:
✅ Production-Ready: Code that can be deployed immediately to production
✅ Security-First: Implement proper authentication, input validation, and security headers
✅ Performance-Optimized: Efficient algorithms, proper database indexing, caching strategies
✅ Error Handling: Comprehensive exception handling and logging
✅ Documentation: Clear docstrings, comments, and inline documentation
✅ Testing: Include unit tests and integration tests where applicable
✅ Scalability: Design for horizontal scaling and high availability
✅ Maintainability: Clean, readable code following SOLID principles
✅ Standards Compliance: Follow PEP 8, ESLint, and industry best practices

CRITICAL OUTPUT FORMAT REQUIREMENTS:
1. SEPARATE CODE FROM DOCUMENTATION:
   - Put ALL executable code in ```language code blocks with filename comments
   - Put ALL explanations, setup instructions, and documentation OUTSIDE code blocks
   - Example format:
     ```python
     # filename.py
     def my_function():
         return "Hello World"
     ```

2. MULTIPLE FILES:
   - Create separate code blocks for each file
   - Use clear filename comments: ```python # main.py
   - Include all necessary files: models, services, utilities, tests, configs

3. CLEAN CODE BLOCKS:
   - Code blocks should contain ONLY executable code and inline comments
   - NO markdown explanations inside code blocks
   - NO setup instructions inside code blocks
   - NO architecture descriptions inside code blocks

4. DOCUMENTATION OUTSIDE CODE:
   - Provide setup instructions, explanations, and architecture notes outside code blocks
   - Use markdown headers (##) for documentation sections
   - Explain dependencies, configuration, and deployment steps

Context Awareness:
Pay attention to the PROJECT CONTEXT provided in the task description
Consider how this task fits into the overall project architecture
Build upon previously completed tasks when mentioned in dependencies
Ensure consistency with the project's overall technical stack and patterns

Your code should be immediately deployable to production environments, with clear separation between executable code and supporting documentation."""

    def _construct_prompt(self, task: Task) -> str:
        return f"""
## Task Details:
**Title**: {task.title}
**Description**: {task.description}
**Estimated Hours**: {task.estimated_hours}
**Complexity**: {task.complexity}
**Dependencies**: {task.dependencies}
## Implementation Requirements:
### 1. **Complete Production Implementation**
- Provide full, working code that can be deployed to production immediately
- Include all necessary files, configurations, and dependencies
- Implement proper error handling, logging, and monitoring
- Add comprehensive security measures and input validation
### 2. **Architecture & Design**
- Follow microservices architecture patterns where applicable
- Implement clean code principles and SOLID design patterns
- Use appropriate design patterns (Factory, Strategy, Observer, etc.)
- Ensure scalability and maintainability
### 3. **Security Implementation**
- Implement authentication and authorization
- Add input validation and sanitization
- Prevent SQL injection, XSS, and CSRF attacks
- Include rate limiting and security headers
- Use secure password hashing and JWT tokens
### 4. **Performance Optimization**
- Implement caching strategies (Redis, in-memory)
- Optimize database queries and use proper indexing
- Add async/await patterns for I/O operations
- Implement connection pooling and resource management
- Add pagination for large datasets
### 5. **Context Integration**
- Consider the project context and dependencies mentioned above
- Ensure compatibility with previously completed tasks
- Follow established patterns and conventions from the project
- Build incrementally on the existing foundation
Please provide a complete, production-ready implementation that follows enterprise-grade software development practices."""

    async def _stream_code_from_llm(self, task: Task) -> str:
        """
        Calls the LLM in streaming mode for code generation,
        broadcasts chunks, and returns the full concatenated response.
        """
        system_prompt = self._get_system_prompt()
        user_prompt = self._construct_prompt(task)

        full_code_content = ""

        async def stream_chunk_callback(chunk: str):
            nonlocal full_code_content
            full_code_content += chunk
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "dev_agent_llm_streaming_chunk",
                "task_id": task.id,
                "content": chunk,
                "timestamp": datetime.now().isoformat()
            })

        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "llm_request",
            "task_id": task.id,
            "timestamp": datetime.now().isoformat(),
            "message": f"Dev Agent: Requesting code for '{task.title}' (streaming LLM response)..."
        })

        try:
            async for _ in ask_llm_streaming(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                model="gemini-2.5-pro",
                temperature=0.3,
                callback=stream_chunk_callback
            ):
                pass

            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "llm_response_complete",
                "task_id": task.id,
                "timestamp": datetime.now().isoformat(),
                "message": f"Dev Agent: LLM response stream completed for task '{task.title}'."
            })

            return full_code_content

        except LLMError as e:
            logger.error(f"Dev Agent LLM streaming failed for task {task.id}: {e}", exc_info=True)
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "error",
                "task_id": task.id,
                "message": f"Dev Agent: LLM streaming error for '{task.title}': {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            raise

        except Exception as e:
            logger.error(f"An unexpected error occurred during Dev Agent LLM streaming for task {task.id}: {e}", exc_info=True)
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "error",
                "task_id": task.id,
                "message": f"Dev Agent: An unexpected error occurred during LLM streaming for '{task.title}': {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            raise

    def _extract_code_blocks(self, llm_response: str) -> dict:
        """
        Extract code blocks from LLM response and separate them from documentation.
        Returns a dictionary with 'code_files' and 'documentation'.
        """
        import re
        
        # Find all code blocks with language specification
        code_pattern = r'```(\w+)?\s*(?:#\s*(.+?))?\n(.*?)```'
        matches = re.findall(code_pattern, llm_response, re.DOTALL)
        
        code_files = {}
        documentation_parts = []
        last_end = 0
        
        # Process each code block
        for match in re.finditer(code_pattern, llm_response, re.DOTALL):
            # Add text before this code block as documentation
            doc_before = llm_response[last_end:match.start()].strip()
            if doc_before:
                documentation_parts.append(doc_before)
            
            language = match.group(1) or 'text'
            comment_line = match.group(2) or ''
            code_content = match.group(3).strip()
            
            # Determine filename from comment or use default
            if comment_line:
                # Extract filename from comment like "# filename.py"
                filename_match = re.search(r'([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)', comment_line)
                if filename_match:
                    filename = filename_match.group(1)
                else:
                    filename = f"code.{language}"
            else:
                # Use language extension
                ext_map = {
                    'python': 'py', 'javascript': 'js', 'typescript': 'ts',
                    'html': 'html', 'css': 'css', 'json': 'json',
                    'yaml': 'yml', 'sql': 'sql', 'bash': 'sh'
                }
                ext = ext_map.get(language.lower(), 'txt')
                filename = f"code.{ext}"
            
            code_files[filename] = {
                'content': code_content,
                'language': language
            }
            
            last_end = match.end()
        
        # Add remaining text as documentation
        doc_after = llm_response[last_end:].strip()
        if doc_after:
            documentation_parts.append(doc_after)
        
        # If no code blocks found, treat entire response as code
        if not code_files:
            code_files['main_code.py'] = {
                'content': llm_response.strip(),
                'language': 'python'
            }
            documentation_parts = []
        
        return {
            'code_files': code_files,
            'documentation': '\n\n'.join(documentation_parts).strip()
        }

    async def execute_task(self, task: Task) -> Task:
        """
        Executes a single development task, streaming LLM response to UI.
        Separates code from documentation and saves them appropriately.
        Returns the updated Task object.
        """
        logger.info(f"Dev Agent: Starting task '{task.title}' (ID: {task.id})")
        task.status = TaskStatus.IN_PROGRESS

        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "task_status_update",
            "task_id": task.id,
            "status": task.status.value,
            "message": f"Dev Agent started task: '{task.title}'",
            "timestamp": datetime.now().isoformat()
        })

        # Create task-specific directory with clean naming
        # Extract meaningful name from task title, removing common prefixes
        clean_title = task.title.lower()
        # Remove common task prefixes
        prefixes_to_remove = ['define', 'create', 'implement', 'develop', 'build', 'setup', 'configure']
        for prefix in prefixes_to_remove:
            if clean_title.startswith(prefix + ' '):
                clean_title = clean_title[len(prefix) + 1:]
                break
        
        # Clean the title for use as filename/folder name
        safe_task_title = "".join(c if c.isalnum() else "_" for c in clean_title).strip('_')
        # Remove multiple underscores and limit length
        safe_task_title = "_".join(filter(None, safe_task_title.split('_')))[:50]
        
        task_dir = DEV_OUTPUT_DIR / f"plan_{safe_task_title}"

        self.clear_task_output(task.id)
        task_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Dev Agent: Task output directory created: {task_dir}")

        try:
            # Get full LLM response
            llm_response = await self._stream_code_from_llm(task)

            # Extract code blocks and documentation
            extracted = self._extract_code_blocks(llm_response)
            code_files = extracted['code_files']
            documentation = extracted['documentation']

            # Send documentation to chat panel (not saved to file)
            if documentation:
                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "dev_agent_documentation",
                    "task_id": task.id,
                    "content": documentation,
                    "message": f"Dev Agent: Documentation for '{task.title}'",
                    "timestamp": datetime.now().isoformat()
                })

            # Save each code file separately
            saved_files = []
            for filename, file_info in code_files.items():
                code_content = file_info['content']
                language = file_info['language']
                # Create meaningful filename using clean task title
                if filename == 'main_code.py' or filename == 'code.py':
                    filename = f"{safe_task_title}.py"
                code_file = task_dir / filename
                try:
                    code_file.write_text(code_content, encoding="utf-8")
                    saved_files.append(filename)
                    logger.info(f"Dev Agent: Saved code file {filename} for task {task.id}")
                    # Send file_generated event with content for immediate viewing
                    file_path_relative = str(code_file.relative_to(DEV_OUTPUT_DIR.parent))
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id,
                        "type": "file_generated",
                        "task_id": task.id,
                        "file_name": filename,
                        "file_path": file_path_relative.replace('\\', '/'),
                        "content": code_content,
                        "file_type": language,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as file_error:
                    logger.error(f"DevAgent: Failed to write code file {filename} for task {task.id}: {file_error}", exc_info=True)
                    await self.websocket_manager.broadcast_message({
                        "agent_id": self.agent_id,
                        "type": "error",
                        "task_id": task.id,
                        "message": f"Dev Agent: Failed to save {filename}: {str(file_error)}",
                        "timestamp": datetime.now().isoformat()
                    })
            if not saved_files:
                raise ValueError("No code files were generated or saved.")

            # Save task metadata
            metadata = {
                "task_id": task.id,
                "title": task.title,
                "description": task.description,
                "complexity": task.complexity,
                "estimated_hours": task.estimated_hours,
                "dependencies": task.dependencies,
                "completed_at": datetime.now().isoformat(),
                "output_files": [str(main_file.relative_to(DEV_OUTPUT_DIR))]
            }

            metadata_file = task_dir / "task_metadata.json"
            metadata_json = json.dumps(metadata, indent=2)
            metadata_file.write_text(metadata_json, encoding="utf-8")
            logger.info(f"Dev Agent: Saved metadata for task {task.id} to {metadata_file.name}")

            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "file_generated",
                "task_id": task.id,
                "file_name": str(metadata_file.relative_to(DEV_OUTPUT_DIR)),
                "content": metadata_json,
                "file_type": "json",
                "timestamp": datetime.now().isoformat()
            })

            task.status = TaskStatus.COMPLETED
            logger.info(f"Dev Agent: Task '{task.title}' (ID: {task.id}) completed successfully.")

            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_status_update",
                "task_id": task.id,
                "status": task.status.value,
                "output_directory": str(task_dir.relative_to(DEV_OUTPUT_DIR.parent)),
                "main_file": str(main_file.relative_to(DEV_OUTPUT_DIR.parent)),
                "message": f"Dev Agent completed task: '{task.title}'",
                "timestamp": datetime.now().isoformat()
            })

            return task

        except (LLMError, ValueError) as e:
            logger.error(f"DevAgent failed on task {task.id} due to LLM or content validation: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_status_update",
                "task_id": task.id,
                "status": task.status.value,
                "error": str(e),
                "message": f"Dev Agent failed task: '{task.title}': {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            return task
        except Exception as e:
            logger.error(f"DevAgent failed on task {task.id} due to an unexpected error: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_status_update",
                "task_id": task.id,
                "status": task.status.value,
                "error": str(e),
                "message": f"Dev Agent failed task: '{task.title}': {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            return task
    
    # Keep existing methods for compatibility
    def _get_latest_plan(self) -> Optional[Path]:
        """Find the most recent plan file in the parsed directory."""
        if not self.plan_dir.exists():
            return None
        plan_files = list(self.plan_dir.glob("plan_*.json"))
        if not plan_files:
            return None
        return max(plan_files, key=lambda p: p.stat().st_mtime)

    def load_current_plan(self) -> Optional[Plan]:
        """Load the most recent plan from the parsed plans directory."""
        plan_file = self._get_latest_plan()
        if not plan_file:
            logger.warning("No plan files found")
            return None
        
        try:
            with open(plan_file, 'r', encoding='utf-8') as f:
                plan_data = json.load(f)
            self.current_plan = Plan(**plan_data)
            return self.current_plan
        except Exception as e:
            logger.error(f"Failed to load plan: {e}")
            return None

    async def process_plan_tasks(self, plan: Optional[Plan] = None):
        """Process all dev_agent tasks from the given plan or the current plan."""
        if plan:
            self.current_plan = plan
        elif not self.current_plan:
            logger.error("No plan provided or loaded to process tasks")
            return False

        dev_tasks = [task for task in self.current_plan.tasks 
                     if task.agent_type == "dev_agent" and task.status == TaskStatus.PENDING]

        logger.info(f"Processing {len(dev_tasks)} development tasks")
        all_succeeded = True
        for task in dev_tasks:
            updated_task = await self.execute_task(task)
            if updated_task.status != TaskStatus.COMPLETED:
                all_succeeded = False
            
            self._save_updated_plan()

        return all_succeeded

    def _save_updated_plan(self):
        """Save the current plan with updated task statuses."""
        if self.current_plan:
            plan_file = self.plan_dir / f"plan_{self.current_plan.id}.json"
            try:
                with open(plan_file, 'w', encoding='utf-8') as f:
                    json.dump(self.current_plan.to_dict(), f, indent=2, ensure_ascii=False)
                logger.info(f"DevAgent: Updated plan saved to {plan_file.name}")
            except Exception as e:
                logger.error(f"DevAgent: Failed to save updated plan: {e}")

    async def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a specific task by its ID."""
        return self.pending_tasks.get(task_id)

    async def get_all_tasks(self) -> List[Task]:
        """Get all tasks (pending and completed)."""
        return list(self.pending_tasks.values())

    async def get_dependency_status(self, task_id: str) -> Dict[str, bool]:
        """Get the completion status of all dependencies for a task."""
        task = self.pending_tasks.get(task_id)
        if not task or not task.dependencies:
            return {}
        
        dependency_status = {}
        for dep_id in task.dependencies:
            dependency_status[dep_id] = dep_id in self.completed_tasks
        
        return dependency_status

    async def force_complete_task(self, task_id: str) -> bool:
        """Force mark a task as completed (for testing/debugging)."""
        if task_id in self.pending_tasks:
            self.completed_tasks.add(task_id)
            self.in_progress_tasks.discard(task_id)
            
            # Remove from queue if present
            self.task_queue = [t for t in self.task_queue if t.id != task_id]
            
            # Check for unblocked tasks
            await self._check_unblocked_tasks(task_id)
            
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_force_completed",
                "task_id": task_id,
                "message": f"Dev Agent: Task {task_id} force completed",
                "timestamp": datetime.now().isoformat()
            })
            
            return True
        return False

    async def reset_task_status(self, task_id: str) -> bool:
        """Reset a task's status to pending."""
        if task_id in self.completed_tasks:
            self.completed_tasks.remove(task_id)
        
        if task_id in self.in_progress_tasks:
            self.in_progress_tasks.remove(task_id)
        
        # Remove from queue if present
        self.task_queue = [t for t in self.task_queue if t.id != task_id]
        
        # Re-evaluate task readiness
        if task_id in self.pending_tasks:
            task = self.pending_tasks[task_id]
            await self._evaluate_task_readiness(task)
            
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_reset",
                "task_id": task_id,
                "message": f"Dev Agent: Task {task_id} status reset",
                "timestamp": datetime.now().isoformat()
            })
            
            return True
        return False

    async def shutdown(self):
        """Gracefully shut down the Dev Agent."""
        logger.info("Dev Agent: Shutting down...")
        
        self.is_processing_active = False
        
        # Wait for in-progress tasks to complete (with timeout)
        timeout = 30  # seconds
        start_time = datetime.now()
        
        while self.in_progress_tasks and (datetime.now() - start_time).seconds < timeout:
            await asyncio.sleep(1)
        
        if self.in_progress_tasks:
            logger.warning(f"Dev Agent: Shutdown timeout reached. {len(self.in_progress_tasks)} tasks still in progress.")
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "agent_shutdown",
            "message": "Dev Agent: Graceful shutdown complete",
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info("Dev Agent: Shutdown complete")

    def get_task_statistics(self) -> Dict[str, int]:
        """Get statistics about task processing."""
        return {
            "total_tasks": len(self.pending_tasks),
            "completed_tasks": len(self.completed_tasks),
            "in_progress_tasks": len(self.in_progress_tasks),
            "queued_tasks": len(self.task_queue),
            "waiting_tasks": len([t for t in self.waiting_for_dependencies.values() if t]),
            "failed_tasks": len([t for t in self.pending_tasks.values() if t.status == TaskStatus.FAILED])
        }

    async def get_detailed_status(self) -> Dict:
        """Get detailed status information for monitoring."""
        stats = self.get_task_statistics()
        
        return {
            "agent_id": self.agent_id,
            "plan_context": self.plan_context,
            "statistics": stats,
            "execution_status": await self.get_execution_status(),
            "task_queue": [{"id": t.id, "title": t.title} for t in self.task_queue],
            "in_progress": list(self.in_progress_tasks),
            "completed": list(self.completed_tasks),
            "dependency_graph": dict(self.dependency_graph),
            "waiting_for_dependencies": {k: list(v) for k, v in self.waiting_for_dependencies.items()},
            "timestamp": datetime.now().isoformat()
        }

    async def handle_task_update(self, task_id: str, updates: Dict):
        """Handle updates to a task from external sources."""
        if task_id not in self.pending_tasks:
            logger.warning(f"Dev Agent: Received update for unknown task {task_id}")
            return False
        
        task = self.pending_tasks[task_id]
        
        # Update task properties
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        # If dependencies changed, re-evaluate readiness
        if "dependencies" in updates:
            self.dependency_graph[task_id] = task.dependencies
            await self._evaluate_task_readiness(task)
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "task_updated",
            "task_id": task_id,
            "updates": updates,
            "message": f"Dev Agent: Task {task_id} updated",
            "timestamp": datetime.now().isoformat()
        })
        
        return True

    async def handle_priority_change(self, task_id: str, new_priority: int):
        """Handle priority changes for tasks."""
        if task_id not in self.pending_tasks:
            return False
        
        task = self.pending_tasks[task_id]
        old_priority = task.priority
        task.priority = new_priority
        
        # If task is in queue, reorder based on priority
        if task in self.task_queue:
            self.task_queue.remove(task)
            # Insert in priority order (higher priority first)
            inserted = False
            for i, queued_task in enumerate(self.task_queue):
                if task.priority > queued_task.priority:
                    self.task_queue.insert(i, task)
                    inserted = True
                    break
            if not inserted:
                self.task_queue.append(task)
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "task_priority_changed",
            "task_id": task_id,
            "old_priority": old_priority,
            "new_priority": new_priority,
            "message": f"Dev Agent: Task {task_id} priority changed from {old_priority} to {new_priority}",
            "timestamp": datetime.now().isoformat()
        })
        
        return True

    async def handle_emergency_stop(self):
        """Handle emergency stop - halt all processing immediately."""
        logger.warning("Dev Agent: Emergency stop requested")
        
        self.is_processing_active = False
        
        # Clear all queues
        self.task_queue.clear()
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "emergency_stop",
            "message": "Dev Agent: Emergency stop - all processing halted",
            "in_progress_tasks": list(self.in_progress_tasks),
            "timestamp": datetime.now().isoformat()
        })

    def __str__(self) -> str:
        """String representation of the DevAgent."""
        return f"DevAgent(plan_id={self.plan_context.get('id', 'None')}, tasks={len(self.pending_tasks)}, completed={len(self.completed_tasks)})"

    def __repr__(self) -> str:
        """Detailed string representation of the DevAgent."""
        return (f"DevAgent(agent_id='{self.agent_id}', "
                f"plan_id='{self.plan_context.get('id', 'None')}', "
                f"total_tasks={len(self.pending_tasks)}, "
                f"completed={len(self.completed_tasks)}, "
                f"in_progress={len(self.in_progress_tasks)}, "
                f"queued={len(self.task_queue)}, "
                f"active={self.is_processing_active})")

    async def handle_qa_feedback(self, task: Task, issues: List[Dict]) -> Task:
        """
        Handle feedback from QA Agent and fix the reported issues.
        This creates a feedback loop between QA and Dev agents.
        """
        logger.info(f"Dev Agent: Received QA feedback for task '{task.title}' with {len(issues)} issues")
        
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "dev_qa_feedback_received",
            "task_id": task.id,
            "message": f"🔄 Dev Agent: Received QA feedback with {len(issues)} issues to fix",
            "issues": issues,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Load the current code files
            clean_title = task.title.lower()
            prefixes_to_remove = ['define', 'create', 'implement', 'develop', 'build', 'setup', 'configure']
            for prefix in prefixes_to_remove:
                if clean_title.startswith(prefix + ' '):
                    clean_title = clean_title[len(prefix) + 1:]
                    break
            
            safe_task_title = "".join(c if c.isalnum() else "_" for c in clean_title).strip('_')
            safe_task_title = "_".join(filter(None, safe_task_title.split('_')))[:50]
            task_dir = DEV_OUTPUT_DIR / f"plan_{safe_task_title}"
            
            if not task_dir.exists():
                raise FileNotFoundError(f"Task directory not found: {task_dir}")
            
            # Group issues by file
            issues_by_file = {}
            for issue in issues:
                file_path = issue['file_path']
                if file_path not in issues_by_file:
                    issues_by_file[file_path] = []
                issues_by_file[file_path].append(issue)
            
            # Fix each file
            for filename, file_issues in issues_by_file.items():
                await self._fix_file_issues(task_dir / filename, file_issues, task)
            
            task.status = TaskStatus.COMPLETED
            
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "dev_qa_fixes_applied",
                "task_id": task.id,
                "message": f"✅ Dev Agent: Applied fixes for all QA issues in '{task.title}'",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Dev Agent: Failed to apply QA fixes for task {task.id}: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "dev_qa_fixes_failed",
                "task_id": task.id,
                "message": f"❌ Dev Agent: Failed to apply QA fixes for '{task.title}': {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        
        return task
    
    async def _fix_file_issues(self, file_path: Path, issues: List[Dict], task: Task):
        """Fix issues in a specific file."""
        if not file_path.exists():
            logger.warning(f"File not found for fixing: {file_path}")
            return
        
        original_code = file_path.read_text(encoding="utf-8")
        
        # Create a comprehensive fix prompt
        issues_description = "\n".join([
            f"- {issue['issue_type']}: {issue['description']}" + 
            (f" (Line {issue['line_number']})" if issue.get('line_number') else "")
            for issue in issues
        ])
        
        fix_prompt = f"""
You are a Senior Software Developer fixing code issues reported by QA.

Task: {task.title}
Task Description: {task.description}

File: {file_path.name}
Issues to Fix:
{issues_description}

Current Code:
```python
{original_code}
```

Requirements:
1. Fix ALL the reported issues
2. Maintain the original functionality and intent
3. Follow Python best practices and PEP 8
4. Ensure the code is production-ready
5. Add proper error handling if missing
6. Keep the code clean and readable

Return ONLY the complete fixed code, no explanations or markdown:
"""
        
        try:
            fixed_code = await ask_llm(
                user_prompt=fix_prompt,
                system_prompt="You are a software developer fixing code issues. Return only the corrected Python code without any markdown formatting or explanations.",
                model="gemini-2.5-pro",
                temperature=0.2
            )
            
            # Clean the response (remove any markdown if present)
            if "```python" in fixed_code:
                fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
            elif "```" in fixed_code:
                fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
            
            # Save the fixed code
            file_path.write_text(fixed_code, encoding="utf-8")
            
            # Notify about the fix
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "dev_file_fixed",
                "task_id": task.id,
                "filename": file_path.name,
                "issues_fixed": len(issues),
                "message": f"🔧 Dev Agent: Fixed {len(issues)} issues in {file_path.name}",
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Dev Agent: Fixed {len(issues)} issues in {file_path.name}")
            
        except Exception as e:
            logger.error(f"Dev Agent: Failed to fix issues in {file_path.name}: {e}")
            raise