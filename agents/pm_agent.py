import uuid
import json
import logging
import hashlib
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
from agents.prompt_templates import PM_SYSTEM_PROMPT
from utils.llm_setup import ask_llm, LLMError
from utils.cache_manager import load_cached_content, save_cached_content, delete_cached_content
from utils.toon_parser import TOONParser

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
        return PM_SYSTEM_PROMPT

    def _construct_prompt(self, user_input: str) -> str:
        """Constructs a clean prompt containing only the user's project requirements."""
        return f"Project Requirements:\n{user_input}"

    async def _get_raw_plan_from_llm(self, user_input: str, websocket: WebSocket):
        """Fetch the raw plan string, using cache when available."""
        system_prompt = self._get_system_prompt()
        prompt = self._construct_prompt(user_input)
        prompt_type = "plan_generation"
        plan_signature = hashlib.sha256(user_input.strip().encode("utf-8")).hexdigest()

        # Try to load from cache (defaults to .toon, falls back to .txt/.json)
        cached_plan = load_cached_content(plan_signature, prompt_type)  # Will try .toon first
        
        if cached_plan:
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "info",
                "timestamp": datetime.now().isoformat(),
                "message": "PM Agent: Using cached plan for identical requirements.",
                "cache_hit": True
            }, websocket)
            return cached_plan, plan_signature, True

        await self.websocket_manager.send_personal_message({
            "agent_id": self.agent_id,
            "type": "llm_request",
            "timestamp": datetime.now().isoformat(),
            "message": "Sending request to LLM for plan generation...",
            "llm_model": "gemini-2.5-flash"
        }, websocket)

        try:
            raw_llm_response = await ask_llm(
                user_prompt=prompt,
                system_prompt=system_prompt,
                model="gemini-2.5-flash",
                temperature=0.7,
                validate_json=False,  # Allow TOON format instead of forcing JSON
                metadata={
                    "agent": self.agent_id,
                    "prompt_name": prompt_type
                }
            )

            # ENFORCE TOON FORMAT: Reject JSON responses
            if TOONParser.is_json_format(raw_llm_response) and not TOONParser.is_toon_format(raw_llm_response):
                logger.warning("⚠️ PM Agent: LLM returned JSON instead of TOON. Re-requesting with strict TOON enforcement...")
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "info",
                    "message": "Invalid format detected. Requesting strict TOON format...",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
                # Re-request with stricter prompt
                raw_llm_response = await ask_llm(
                    user_prompt=prompt + "\n\n❌ YOUR LAST RESPONSE WAS INVALID JSON. YOU MUST OUTPUT STRICT TOON FORMAT NOW.\nStart with: PLAN<id>|title|description",
                    system_prompt=system_prompt,
                    model="gemini-2.5-flash",
                    temperature=0.4,  # Lower temperature for more deterministic output
                    validate_json=False,
                    metadata={
                        "agent": self.agent_id,
                        "prompt_name": "plan_toon_enforcement"
                    }
                )
                
                # Final check
                if not TOONParser.is_toon_format(raw_llm_response):
                    logger.error("❌ PM Agent: LLM still did not return TOON format after retry")
                    raise ValueError("LLM failed to generate TOON format after enforcement retry")

            logger.info("✅ PM Agent: TOON format validated successfully")
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "llm_response_complete",
                "timestamp": datetime.now().isoformat(),
                "message": "TOON plan received and validated.",
                "content_preview": raw_llm_response[:200] + "..." if len(raw_llm_response) > 200 else raw_llm_response
            }, websocket)

            return raw_llm_response, plan_signature, False

        except LLMError as e:
            logger.error(f"LLM Error during plan generation: {e}", exc_info=True)
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "error",
                "message": f"PM Agent: LLM call failed during plan generation: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }, websocket)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during LLM call for plan generation: {e}", exc_info=True)
            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "error",
                "message": f"PM Agent: Unexpected error during plan generation: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }, websocket)
            raise

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
            raw_llm_response, plan_signature, from_cache = await self._get_raw_plan_from_llm(user_input, websocket)
            cache_needs_update = not from_cache

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

            # Step 2: Clean and parse the plan (TOON or JSON)
            parsed_data = {}
            try:
                # Use PlanParser's unified method for parsing TOON or JSON
                parsed_data = PlanParser.clean_and_parse(raw_llm_response)
                
                # Convert to TOON if not already (for consistency)
                if not TOONParser.is_toon_format(raw_llm_response):
                    logger.info("Converting parsed plan to TOON format for storage...")
                    toon_content = TOONParser.serialize_plan_to_toon(parsed_data)
                else:
                    toon_content = raw_llm_response
                
                # Only cache TOON format if tasks array exists and is non-empty
                if cache_needs_update and isinstance(parsed_data.get("tasks"), list) and parsed_data["tasks"]:
                    save_cached_content(
                        plan_signature,
                        "plan_generation",
                        toon_content,  # Always cache TOON format
                        extension="toon",  # Use .toon extension
                        metadata={
                            "agent": self.agent_id,
                            "stored_at": datetime.now().isoformat(),
                            "validated": True,
                            "format": "TOON"
                        }
                    )
                    cache_needs_update = False
                    
                # Save TOON to parsed directory
                toon_parsed_path = self.plan_parser.parsed_plan_dir / f"plan_{plan_id}.toon"
                toon_parsed_path.write_text(toon_content, encoding='utf-8')
                logger.info(f"📦 TOON plan saved to: {toon_parsed_path.name}")
                
                logger.info(f"Plan successfully cleaned and parsed for plan_id: {plan_id}")
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "info",
                    "message": "Plan successfully parsed as TOON. Preparing tasks for streaming...",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"PM Agent: Initial plan response did not contain valid JSON ('{e}'). Retrying")
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "info",
                    "message": "Initial plan generation failed JSON validation. Retrying with a fresh request...",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
                # --- FALLBACK LOGIC ---
                try:
                    # Use the non-streaming ask_llm function for a more reliable single response
                    fallback_response = await ask_llm(
                        user_prompt=self._construct_prompt(user_input),
                        system_prompt=self._get_system_prompt(),
                        model="gemini-2.5-flash",
                        temperature=0.5,  # Use a slightly lower temp for reliability
                        validate_json=False,  # Allow TOON format instead of forcing JSON
                        metadata={
                            "agent": self.agent_id,
                            "prompt_name": "plan_fallback"
                        }
                    )
                    parsed_data = PlanParser.clean_and_parse(fallback_response)
                    # Cache fallback only if valid non-empty tasks list
                    if isinstance(parsed_data.get("tasks"), list) and parsed_data["tasks"]:
                        save_cached_content(
                            plan_signature,
                            "plan_generation",
                            fallback_response,
                            extension="txt",
                            metadata={
                                "agent": self.agent_id,
                                "stored_at": datetime.now().isoformat(),
                                "source": "fallback",
                                "validated": True,
                                "format": "TOON" if TOONParser.is_toon_format(fallback_response) else "JSON"
                            }
                        )
                        cache_needs_update = False
                    raw_llm_response = fallback_response
                    try:
                        raw_plan_file_path.write_text(raw_llm_response, encoding='utf-8')
                    except Exception as file_update_error:
                        logger.error(f"Failed to overwrite raw plan with fallback response: {file_update_error}", exc_info=True)
                    logger.info(f"PM Agent: Successfully parsed plan from fallback request for plan_id: {plan_id}")
                except (LLMError, ValueError, json.JSONDecodeError) as fallback_e:
                    logger.error(f"PM Agent: Fallback request also failed to produce a valid plan for plan_id {plan_id}: {fallback_e}", exc_info=True)
                    await self.websocket_manager.send_personal_message({
                        "agent_id": self.agent_id,
                        "type": "planning_failed",
                        "message": f"PM Agent: Critical error. Both initial and fallback requests failed to generate a valid plan: {fallback_e}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    return # Exit generator if fallback also fails

            # Check if we need a strict retry (parsed_data exists but has no tasks)
            if not (isinstance(parsed_data.get("tasks"), list) and parsed_data["tasks"]):
                # Attempt a strict one-time retry requiring non-empty tasks
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "info",
                    "message": "PM Agent: Plan missing tasks. Retrying once with strict JSON requirements...",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

                try:
                    strict_user_prompt = (
                        self._construct_prompt(user_input)
                        + "\n\nReturn ONLY a TOON formatted plan with non-empty tasks. "
                          "Format: PLAN<id>|title|description followed by TASK<id>|title|desc|priority|deps|hours|complexity|agent. "
                          "No markdown, no JSON, no commentary."
                    )

                    # Use a strict schema-only system prompt for the retry
                    strict_system_prompt = (
                        "You are a planner. Respond ONLY in TOON format.\n"
                        "Required structure:\n"
                        "PLAN<unique_id>|Plan Title|Plan description\n"
                        "TASK<001>|Task Title|Task description|priority|[deps]|hours|complexity|agent_type\n"
                        "TASK<002>|Task Title|Task description|priority|[]|hours|complexity|agent_type\n\n"
                        "Example:\n"
                        "PLAN<abc123>|Todo API|Simple REST API for todos\n"
                        "TASK<001>|Setup FastAPI|Create project structure|1|[]|2.0|simple|dev_agent\n"
                        "TASK<002>|CRUD Endpoints|Implement todo CRUD|2|[001]|4.0|medium|dev_agent\n"
                        "TASK<003>|Unit Tests|Write pytest tests|3|[002]|3.0|medium|qa_agent\n\n"
                        "Use pipe | as delimiter. No markdown, no other text."
                    )

                    strict_response = await ask_llm(
                        user_prompt=strict_user_prompt,
                        system_prompt=strict_system_prompt,
                        model="gemini-2.5-flash",
                        temperature=0.2,
                        validate_json=False,  # Allow TOON format instead of forcing JSON
                        metadata={
                            "agent": self.agent_id,
                            "prompt_name": "plan_strict_retry"
                        }
                    )
                    strict_parsed = PlanParser.clean_and_parse(strict_response)

                    if isinstance(strict_parsed.get("tasks"), list) and strict_parsed["tasks"]:
                        # Cache the valid strict plan and proceed
                        save_cached_content(
                            plan_signature,
                            "plan_generation",
                            strict_response,
                            extension="txt",
                            metadata={
                                "agent": self.agent_id,
                                "stored_at": datetime.now().isoformat(),
                                "source": "strict_retry",
                                "validated": True,
                                "format": "TOON" if TOONParser.is_toon_format(strict_response) else "JSON"
                            }
                        )
                        # Overwrite raw plan file for audit
                        try:
                            raw_plan_file_path.write_text(strict_response, encoding='utf-8')
                        except Exception:
                            pass
                        # Update parsed_data so Step 3 & 4 can process these tasks
                        parsed_data = strict_parsed
                        logger.info("PM Agent: Strict retry succeeded. Proceeding with task generation.")
                        # Don't return here - let the flow continue to Step 3 & 4 below
                    else:
                        # Purge any cached invalid plan and abort
                        delete_cached_content(plan_signature, "plan_generation")
                        await self.websocket_manager.send_personal_message({
                            "agent_id": self.agent_id,
                            "type": "planning_failed",
                            "message": "PM Agent: Invalid plan (missing tasks) after strict retry. Please refine requirements and retry.",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
                        logger.warning("PM Agent: Aborting plan generation due to missing tasks after strict retry.")
                        return

                except (LLMError, ValueError, json.JSONDecodeError) as strict_e:
                    delete_cached_content(plan_signature, "plan_generation")
                    await self.websocket_manager.send_personal_message({
                        "agent_id": self.agent_id,
                        "type": "planning_failed",
                        "message": f"PM Agent: Strict retry failed to produce a valid plan: {strict_e}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    logger.warning("PM Agent: Strict retry failed. Aborting plan.")
                    return

            # Step 3: Create the main Plan object (runs after any successful parsing path)
            plan_title = parsed_data.get('plan_title', 'Untitled Project Plan')
            plan_description = parsed_data.get('plan_description', 'No description provided.')

            self.current_plan = Plan(
                id=plan_id,
                title=plan_title,
                description=plan_description,
                tasks=[]  # Initialize empty, tasks will be added as they are yielded
            )
            self.planning_history.append(self.current_plan)

            await self.websocket_manager.send_personal_message({
                "agent_id": self.agent_id,
                "type": "planning_details",
                "plan_id": plan_id,
                "title": plan_title,
                "description": plan_description,
                "message": "Plan details extracted. Beginning task streaming...",
                "timestamp": datetime.now().isoformat()
            }, websocket)

            # Step 4: Iterate through parsed tasks and yield them one by one
            if isinstance(parsed_data.get('tasks'), list) and parsed_data['tasks']:
                for i, t_data in enumerate(parsed_data['tasks']):
                    try:
                        task = Task(
                            id=t_data.get("id", f"{plan_id}_task_{i+1:03d}"),
                            title=t_data.get("title", "Untitled Task"),
                            description=t_data.get("description", ""),
                            priority=int(t_data.get("priority", 5)),
                            status=TaskStatus.PENDING,
                            dependencies=t_data.get("dependencies", []),
                            estimated_hours=float(t_data.get("estimated_hours", 0.0)),
                            complexity=t_data.get("complexity", "medium"),
                            agent_type=t_data.get("agent_type", "dev_agent")
                        )
                        self.current_plan.tasks.append(task)

                        await self.websocket_manager.send_personal_message({
                            "agent_id": self.agent_id,
                            "type": "task_generated",
                            "task_id": task.id,
                            "title": task.title,
                            "message": f"PM Agent generated task {i+1}: '{task.title}'. Sending for execution.",
                            "timestamp": datetime.now().isoformat(),
                            "task_details": task.to_dict()
                        }, websocket)
                        yield {"type": "task_created", "task": task}

                    except Exception as task_parse_error:
                        logger.warning(f"PM Agent: Failed to parse task {i+1}: {task_parse_error}. Task data: {t_data}", exc_info=True)
                        await self.websocket_manager.send_personal_message({
                            "agent_id": self.agent_id,
                            "type": "warning",
                            "message": f"PM Agent: Failed to parse task {i+1}: {str(task_parse_error)}. Skipping.",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
            else:
                # This shouldn't happen if validation worked, but handle gracefully
                logger.error("PM Agent: No valid tasks found after all parsing attempts.")
                await self.websocket_manager.send_personal_message({
                    "agent_id": self.agent_id,
                    "type": "planning_failed",
                    "message": "PM Agent: Failed to generate any valid tasks.",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                return

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
        if self.current_plan and self.current_plan.tasks:
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