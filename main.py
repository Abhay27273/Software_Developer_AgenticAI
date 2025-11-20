import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
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

# Import API routers for production enhancement features
from api.routes import (
    project_router,
    modification_router,
    template_router,
    documentation_router
)

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

# Include API routers for production enhancement features
app.include_router(project_router)
app.include_router(modification_router)
app.include_router(template_router)
app.include_router(documentation_router)

# --- Define base directory for generated files for security checks ---
GENERATED_CODE_ROOT = BASE_DIR / "generated_code"


# Global managers
websocket_manager = WebSocketManager()

# Configure WebSocket manager for API routes (Task 9.1)
from api.routes import set_websocket_manager
set_websocket_manager(websocket_manager)

# Initialize Project Manager
from utils.project_manager import ProjectManager
import config
project_manager = ProjectManager(config.PROJECTS_ROOT)

# Initialize agents - Pass the websocket_manager to agents
planner_agent = PlannerAgent(websocket_manager=websocket_manager)
dev_agent = DevAgent(websocket_manager=websocket_manager)
qa_agent = QAAgent(websocket_manager=websocket_manager)
ops_agent = OpsAgent(websocket_manager=websocket_manager, generated_code_root=GENERATED_CODE_ROOT) # NEW: Initialize the OpsAgent

# Track current project
current_project_name = None


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


# --- PROJECT MANAGEMENT ENDPOINTS ---

@app.get("/api/project/tree")
async def get_project_tree():
    """Get hierarchical project tree with current and archived projects."""
    try:
        tree = project_manager.get_project_tree()
        return JSONResponse(content=tree)
    except Exception as e:
        logger.error(f"Error getting project tree: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/project/current")
async def get_current_project():
    """Get metadata for the current project."""
    try:
        metadata = project_manager.metadata.get("current")
        if not metadata:
            return JSONResponse(content={"message": "No active project"}, status_code=404)
        return JSONResponse(content=metadata)
    except Exception as e:
        logger.error(f"Error getting current project: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/project/archived")
async def get_archived_projects():
    """Get list of all archived projects."""
    try:
        archived = project_manager.get_archived_projects()
        return JSONResponse(content={"archived": archived})
    except Exception as e:
        logger.error(f"Error getting archived projects: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/project/new")
async def create_new_project(request: Request):
    """Create a new project and archive the current one."""
    try:
        data = await request.json()
        user_request = data.get("request", "new_project")
        
        project_info = project_manager.create_new_project(user_request)
        
        # Broadcast to all connected clients
        await websocket_manager.broadcast_message({
            "type": "project_created",
            "project_name": project_info["name"],
            "timestamp": project_info["timestamp"]
        })
        
        return JSONResponse(content=project_info)
    except Exception as e:
        logger.error(f"Error creating new project: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/project/download")
async def download_project(project_type: str = "current"):
    """Download all files in a project as ZIP archive."""
    from fastapi.responses import FileResponse
    try:
        zip_path = project_manager.download_all_files(project_type)
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=Path(zip_path).name,
            headers={"Content-Disposition": f"attachment; filename={Path(zip_path).name}"}
        )
    except Exception as e:
        logger.error(f"Error downloading project: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


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

                # Create new project and archive previous one
                global current_project_name
                project_info = project_manager.create_new_project(requirements)
                current_project_name = project_info["name"]
                
                # Notify frontend about new project creation
                await websocket_manager.broadcast_message({
                    "type": "project_created",
                    "project_name": project_info["name"],
                    "timestamp": project_info["timestamp"],
                    "message": f"📁 New project created: {project_info['name']}"
                })

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
                            
                            # Send task creation notification to PM Agent tab
                            await websocket_manager.send_personal_message({
                                "type": "pm_task_created",
                                "task_id": task.id,
                                "task_title": task.title,
                                "agent_type": task.agent_type,
                                "priority": task.priority,
                                "timestamp": datetime.now().isoformat()
                            }, websocket) # Send to the specific client that initiated

                            if task.agent_type == "dev_agent":
                                # Notify that Dev Agent is starting work on this task
                                await websocket_manager.send_personal_message({
                                    "type": "dev_agent_started",
                                    "task_id": task.id,
                                    "task_title": task.title,
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)
                                # --- Dev Agent Execution with Streaming ---
                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "agent_id": "dev",
                                    "task_id": task.id,
                                    "status": TaskStatus.IN_PROGRESS.value,
                                    "message": f"🔨 Dev Agent executing task: '{task.title}'",
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
                                    "agent_id": "dev",
                                    "task_id": updated_task.id,
                                    "status": updated_task.status.value,
                                    "message": f"✅ Dev Agent task '{updated_task.title}' {updated_task.status.value.lower()}.",
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

                                    # Check QA result status
                                    if qa_task_result.status == TaskStatus.COMPLETED:
                                        # Note: OpsAgent will be triggered after ALL dev tasks are completed
                                        # Individual QA completion no longer triggers Ops
                                        pass
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
                                    "agent_id": "qa",
                                    "task_id": task.id,
                                    "status": TaskStatus.IN_PROGRESS.value,
                                    "message": f"🧪 QA Agent executing task: '{task.title}'",
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
                                    "agent_id": "qa",
                                    "task_id": updated_task.id,
                                    "status": updated_task.status.value,
                                    "message": f"✅ QA Agent task '{updated_task.title}' {updated_task.status.value.lower()}.",
                                    "timestamp": datetime.now().isoformat()
                                }, websocket)

                            elif task.agent_type == "ops_agent": # NEW: Handle ops agent tasks
                                await websocket_manager.send_personal_message({
                                    "type": "task_status_update",
                                    "agent_id": "ops",
                                    "task_id": task.id,
                                    "status": TaskStatus.IN_PROGRESS.value,
                                    "message": f"🚀 Ops Agent executing task: '{task.title}'",
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
                                    "agent_id": "ops",
                                    "task_id": updated_task.id,
                                    "status": updated_task.status.value,
                                    "message": f"✅ Ops Agent task '{updated_task.title}' {updated_task.status.value.lower()}.",
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
                    
                    # Check if we have completed dev tasks that need deployment
                    dev_tasks_completed = [
                        task for task in planner_agent.current_plan.tasks 
                        if task.agent_type == "dev_agent" and task.status == TaskStatus.COMPLETED
                    ]
                    
                    # Trigger OpsAgent only if there are completed dev tasks
                    if dev_tasks_completed:
                        await websocket_manager.send_personal_message({
                            "type": "all_dev_tasks_complete_init_ops",
                            "message": f"All development tasks completed. Initiating production deployment...",
                            "dev_tasks_count": len(dev_tasks_completed),
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
                        
                        # Create a deployment task for OpsAgent
                        deployment_task = Task(
                            id="deployment_final",
                            title="Production Deployment",
                            description=f"Deploy all completed development work to production. {len(dev_tasks_completed)} components ready for deployment.",
                            priority=10,  # Highest priority
                            status=TaskStatus.PENDING,
                            dependencies=[],
                            estimated_hours=1.0,
                            complexity="medium",
                            agent_type="ops_agent"
                        )
                        
                        # Execute OpsAgent deployment
                        ops_result = await ops_agent.execute_task(deployment_task)
                        
                        # Add deployment task to plan
                        planner_agent.current_plan.tasks.append(ops_result)
                        _save_plan(planner_agent.current_plan)
                        
                        await websocket_manager.send_personal_message({
                            "type": "ops_deployment_status",
                            "task_id": deployment_task.id,
                            "status": ops_result.status.value,
                            "message": f"Production deployment {ops_result.status.value.lower()}: {ops_result.result}",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
                    
                    await websocket_manager.send_personal_message({
                        "type": "planning_completed",
                        "message": f"All {total_tasks_processed} tasks for plan '{planner_agent.current_plan.title}' processed. {'Production deployment completed.' if dev_tasks_completed else ''}",
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

# --- QA Task Execution and Ops Triggering ---

async def execute_qa_task(task: Task, websocket: WebSocket):
    """Execute QA task with real-time progress tracking."""
    try:
        logger.info(f"🧪 QA Agent starting: {task.title}")
        
        # Send QA start notification
        await websocket_manager.send_personal_message({
            "type": "qa_started",
            "task_id": task.id,
            "title": task.title,
            "message": f"🧪 Running QA tests for '{task.title}'...",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # Execute QA task
        qa_result = await qa_agent.execute_task(task)
        
        # Send QA completion notification
        if qa_result.status == TaskStatus.COMPLETED:
            await websocket_manager.send_personal_message({
                "type": "qa_complete",
                "task_id": task.id,
                "title": task.title,
                "message": f"✅ QA completed for '{task.title}'",
                "timestamp": datetime.now().isoformat(),
                "qa_result": qa_result.result,
                "test_summary": {
                    "total_tests": qa_result.metadata.get("total_tests", 0),
                    "passed_tests": qa_result.metadata.get("passed_tests", 0),
                    "failed_tests": qa_result.metadata.get("failed_tests", 0)
                }
            }, websocket)
            
            logger.info(f"✅ QA COMPLETE: {task.id} - Ready for Ops deployment")
            
            # Trigger Ops Agent if all QA tasks complete
            await check_and_trigger_ops(websocket)
            
        elif qa_result.status == TaskStatus.FAILED:
            await websocket_manager.send_personal_message({
                "type": "qa_failed",
                "task_id": task.id,
                "title": task.title,
                "message": f"❌ QA failed for '{task.title}'",
                "timestamp": datetime.now().isoformat(),
                "error": qa_result.result
            }, websocket)
            
            logger.error(f"❌ QA FAILED: {task.id} - {qa_result.result}")
        
        return qa_result
        
    except Exception as e:
        logger.error(f"QA task execution error: {e}", exc_info=True)
        await websocket_manager.send_personal_message({
            "type": "qa_error",
            "task_id": task.id,
            "message": f"Error in QA: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        raise


async def check_and_trigger_ops(websocket: WebSocket):
    """Check if all QA tasks are complete and trigger Ops Agent."""
    try:
        if not planner_agent.current_plan:
            return
        
        # Check if all dev tasks have been QA'd
        all_qa_complete = all(
            task.status == TaskStatus.COMPLETED 
            for task in planner_agent.current_plan.tasks 
            if task.agent_type == "qa_agent"
        )
        
        if all_qa_complete:
            logger.info("🚀 All QA complete - Triggering Ops Agent")
            
            await websocket_manager.send_personal_message({
                "type": "ops_trigger",
                "message": "🚀 All QA passed! Starting deployment...",
                "timestamp": datetime.now().isoformat()
            }, websocket)
            
            # Create deployment task
            deployment_task = Task(
                id=f"deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                title="Production Deployment",
                description=f"Deploy {len([t for t in planner_agent.current_plan.tasks if t.agent_type == 'dev_agent'])} completed components",
                priority=10,
                status=TaskStatus.PENDING,
                agent_type="ops_agent"
            )
            
            # Execute Ops Agent
            ops_result = await ops_agent.execute_task(deployment_task)
            
            await websocket_manager.send_personal_message({
                "type": "ops_complete",
                "task_id": deployment_task.id,
                "message": f"✅ Deployment {ops_result.status.value.lower()}: {ops_result.result}",
                "timestamp": datetime.now().isoformat(),
                "deployment_urls": ops_result.metadata.get("deployment_urls", []),
                "github_url": ops_result.metadata.get("github_url"),
                "timestamp": datetime.now().isoformat()
            }, websocket)
        else:
            logger.info("⚠️ Not all QA tasks are complete yet.")
        
    except Exception as e:
        logger.error(f"Ops triggering error: {e}", exc_info=True)
        await websocket_manager.send_personal_message({
            "type": "ops_error",
            "message": f"Error triggering Ops: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, websocket)

# NEW: API endpoint to manually trigger Ops deployment
@app.post("/api/trigger-ops")
async def trigger_ops_deployment(background_tasks: BackgroundTasks):
    """
    Manual trigger for Ops Agent deployment (testing purposes).
    
    Returns:
        Deployment status and details
    """
    try:
        if not planner_agent.current_plan:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "No active plan found. Please create a plan first."
                }
            )
        
        # Get all completed dev tasks
        dev_tasks_completed = [
            task for task in planner_agent.current_plan.tasks 
            if task.agent_type == "dev_agent" and task.status == TaskStatus.COMPLETED
        ]
        
        if not dev_tasks_completed:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "No completed dev tasks to deploy"
                }
            )
        
        # Create deployment task
        deployment_id = f"manual_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        deployment_task = Task(
            id=deployment_id,
            title="Manual Production Deployment",
            description=f"Deploy {len(dev_tasks_completed)} completed components",
            priority=10,
            status=TaskStatus.PENDING,
            agent_type="ops_agent",
            metadata={
                "trigger_type": "manual",
                "deployed_tasks": [t.id for t in dev_tasks_completed]
            }
        )
        
        # Execute Ops Agent
        logger.info(f"🚀 Manual Ops Agent trigger initiated: {deployment_id}")
        ops_result = await ops_agent.execute_task(deployment_task)
        
        # Parse deployment result
        deployment_urls = []
        github_url = None
        
        if ops_result.metadata:
            deployment_urls = ops_result.metadata.get("deployment_urls", [])
            github_url = ops_result.metadata.get("github_url")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "deployment_id": deployment_id,
                "status": ops_result.status.value,
                "message": ops_result.result[:500] if ops_result.result else "Deployment initiated",
                "deployed_tasks": len(dev_tasks_completed),
                "github_url": github_url,
                "deployment_urls": deployment_urls,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Manual Ops trigger failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.get("/api/deployment-status")
async def get_deployment_status():
    """
    Get current deployment status and history.
    
    Returns:
        Deployment statistics and recent deployments
    """
    try:
        if not planner_agent.current_plan:
            return JSONResponse(
                status_code=200,
                content={
                    "has_active_plan": False,
                    "message": "No active plan"
                }
            )
        
        # Count tasks by status
        dev_completed = len([
            t for t in planner_agent.current_plan.tasks 
            if t.agent_type == "dev_agent" and t.status == TaskStatus.COMPLETED
        ])
        
        qa_completed = len([
            t for t in planner_agent.current_plan.tasks 
            if t.agent_type == "qa_agent" and t.status == TaskStatus.COMPLETED
        ])
        
        ops_completed = len([
            t for t in planner_agent.current_plan.tasks 
            if t.agent_type == "ops_agent" and t.status == TaskStatus.COMPLETED
        ])
        
        return JSONResponse(
            status_code=200,
            content={
                "has_active_plan": True,
                "plan_id": planner_agent.current_plan.id,
                "statistics": {
                    "dev_completed": dev_completed,
                    "qa_completed": qa_completed,
                    "ops_completed": ops_completed,
                    "ready_for_deployment": dev_completed > 0 and qa_completed > 0
                },
                "can_deploy": dev_completed > 0,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Deployment status check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
