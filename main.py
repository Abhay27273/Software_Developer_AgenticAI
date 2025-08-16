import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from models.task import Task
from models.plan import Plan
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from agents.pm_agent import PlannerAgent
from agents.dev_agent import DevAgent
from agents.qa_agent import QAAgent
from agents.ops_agent import OpsAgent # NEW: Import the OpsAgent
import asyncio
from pathlib import Path
from datetime import datetime
import json
import os
import logging
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Configure templates and static files
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Ensure static directory exists
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)


# Mount static files (e.g., for frontend JS/CSS)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
)

# --- Define base directory for generated files for security checks ---
GENERATED_CODE_ROOT = BASE_DIR / "generated_code"


# Global managers
websocket_manager = WebSocketManager()

# Initialize agents - Pass the websocket_manager to agents
planner_agent = PlannerAgent(websocket_manager=websocket_manager)
dev_agent = DevAgent(websocket_manager=websocket_manager)
qa_agent = QAAgent(websocket_manager=websocket_manager)
ops_agent = OpsAgent(websocket_manager=websocket_manager, generated_code_root=GENERATED_CODE_ROOT) # NEW: Initialize the OpsAgent


@app.get("/", response_class=HTMLResponse)
async def get_ui(request: Request):
    """Serves the main HTML page for the UI."""
    return templates.TemplateResponse("index.html", {"request": request})

# --- FILE TREE ENDPOINTS AND MONITORING ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes the file monitor when the application starts (lifespan event)."""
    loop = asyncio.get_running_loop()
    event_handler = FileChangeHandler(loop=loop, manager=websocket_manager)
    observer = Observer()
    
    # Ensure the root directory for monitoring exists before scheduling
    GENERATED_CODE_ROOT.mkdir(parents=True, exist_ok=True)
    observer.schedule(event_handler, str(GENERATED_CODE_ROOT), recursive=True)

    # Run the observer in a separate thread so it doesn't block the main app
    monitor_thread = threading.Thread(target=observer.start, daemon=True)
    monitor_thread.start()
    logger.info(f"👀 Started file system monitor in '{GENERATED_CODE_ROOT}'")
    try:
        yield
    finally:
        observer.stop()
        observer.join()

# Attach the lifespan handler to the app
app.router.lifespan_context = lifespan

@app.get("/api/files")
async def list_generated_files():
    """
    Scans the generated_code directory recursively and returns a JSON
    representing the file tree structure.
    """
    # Ensure the directory exists before attempting to scan it
    if not GENERATED_CODE_ROOT.is_dir():
        logger.warning(f"GENERATED_CODE_ROOT '{GENERATED_CODE_ROOT}' does not exist or is not a directory.")
        return [] # Return empty list if directory doesn't exist yet

    def _scan_dir(path: Path):
        items = []
        # Sort items to show directories first, then files alphabetically
        sorted_paths = sorted(list(path.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
        for item in sorted_paths:
            node = {"name": item.name, "path": str(item.relative_to(GENERATED_CODE_ROOT))}
            if item.is_dir():
                node["type"] = "directory"
                node["children"] = _scan_dir(item)
            else:
                node["type"] = "file"
            items.append(node)
        return items

    return _scan_dir(GENERATED_CODE_ROOT)


@app.get("/api/file-content", response_class=PlainTextResponse)
async def get_file_content(path: str):
    file_path = BASE_DIR / path
    try:
        # Try reading as UTF-8 text
        content = file_path.read_text(encoding="utf-8")
        return content
    except UnicodeDecodeError:
        # If not decodable, return a message or empty string
        logger.error(f"Could not decode file as UTF-8: {file_path}")
        return "[Error] File is not a UTF-8 text file or is binary."
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"[Error] Could not read file: {e}"

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles WebSocket connections, processes incoming messages,
    and orchestrates the entire agent pipeline in a streaming fashion.
    """
    await websocket.accept()
    try:
        await websocket_manager.connect(websocket)
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start_planning":
                requirements = data.get("requirements", "")
                
                if not requirements:
                    await websocket_manager.send_personal_message({
                        "type": "error",
                        "message": "Requirements are missing for planning.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                # Notify frontend that planning has started (via broadcast for all connected clients)
                await websocket_manager.broadcast_message({
                    "type": "planning_started",
                    "message": "Planning initiated. PM Agent is creating and streaming tasks...",
                    "timestamp": datetime.now().isoformat()
                })
                
                processed_tasks_count = 0
                
                try:
                    # PM Agent creates plan and streams task descriptions
                    async for task_message in planner_agent.create_plan_and_stream_tasks(requirements, websocket):
                        if task_message["type"] == "task_created":
                            task: Task = task_message["task"] # The actual Task object
                            
                            await websocket_manager.send_personal_message({
                                "type": "agent_output", # General message for task processing
                                "agent_type": "pm",
                                "content": f"PM Agent: Created task: '{task.title}' (Agent: {task.agent_type})...\n",
                                "task_id": task.id,
                                "timestamp": datetime.now().isoformat()
                            }, websocket) # Send to the specific client that initiated

                            if task.agent_type == "dev_agent":
                                # --- Dev Agent Execution with Streaming ---
                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "task_id": task.id,
                                    "status": TaskStatus.IN_PROGRESS.value,
                                    "message": f"Dev Agent executing task: '{task.title}'",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)

                                # Pass the WebSocket object to the DevAgent's execute_task
                                updated_task = await dev_agent.execute_task(task) 

                                # --- REMOVED: Redundant file saving logic. ---
                                # The DevAgent is now solely responsible for saving its own output files.

                                # Once DevAgent is done, update the plan and notify
                                if planner_agent.current_plan:
                                    for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                                        if p_task.id == updated_task.id:
                                            planner_agent.current_plan.tasks[idx] = updated_task
                                            break
                                _save_plan(planner_agent.current_plan) # Save updated plan with task status
                                
                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "task_id": updated_task.id,
                                    "status": updated_task.status.value,
                                    "message": f"Dev Agent task '{updated_task.title}' {updated_task.status.value.lower()}.",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)

                                if updated_task.status == TaskStatus.COMPLETED:
                                    await websocket_manager.send_personal_message({
                                        "type": "dev_task_complete_init_qa",
                                        "task_id": updated_task.id,
                                        "title": updated_task.title,
                                        "message": f"Development for '{updated_task.title}' completed. Initiating QA for this task...",
                                        "timestamp": datetime.now().isoformat()
                                    }, websocket)
                                    
                                    qa_task_result = await qa_agent.execute_task(updated_task)
                                    
                                    if planner_agent.current_plan:
                                        for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                                            if p_task.id == updated_task.id: # Use updated_task ID as reference
                                                planner_agent.current_plan.tasks[idx] = qa_task_result
                                                break
                                    _save_plan(planner_agent.current_plan) # Save updated plan with QA result

                                    if qa_task_result.status == TaskStatus.COMPLETED:
                                        # NEW: Trigger Ops Agent after successful QA
                                        await websocket_manager.send_personal_message({
                                            "type": "qa_task_complete_init_ops",
                                            "task_id": qa_task_result.id,
                                            "title": qa_task_result.title,
                                            "message": f"QA for '{qa_task_result.title}' completed. Initiating Ops for deployment...",
                                            "timestamp": datetime.now().isoformat()
                                        }, websocket)
                                        
                                        ops_task_result = await ops_agent.execute_task(qa_task_result)
                                        if planner_agent.current_plan:
                                            for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                                                if p_task.id == qa_task_result.id:
                                                    planner_agent.current_plan.tasks[idx] = ops_task_result
                                                    break
                                        _save_plan(planner_agent.current_plan)

                                    else: # QA task failed
                                        await websocket_manager.send_personal_message({
                                            "type": "qa_task_failed",
                                            "task_id": qa_task_result.id,
                                            "title": qa_task_result.title,
                                            "message": f"QA for '{qa_task_result.title}' failed. Skipping Ops.",
                                            "timestamp": datetime.now().isoformat()
                                        }, websocket)

                                else: # Dev task failed or skipped
                                    await websocket_manager.send_personal_message({
                                        "type": "dev_task_failed",
                                        "task_id": updated_task.id,
                                        "title": updated_task.title,
                                        "message": f"Development for '{updated_task.title}' failed. Skipping QA and Ops.",
                                        "timestamp": datetime.now().isoformat()
                                    }, websocket)

                            elif task.agent_type == "qa_agent":
                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "task_id": task.id,
                                    "status": TaskStatus.IN_PROGRESS.value,
                                    "message": f"QA Agent executing task: '{task.title}'",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                updated_task = await qa_agent.execute_task(task)
                                if planner_agent.current_plan:
                                    for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                                        if p_task.id == updated_task.id:
                                            planner_agent.current_plan.tasks[idx] = updated_task
                                            break
                                _save_plan(planner_agent.current_plan)

                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "task_id": updated_task.id,
                                    "status": updated_task.status.value,
                                    "message": f"QA Agent task '{updated_task.title}' {updated_task.status.value.lower()}.",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)

                            elif task.agent_type == "ops_agent": # NEW: Handle ops agent tasks
                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "task_id": task.id,
                                    "status": TaskStatus.IN_PROGRESS.value,
                                    "message": f"Ops Agent executing task: '{task.title}'",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                updated_task = await ops_agent.execute_task(task)
                                if planner_agent.current_plan:
                                    for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                                        if p_task.id == updated_task.id:
                                            planner_agent.current_plan.tasks[idx] = updated_task
                                            break
                                _save_plan(planner_agent.current_plan)
                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "task_id": updated_task.id,
                                    "status": updated_task.status.value,
                                    "message": f"Ops Agent task '{updated_task.title}' {updated_task.status.value.lower()}.",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)


                            else: # Unhandled agent type
                                await websocket_manager.send_personal_message({
                                    "type": "task_skipped",
                                    "task_id": task.id,
                                    "title": task.title,
                                    "message": f"Task '{task.title}' with unsupported agent type '{task.agent_type}' skipped.",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                if planner_agent.current_plan:
                                    for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                                        if p_task.id == task.id:
                                            p_task.status = TaskStatus.SKIPPED
                                            break
                                _save_plan(planner_agent.current_plan)

                except Exception as e:
                    logger.error(f"Error during planning/task execution pipeline: {e}", exc_info=True)
                    await websocket_manager.send_personal_message({ # Send error to the specific client
                        "type": "pipeline_failed",
                        "message": f"An error occurred during task streaming/execution: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    # No continue, let the finally block handle disconnection

                # After all tasks are processed or an error occurred during processing
                if planner_agent.current_plan:
                    total_tasks_processed = len(planner_agent.current_plan.tasks) if planner_agent.current_plan.tasks else 0
                    await websocket_manager.send_personal_message({
                        "type": "planning_completed",
                        "message": f"All {total_tasks_processed} tasks for plan '{planner_agent.current_plan.title}' processed.",
                        "plan": planner_agent.current_plan.to_dict(),
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                else:
                    await websocket_manager.send_personal_message({
                        "type": "error",
                        "message": "Planning and task execution attempt completed. No full plan available or an error occurred.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)

            # --- Handle file content requests via WebSocket ---
            elif msg_type == "request_file_content":
                file_path_str = data.get("file_path")

                # Handle the special 'welcome' path for initial content
                if file_path_str == "welcome":
                    await websocket_manager.send_personal_message({
                        "type": "file_content_response",
                        "file_path": "welcome",
                        "content": "Welcome to AI Planning Agent\n\nYour generated code files will appear here.\nClick on files in the left panel to view their contents.",
                        "error": None,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                if not file_path_str:
                    await websocket_manager.send_personal_message({
                        "type": "file_content_response",
                        "file_path": None,
                        "content": None,
                        "error": "File path not provided.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                # --- SECURITY CHECK: Prevent Path Traversal ---
                try:
                    # Create an absolute path and ensure it's within our secure root directory.
                    file_path = GENERATED_CODE_ROOT.joinpath(file_path_str).resolve()

                    if not file_path.is_relative_to(GENERATED_CODE_ROOT.resolve()):
                        raise HTTPException(status_code=403, detail="Access denied: Path is outside the allowed directory.")

                    if ".git" in file_path.parts:
                        return "[Error] Cannot view files inside .git directory."

                    if file_path.is_file():
                        content = file_path.read_text(encoding="utf-8")
                        await websocket_manager.send_personal_message({
                            "type": "file_content_response",
                            "file_path": file_path_str,
                            "content": content,
                            "error": None,
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
                    else:
                        await websocket_manager.send_personal_message({
                            "type": "file_content_response",
                            "file_path": file_path_str,
                            "content": None,
                            "error": "File not found or is a directory.",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)

                except Exception as e:
                    logger.error(f"Error reading file {file_path_str}: {e}", exc_info=True)
                    await websocket_manager.send_personal_message({
                        "type": "file_content_response",
                        "file_path": file_path_str,
                        "content": None,
                        "error": f"Error reading file: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
            
            else:
                logger.warning(f"Unknown message type received: {msg_type}")
                await websocket_manager.send_personal_message({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "received_data": data,
                    "timestamp": datetime.now().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket: {websocket.client.host}:{websocket.client.port}")
    except Exception as e:
        logger.exception(f"An unhandled error occurred in WebSocket for client {websocket.client.host}:{websocket.client.port}:")
    finally:
        websocket_manager.disconnect(websocket)


# Helper function to save the plan
def _save_plan(plan: Plan):
    """Saves the current state of the plan to a JSON file."""
    if plan:
        PLANS_DIR = GENERATED_CODE_ROOT / "plans" / "parsed"
        PLANS_DIR.mkdir(parents=True, exist_ok=True) # Ensure dir exists
        plan_file = PLANS_DIR / f"plan_{plan.id}.json"
        try:
            with open(plan_file, 'w', encoding='utf-8') as f:
                json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Plan {plan.id} saved to {plan_file.name}")
        except Exception as e:
            logger.error(f"Failed to save plan {plan.id} to file: {e}", exc_info=True)

# Keep the /start POST endpoint as a separate, alternative way to trigger
@app.post("/start")
async def start_pipeline_post(request: Request):
    """
    Alternative REST endpoint to trigger the entire agent pipeline.
    This version processes tasks in a batch after the full plan is received.
    """
    data = await request.json()
    requirements = data.get("requirements", "")
    if not requirements:
        return {"error": "Requirements missing"}

    # Use broadcast for general info in batch mode as no single WS connection might be active
    await websocket_manager.broadcast_message({ 
        "type": "info",
        "message": "POST /start initiated. Processing plan in batch mode...",
        "timestamp": datetime.now().isoformat()
    })

    # For POST endpoint, we don't stream task creation.
    # The planner_agent.create_plan_and_stream_tasks will still generate tasks,
    # but we'll consume the generator without sending individual task_created messages here.
    async for _ in planner_agent.create_plan_and_stream_tasks(requirements, websocket=None):
        pass 

    current_plan = planner_agent.current_plan
    if not current_plan or not current_plan.tasks:
        return {"error": "Failed to create plan or no tasks generated.", 
                "plan_id": current_plan.id if current_plan else "N/A"}

    all_dev_success = True
    all_qa_success = True
    all_ops_success = True

    for task in current_plan.tasks:
        if task.agent_type == "dev_agent":
            await websocket_manager.broadcast_message({
                "type": "info",
                "message": f"POST Mode: Executing Dev task '{task.title}' ({task.id})",
                "timestamp": datetime.now().isoformat()
            })
            # Pass None for websocket as streaming not expected in POST mode
            updated_task = await dev_agent.execute_task(task) 
            if updated_task.status != TaskStatus.COMPLETED:
                all_dev_success = False
            for idx, p_task in enumerate(current_plan.tasks):
                if p_task.id == updated_task.id:
                    current_plan.tasks[idx] = updated_task
                    break
            _save_plan(current_plan)

            if updated_task.status == TaskStatus.COMPLETED:
                await websocket_manager.broadcast_message({
                    "type": "info",
                    "message": f"POST Mode: Executing QA for task '{updated_task.title}' ({updated_task.id})",
                    "timestamp": datetime.now().isoformat()
                })
                # Pass None for websocket as streaming not expected in POST mode
                qa_task_result = await qa_agent.execute_task(updated_task) 
                if qa_task_result.status != TaskStatus.COMPLETED:
                    all_qa_success = False
                for idx, p_task in enumerate(current_plan.tasks):
                    if p_task.id == qa_task_result.id:
                        current_plan.tasks[idx] = qa_task_result
                        break
                _save_plan(current_plan)

                if qa_task_result.status == TaskStatus.COMPLETED:
                    await websocket_manager.broadcast_message({
                        "type": "info",
                        "message": f"POST Mode: Executing Ops for task '{qa_task_result.title}' ({qa_task_result.id})",
                        "timestamp": datetime.now().isoformat()
                    })
                    ops_task_result = await ops_agent.execute_task(qa_task_result)
                    if ops_task_result.status != TaskStatus.COMPLETED:
                        all_ops_success = False
                    for idx, p_task in enumerate(current_plan.tasks):
                        if p_task.id == ops_task_result.id:
                            current_plan.tasks[idx] = ops_task_result
                            break
                    _save_plan(current_plan)


        elif task.agent_type == "qa_agent":
            await websocket_manager.broadcast_message({
                "type": "info",
                "message": f"POST Mode: Executing standalone QA task '{task.title}' ({task.id})",
                "timestamp": datetime.now().isoformat()
            })
            # Pass None for websocket as streaming not expected in POST mode
            updated_task = await qa_agent.execute_task(task) 
            if updated_task.status != TaskStatus.COMPLETED:
                all_qa_success = False
            for idx, p_task in enumerate(current_plan.tasks):
                if p_task.id == updated_task.id:
                    current_plan.tasks[idx] = updated_task
                    break
            _save_plan(current_plan)
        
        elif task.agent_type == "ops_agent":
             await websocket_manager.broadcast_message({
                "type": "info",
                "message": f"POST Mode: Executing standalone Ops task '{task.title}' ({task.id})",
                "timestamp": datetime.now().isoformat()
            })
             updated_task = await ops_agent.execute_task(task)
             if updated_task.status != TaskStatus.COMPLETED:
                all_ops_success = False
             for idx, p_task in enumerate(current_plan.tasks):
                if p_task.id == updated_task.id:
                    current_plan.tasks[idx] = updated_task
                    break
             _save_plan(current_plan)

        else:
            await websocket_manager.broadcast_message({
                "type": "info",
                "message": f"POST Mode: Skipping task '{task.title}' ({task.id}) with unsupported agent type '{task.agent_type}'.",
                "timestamp": datetime.now().isoformat()
            })
            for idx, p_task in enumerate(current_plan.tasks):
                if p_task.id == task.id:
                    p_task.status = TaskStatus.SKIPPED
                    break
            _save_plan(current_plan)

    return {
        "plan_id": current_plan.id,
        "status": "Pipeline execution complete (batch mode)",
        "dev_success": all_dev_success,
        "qa_success": all_qa_success,
        "ops_success": all_ops_success,
        "final_plan_status": current_plan.to_dict()
    }

# --- File monitoring and notifications ---

class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events and notifies clients via WebSocket."""
    def __init__(self, loop, manager: WebSocketManager):
        self.loop = loop
        self.manager = manager

    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory:
            try:
                # Make path relative to the generated code root for the client
                relative_path = os.path.relpath(event.src_path, str(GENERATED_CODE_ROOT))
                logger.info(f"✅ New file detected: {relative_path}")

                message = {
                    "type": "file_generated",
                    "file_path": relative_path,
                    "file_name": os.path.basename(event.src_path),
                    "timestamp": datetime.now().isoformat()
                }

                # Schedule the async broadcast message on the main event loop
                asyncio.run_coroutine_threadsafe(
                    self.manager.broadcast_message(message), self.loop
                )
            except Exception as e:
                logger.error(f"Error in FileChangeHandler: {e}", exc_info=True)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7860,
        reload=False,
        reload_excludes=[
            str(GENERATED_CODE_ROOT),
        ],
    )
