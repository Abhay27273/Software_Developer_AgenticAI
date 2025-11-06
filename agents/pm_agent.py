import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
import re
import shutil  # Added for directory cleanup
import json5  # For more lenient JSON parsing
from fastapi import WebSocket  # Import WebSocket for type hinting

from models.task import Task
from models.plan import Plan
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from parse.plan_parser import PlanParser
from config import GENERATED_CODE_ROOT  # Keep this import

# --- IMPORTANT ADDITION ---
# Import ask_llm_streaming and LLMError from your utils.llm_setup module
from utils.llm_setup import ask_llm_streaming, ask_llm, LLMError

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlannerAgent:
    def __init__(self, websocket_manager: WebSocketManager = None):
        self.agent_id = "pm_agent"
        self.websocket_manager = websocket_manager if websocket_manager is not None else WebSocketManager()
        self.current_plan = None
        self.planning_history = []

        # Use the imported GENERATED_CODE_ROOT as the base for all agent-specific directories
        self.generated_code_root = GENERATED_CODE_ROOT

        # Initialize PlanParser, passing the base output directory
        self.plan_parser = PlanParser(base_output_dir=self.generated_code_root)

        # Define and ensure existence of other agent-specific output directories
        self.dev_outputs_dir = self.generated_code_root / "dev_outputs"
        self.qa_outputs_dir = self.generated_code_root / "qa_outputs"

        try:
            self.dev_outputs_dir.mkdir(parents=True, exist_ok=True)
            self.qa_outputs_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"PM Agent initialized output directories: {self.dev_outputs_dir}, {self.qa_outputs_dir}")
        except Exception as e:
            logger.error(f"PM Agent: Failed to create necessary output directories: {e}", exc_info=True)
            # This is a critical error, but we'll allow the app to try to continue.
            # File operations will likely fail if directories aren't writable.

    def _get_system_prompt(self) -> str:
        return """You are a Senior Project Planner Agent with 15+ years of experience in software development project management. You excel at breaking down complex software requirements into comprehensive, actionable development plans.
Your Core Responsibilities:
- Analyze user requirements thoroughly to understand scope, complexity, and technical challenges
- Decompose large projects into manageable, sequential tasks following software development best practices
- Establish clear dependencies and critical path for efficient project execution
- Assign appropriate priorities, time estimates, and team roles based on industry standards
- Ensure comprehensive coverage from requirements gathering to deployment and maintenance
Task Breakdown Framework:
1. Project Analysis Phase
  - Requirements gathering and analysis
  - Technical feasibility assessment
  - Architecture planning and design decisions
  - Technology stack selection
  - Risk assessment and mitigation planning
2. Design & Architecture Phase
  - System architecture design
  - Database design and modeling
  - API design and documentation
  - UI/UX design and wireframing
  - Security architecture planning
3. Development Phase
  - Backend development (broken into logical modules)
  - Frontend development (component-based breakdown)
  - Database implementation
  - API development and integration
  - Authentication and authorization systems
  - Third-party integrations
4. Quality Assurance Phase
  - Unit testing implementation
  - Integration testing
  - System testing
  - Security testing
  - Performance testing
  - User acceptance testing
5. Deployment & Operations Phase
  - Development environment setup
  - Staging environment configuration
  - Production deployment setup
  - CI/CD pipeline implementation
  - Monitoring and logging setup
  - Documentation and training
Task Specification Requirements:
For EVERY task, provide:
- id: Unique identifier (e.g., "task_001", "task_002")
- title: Clear, actionable task name (max 80 characters)
- description: Detailed description with specific acceptance criteria
- priority: 1=low, 5=medium, 8=high, 10=critical
- dependencies: Array of task IDs that must be completed first
- estimated_hours: Realistic time estimate based on complexity
- complexity: "simple" | "medium" | "complex" | "expert"
- agent_type: "dev_agent" | "qa_agent" | "ops_agent"
Priority Guidelines:
10 (Critical): Blocking tasks, core architecture, security foundations
8 (High): Core features, main user flows, essential integrations
5 (Medium): Secondary features, optimizations, nice-to-have integrations
1 (Low): Documentation, minor enhancements, future improvements
Complexity Guidelines:
Simple: Basic CRUD operations, simple UI components, basic configurations
Medium: Complex business logic, API integrations, database relationships
Complex: Advanced algorithms, complex UI/UX, performance optimizations
Expert: Security implementations, scalability solutions, complex integrations
Agent Type Guidelines:
dev_agent: All development tasks (backend, frontend, database)
qa_agent: All testing and quality assurance tasks
ops_agent: Deployment, infrastructure, monitoring, CI/CD
Response Format:
Always respond with valid JSON in this exact structure:
```json
{
  "plan_title": "Descriptive Project Title",
  "plan_description": "Comprehensive overview of the project scope, objectives, and key deliverables",
  "tasks": [
    {
      "id": "task_001",
      "title": "Task Title",
      "description": "Detailed task description with clear acceptance criteria: - Criteria 1 - Criteria 2 - Criteria 3",
      "priority": 8,
      "dependencies": [],
      "estimated_hours": 4.5,
      "complexity": "medium",
      "agent_type": "dev_agent"
    }
  ]
}
Planning Best Practices:
Start with foundation tasks (architecture, database design, core setup)
Build incrementally - ensure each task builds logically on previous ones
Consider parallel execution - minimize blocking dependencies where possible
Include comprehensive testing - don't just focus on development
Plan for deployment - include infrastructure and operations tasks
Document everything - include documentation tasks throughout
Think about scalability - consider future growth and maintenance
Security first - integrate security considerations from the start
Now, analyze the user's requirements and create a comprehensive development plan. Consider:
Project scale and complexity
Technology requirements
Team structure and skills
Timeline constraints
Risk factors
Deployment requirements
Maintenance and support needs
Provide a detailed, actionable plan that a development team can follow from start to finish.
"""

    def _construct_prompt(self, user_input: str) -> str:
        """Constructs a clean prompt containing only the user's project requirements."""
        return f"Project Requirements:\n{user_input}"

    async def _get_raw_plan_from_llm(self, user_input: str, websocket: WebSocket):
        """
        Calls the LLM to generate the raw plan, streams its output,
        and returns the complete response.
        """
        system_prompt = self._get_system_prompt()
        prompt = self._construct_prompt(user_input)

        await self.websocket_manager.send_personal_message({
            "agent_id": self.agent_id,
            "type": "llm_request",
            "timestamp": datetime.now().isoformat(),
            "message": "Sending request to LLM for plan generation...",
            "llm_model": "gemini-2.5-flash"  # Indicate which model is being used
        }, websocket)

        full_response_content = []
        try:
            # Use the streaming-specific method without await
            async for chunk in ask_llm_streaming(  # <-- This is where ask_llm_streaming is called
                user_prompt=prompt,
                system_prompt=system_prompt,
                model="gemini-2.5-flash",  # Using 'pro' for planning as it's typically more robust for structured output
                temperature=0.7  # A bit lower temperature for more consistent JSON
            ):
                # Stream each chunk back to the client
                await self.websocket_manager.stream_chunk(chunk, websocket)
                full_response_content.append(chunk)

            raw_llm_response = "".join(full_response_content)
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "llm_response_complete",
                "timestamp": datetime.now().isoformat(),
                "message": "LLM response stream completed for plan.",
                "content_preview": raw_llm_response[:200] + "..." if len(raw_llm_response) > 200 else raw_llm_response
            }, websocket)

            return raw_llm_response

        except LLMError as e:  # Catch specific LLMError
            logger.error(f"LLM Error during plan generation: {e}", exc_info=True)
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "error",
                "message": f"PM Agent: LLM call failed during plan generation: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }, websocket)
            raise  # Re-raise to be caught by the caller for pipeline failure
        except Exception as e:  # Catch any other unexpected errors
            logger.error(f"Unexpected error during LLM call for plan generation: {e}", exc_info=True)
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "error",
                "message": f"PM Agent: Unexpected error during plan generation: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }, websocket)
            raise  # Re-raise to be caught by the caller for pipeline failure

    def _cleanup_all_outputs(self):
        """
        Deletes all files in raw plans, parsed plans, dev_outputs, and qa_outputs directories.
        Ensures operation within the generated_code_root for safety.
        This method automatically cleans up previous plans when a new user request comes in.
        """
        dirs_to_clean = [
            self.generated_code_root / "dev_outputs",
            self.generated_code_root / "plans" / "raw",
            self.generated_code_root / "plans" / "parsed",
            self.generated_code_root / "qa_outputs"
        ]

        logger.info("🧹 PM Agent: Starting automatic cleanup of previous plans and outputs...")
        
        # Count files before cleanup for better logging
        total_files_removed = 0
        for d in dirs_to_clean:
            if d.exists():
                try:
                    files_in_dir = list(d.iterdir())
                    files_count = len(files_in_dir)
                    
                    if files_count > 0:
                        logger.info(f"🗑️  Removing {files_count} items from: {d.name}")
                        
                        # Remove content, but keep the directory itself
                        for item in files_in_dir:
                            if item.is_file():
                                item.unlink()
                                total_files_removed += 1
                            elif item.is_dir():
                                shutil.rmtree(item)
                                total_files_removed += 1
                        
                        logger.info(f"✅ Cleaned contents of: {d.name}")
                    else:
                        logger.info(f"📁 Directory already empty: {d.name}")
                        
                except Exception as e:
                    logger.warning(f"❌ Failed to clean contents of {d}: {e}")
            else:
                logger.info(f"📁 Directory doesn't exist yet: {d.name}")
                
            # Ensure the directory exists after cleaning (or if it didn't exist initially)
            d.mkdir(parents=True, exist_ok=True)
            
        if total_files_removed > 0:
            logger.info(f"🎯 PM Agent: Successfully removed {total_files_removed} previous files/directories")
        else:
            logger.info("🎯 PM Agent: No previous files to clean up")
            
        logger.info("✨ PM Agent: Automatic cleanup completed - ready for new user request")

    async def create_plan_and_stream_tasks(self, user_input: str, websocket: WebSocket):
        """
        Generates a comprehensive plan from user input, streams LLM output,
        parses the plan, stores it, and then yields individual tasks as they are parsed.
        This method acts as an async generator.
        
        AUTOMATIC CLEANUP: This method automatically deletes all previous plans and outputs
        when a new user request comes in, ensuring only the current request's data is kept.
        """
        # 🧹 AUTOMATIC CLEANUP: Remove all previous plans and outputs before starting new plan
        self._cleanup_all_outputs()

        plan_id = str(uuid.uuid4())  # Generate a unique ID for this planning session

        # Notify the start of the planning process to the specific client
        await self.websocket_manager.send_personal_message({
            "agent_id": self.agent_id,
            "type": "planning_start",
            "timestamp": datetime.now().isoformat(),
            "plan_id": plan_id,
            "message": "PM Agent initiated planning process. LLM is generating the plan..."
        }, websocket)

        # Use paths from self.plan_parser for consistency
        raw_plan_file_path = self.plan_parser.raw_plan_dir / f"plan_{plan_id}_raw.txt"
        parsed_plan_file_path_placeholder = self.plan_parser.parsed_plan_dir / f"plan_{plan_id}.json"  # Placeholder name

        try:
            # Step 1: Get the raw plan (full JSON string) from the LLM, with streaming to client
            raw_llm_response = await self._get_raw_plan_from_llm(user_input, websocket)

            # Save raw response for auditing/debugging
            try:
                raw_plan_file_path.write_text(raw_llm_response, encoding='utf-8')
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "info",
                    "message": f"Raw plan response saved to {raw_plan_file_path.name}",
                    # Ensure relative path for frontend display
                    "file_path": str(raw_plan_file_path.relative_to(self.generated_code_root)).replace("\\", "/"),
                    "timestamp": datetime.now().isoformat()
                }, websocket)
            except Exception as e:
                logger.error(f"Failed to save raw plan file {raw_plan_file_path.name}: {e}", exc_info=True)
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "error",
                    "message": f"PM Agent: Failed to save raw plan: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                # This is not a critical failure that should stop the pipeline, just log and proceed.

            # Step 2: Clean and parse the full JSON plan
            parsed_data = {}
            try:
                # Use PlanParser's static method for cleaning and validation
                cleaned_json_str = PlanParser.clean_json_string(raw_llm_response)
                parsed_data = json5.loads(cleaned_json_str)  # Use json5 for robust parsing
                logger.info(f"Plan JSON successfully cleaned and parsed for plan_id: {plan_id}")
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "info",
                    "message": "Plan JSON successfully parsed. Preparing tasks for streaming...",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"PM Agent: Streaming response did not contain valid JSON ('{e}'). Falling back to a non-streaming request.")
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "info",
                    "message": "Streaming failed to produce a valid plan. Retrying with a more robust request...",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
                # --- FALLBACK LOGIC ---
                try:
                    # Use the non-streaming ask_llm function for a more reliable single response
                    fallback_response = await ask_llm(
                        user_prompt=self._construct_prompt(user_input),
                        system_prompt=self._get_system_prompt(),
                        model="gemini-2.5-flash",
                        temperature=0.5, # Use a slightly lower temp for reliability
                        validate_json=True
                    )
                    cleaned_json_str = PlanParser.clean_json_string(fallback_response)
                    parsed_data = json5.loads(cleaned_json_str)
                    logger.info(f"PM Agent: Successfully parsed plan from fallback request for plan_id: {plan_id}")
                except (LLMError, ValueError, json.JSONDecodeError) as fallback_e:
                    logger.error(f"PM Agent: Fallback request also failed to produce a valid plan for plan_id {plan_id}: {fallback_e}", exc_info=True)
                    await self.websocket_manager.send_personal_message({
                        "agent_id": self.agent_id,
                        "type": "planning_failed",
                        "message": f"PM Agent: Critical error. Both streaming and fallback requests failed to generate a valid plan: {fallback_e}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    return # Exit generator if fallback also fails

            # Step 3: Create the main Plan object and store it
            plan_title = parsed_data.get('plan_title', 'Untitled Project Plan')
            plan_description = parsed_data.get('plan_description', 'No description provided.')

            self.current_plan = Plan(
                id=plan_id,
                title=plan_title,
                description=plan_description,
                tasks=[]  # Initialize empty, tasks will be added as they are yielded
            )
            self.planning_history.append(self.current_plan)  # Add to history

            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "planning_details",
                "plan_id": plan_id,
                "title": plan_title,
                "description": plan_description,
                "message": "Plan details extracted. Beginning task streaming to Dev Agent...",
                "timestamp": datetime.now().isoformat()
            }, websocket)

            # Step 4: Iterate through parsed tasks and yield them one by one
            if 'tasks' in parsed_data and isinstance(parsed_data['tasks'], list):
                for i, t_data in enumerate(parsed_data['tasks']):
                    try:
                        task = Task(
                            id=t_data.get("id", f"{plan_id}_task_{i+1:03d}"),  # Ensure unique and linked ID
                            title=t_data.get("title", "Untitled Task"),
                            description=t_data.get("description", ""),
                            priority=int(t_data.get("priority", 5)),
                            status=TaskStatus.PENDING,  # Initial status
                            dependencies=t_data.get("dependencies", []),
                            estimated_hours=float(t_data.get("estimated_hours", 0.0)),
                            complexity=t_data.get("complexity", "medium"),
                            agent_type=t_data.get("agent_type", "dev_agent")
                        )
                        self.current_plan.tasks.append(task)  # Add to the main plan object in memory

                        await self.websocket_manager.send_personal_message({
                            "agent_id": self.agent_id,
                            "type": "task_generated",  # This indicates a task has been successfully parsed and is ready
                            "task_id": task.id,
                            "title": task.title,
                            "message": f"PM Agent generated task {i+1}: '{task.title}'. Sending for execution.",
                            "timestamp": datetime.now().isoformat(),
                            "task_details": task.to_dict()  # Include task details for frontend display
                        }, websocket)
                        yield {"type": "task_created", "task": task}  # Yield a dictionary with the task object

                    except Exception as task_parse_error:
                        logger.warning(f"PM Agent: Failed to parse individual task {i+1} from LLM response: {task_parse_error}. Task data: {t_data}", exc_info=True)
                        await self.websocket_manager.send_personal_message({
                            "agent_id": self.agent_id,
                            "type": "warning",
                            "message": f"PM Agent: Failed to parse task {i+1}: {str(task_parse_error)}. Skipping this task.",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
                        # Continue to next task even if one fails to parse
            else:
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "warning",
                    "message": "PM Agent: Plan generated by LLM contains no 'tasks' array or it's malformed.",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                logger.warning("PM Agent: No 'tasks' array found in the parsed plan or it's malformed.")

        except Exception as e:
            logger.error(f"PM Agent: Critical error during plan generation or task streaming: {e}", exc_info=True)
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "planning_failed",
                "message": f"PM Agent: Critical failure during plan generation: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }, websocket)
            # Do not yield any tasks if a critical error occurs
            return  # Exit the generator

        # Step 5: Save the full structured plan after all tasks have been yielded
        if self.current_plan:
            final_parsed_plan_file_path = self.plan_parser.parsed_plan_dir / f"plan_{self.current_plan.id}.json"
            try:
                # The parent directory for parsed plans should already be created by PlanParser's __init__
                logger.info(f"Attempting to save final parsed plan to: {final_parsed_plan_file_path}")
                parsed_json = json.dumps(self.current_plan.to_dict(), indent=2, ensure_ascii=False)
                final_parsed_plan_file_path.write_text(parsed_json, encoding='utf-8')
                logger.info(f"Successfully saved final parsed plan to: {final_parsed_plan_file_path}")
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "planning_complete",
                    "plan_id": self.current_plan.id,
                    "tasks_count": len(self.current_plan.tasks),
                    "message": f"PM Agent: All tasks generated and full plan saved to {final_parsed_plan_file_path.name}",
                    # Ensure relative path for frontend display
                    "file_path": str(final_parsed_plan_file_path.relative_to(self.generated_code_root)).replace("\\", "/"),
                    "timestamp": datetime.now().isoformat()
                }, websocket)
            except Exception as e:
                logger.error(f"PM Agent: Failed to save final structured plan at {final_parsed_plan_file_path}: {e}", exc_info=True)
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "error",
                    "message": f"PM Agent: Failed to save final plan: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }, websocket)