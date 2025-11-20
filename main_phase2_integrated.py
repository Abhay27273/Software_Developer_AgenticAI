"""
Software Developer Agentic AI - Production Ready
Phase 2 Parallel Architecture Integration

Features:
- Feature flag based Phase 1/Phase 2 switching (PHASE2_ENABLED env var)
- Backward compatible with existing sequential flow
- Parallel task execution with dependency analysis
- Auto-scaling worker pool
- Circuit breaker for fault tolerance
- Real-time metrics and monitoring
- Production-ready error handling
"""

import os
import json
import asyncio
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Core models and agents
from models.task import Task
from models.plan import Plan
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from agents.pm_agent import PlannerAgent
from agents.dev_agent import DevAgent
from agents.qa_agent import QAAgent
from agents.ops_agent import OpsAgent

# API routers for production enhancement features
from api.routes import (
    project_router,
    modification_router,
    template_router,
    documentation_router
)

# ============================================================
# CONFIGURATION
# ============================================================

# Feature flags
PHASE2_ENABLED = os.getenv("PHASE2_ENABLED", "false").lower() == "true"

# Phase 2 configuration
DEV_WORKERS_MIN = int(os.getenv("DEV_WORKERS_MIN", "2"))
DEV_WORKERS_MAX = int(os.getenv("DEV_WORKERS_MAX", "10"))
QA_WORKERS_MIN = int(os.getenv("QA_WORKERS_MIN", "2"))
QA_WORKERS_MAX = int(os.getenv("QA_WORKERS_MAX", "8"))
# Circuit breaker: 80% failure rate before opening (more lenient for dev)
CIRCUIT_BREAKER_THRESHOLD = float(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "0.8"))
# Circuit breaker: 60s timeout before attempting recovery
CIRCUIT_BREAKER_TIMEOUT = float(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60.0"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# STARTUP BANNER
# ============================================================

logger.info("=" * 60)
logger.info("🚀 Software Developer Agentic AI v2.0")
logger.info("=" * 60)
logger.info(f"📊 Execution Mode: {'Phase 2 (Parallel)' if PHASE2_ENABLED else 'Phase 1 (Sequential)'}")

if PHASE2_ENABLED:
    logger.info(f"⚙️  Dev Workers: {DEV_WORKERS_MIN}-{DEV_WORKERS_MAX} (auto-scaling)")
    logger.info(f"⚙️  QA Workers: {QA_WORKERS_MIN}-{QA_WORKERS_MAX} (PARALLEL)")
    logger.info(f"🔒 Circuit Breaker: {CIRCUIT_BREAKER_THRESHOLD:.0%} error threshold / {CIRCUIT_BREAKER_TIMEOUT:.0f}s timeout")
    logger.info("✨ Features: Parallel execution, dependency analysis, auto-scaling")
else:
    logger.info("ℹ️  Using sequential execution (stable, predictable)")
    logger.info("💡 Set PHASE2_ENABLED=true to enable parallel execution")

logger.info("=" * 60)

# ============================================================
# DIRECTORY SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
GENERATED_CODE_ROOT = BASE_DIR / "generated_code"
GENERATED_CODE_ROOT.mkdir(parents=True, exist_ok=True)

# Static files
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)

# ============================================================
# GLOBAL STATE
# ============================================================

# WebSocket manager
websocket_manager = WebSocketManager()

# Configure WebSocket manager for API routes (Task 9.1)
from api.routes import set_websocket_manager
set_websocket_manager(websocket_manager)

# Phase 1 agents (always initialized)
planner_agent: Optional[PlannerAgent] = None
dev_agent: Optional[DevAgent] = None
qa_agent: Optional[QAAgent] = None
ops_agent: Optional[OpsAgent] = None

# Phase 2 components (initialized if PHASE2_ENABLED=true)
pipeline_manager = None
task_queue = None
worker_pool = None
event_router = None
circuit_breaker = None
metrics_collector = None
dependency_analyzer = None

# ============================================================
# LIFESPAN MANAGEMENT
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    global planner_agent, dev_agent, qa_agent, ops_agent
    global pipeline_manager, task_queue, worker_pool, event_router
    global circuit_breaker, metrics_collector, dependency_analyzer
    
    # Track if Phase 2 is actually enabled (may fall back to Phase 1)
    phase2_active = PHASE2_ENABLED
    
    # ========================================
    # STARTUP
    # ========================================
    logger.info("")
    logger.info("🔧 Initializing agents and components...")
    logger.info("-" * 60)
    
    # Initialize Phase 1 agents (always needed)
    try:
        planner_agent = PlannerAgent(websocket_manager=websocket_manager)
        dev_agent = DevAgent(websocket_manager=websocket_manager)
        qa_agent = QAAgent(websocket_manager=websocket_manager)
        ops_agent = OpsAgent(
            websocket_manager=websocket_manager,
            generated_code_root=GENERATED_CODE_ROOT
        )
        
        logger.info("✅ Core agents initialized:")
        logger.info(f"   • PM Agent: {planner_agent.agent_id}")
        logger.info(f"   • Dev Agent: {dev_agent.agent_id}")
        logger.info(f"   • QA Agent: {qa_agent.agent_id}")
        logger.info(f"   • Ops Agent: {ops_agent.deployment_id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize agents: {e}")
        raise
    
    # Initialize Phase 2 components if enabled
    if phase2_active:
        try:
            logger.info("")
            logger.info("🚀 Initializing Phase 2 parallel components...")
            
            # Import Phase 2 components (lazy import to avoid errors if not available)
            try:
                from utils.enhanced_pipeline_manager import EnhancedPipelineManager
                
                # Create enhanced pipeline manager with parallel QA workers
                pipeline_manager = EnhancedPipelineManager(
                    dev_workers_min=DEV_WORKERS_MIN,
                    dev_workers_max=DEV_WORKERS_MAX,
                    qa_workers_min=QA_WORKERS_MIN,
                    qa_workers_max=QA_WORKERS_MAX,
                    deploy_workers=1,
                    enable_cache=True,
                    cache_ttl_seconds=3600,
                    cache_max_size=1000,
                    enable_circuit_breaker=True,
                    circuit_failure_threshold=CIRCUIT_BREAKER_THRESHOLD,
                    circuit_timeout_seconds=CIRCUIT_BREAKER_TIMEOUT,
                    scale_up_threshold=10,
                    scale_down_threshold=2,
                    max_retries=3
                )
                
                # Set agents in pipeline manager (base class only takes dev, qa, ops)
                pipeline_manager.set_agents(
                    dev_agent=dev_agent,
                    qa_agent=qa_agent,
                    ops_agent=ops_agent
                )
                
                # Start the pipeline (this starts all worker pools)
                await pipeline_manager.start()
                
                logger.info("   ✅ Enhanced Pipeline Manager")
                logger.info(f"   ✅ Dev Worker Pool: {DEV_WORKERS_MIN}-{DEV_WORKERS_MAX} workers (auto-scaling)")
                logger.info(f"   ✅ QA Worker Pool: {QA_WORKERS_MIN}-{QA_WORKERS_MAX} workers (PARALLEL)")
                logger.info(f"   ✅ Circuit Breakers: {CIRCUIT_BREAKER_THRESHOLD:.0%} threshold")
                logger.info("   ✅ Result Cache: Enabled (1 hour TTL)")
                logger.info("   ✅ Event Router: DLQ + Retries enabled")
                logger.info("   ✅ Dependency Analyzer: Active")
                
                logger.info("")
                logger.info("✅ Phase 2 parallel architecture ready!")
                logger.info("   🚀 Parallel Dev execution: YES")
                logger.info("   🧪 Parallel QA execution: YES")
                logger.info("   📊 Real-time metrics: YES")
                
            except ImportError as ie:
                logger.warning(f"⚠️  Phase 2 components not available: {ie}")
                logger.warning("⚠️  Falling back to Phase 1 sequential mode")
                phase2_active = False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Phase 2 components: {e}")
            logger.warning("⚠️  Falling back to Phase 1 sequential mode")
            phase2_active = False
            # Don't raise, fall back to Phase 1
    
    # Start file monitoring
    try:
        loop = asyncio.get_running_loop()
        event_handler = FileChangeHandler(loop=loop, manager=websocket_manager)
        observer = Observer()
        observer.schedule(event_handler, str(GENERATED_CODE_ROOT), recursive=True)
        
        monitor_thread = threading.Thread(target=observer.start, daemon=True)
        monitor_thread.start()
        logger.info(f"👀 File system monitor started: {GENERATED_CODE_ROOT}")
    except Exception as e:
        logger.warning(f"⚠️  File monitoring not started: {e}")
    
    logger.info("-" * 60)
    logger.info("✅ Application startup complete")
    logger.info("")
    
    yield  # Application runs here
    
    # ========================================
    # SHUTDOWN
    # ========================================
    logger.info("")
    logger.info("🛑 Shutting down application...")
    
    if phase2_active and pipeline_manager:
        try:
            await pipeline_manager.stop(graceful=True, timeout=30.0)
            logger.info("   ✅ Pipeline manager stopped (all worker pools shut down)")
        except Exception as e:
            logger.error(f"⚠️  Shutdown error: {e}")
    
    logger.info("✅ Shutdown complete")

# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Software Developer Agentic AI",
    description="AI-powered software development with PM, Dev, QA, and Ops agents",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers for production enhancement features
app.include_router(project_router)
app.include_router(modification_router)
app.include_router(template_router)
app.include_router(documentation_router)

# Add cache-busting middleware
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    """Add cache-control headers to prevent stale content."""
    response = await call_next(request)
    # Don't cache HTML, CSS, JS files - always get fresh content
    if any(request.url.path.endswith(ext) for ext in ['.html', '.css', '.js', '.json']):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Static files and templates
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def save_plan(plan: Plan):
    """Save plan to disk."""
    if not plan:
        return
    
    plans_dir = GENERATED_CODE_ROOT / "plans" / "parsed"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / f"plan_{plan.id}.json"
    
    try:
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Plan {plan.id} saved to {plan_file.name}")
    except Exception as e:
        logger.error(f"Failed to save plan {plan.id}: {e}")

# ============================================================
# HEALTH AND MONITORING ENDPOINTS
# ============================================================

@app.get("/health")
async def health_check():
    """Health check endpoint with system status."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "mode": "phase2_parallel" if PHASE2_ENABLED else "phase1_sequential",
        "agents": {
            "pm": planner_agent.agent_id if planner_agent else None,
            "dev": dev_agent.agent_id if dev_agent else None,
            "qa": qa_agent.agent_id if qa_agent else None,
            "ops": ops_agent.agent_id if ops_agent else None
        }
    }
    
    if PHASE2_ENABLED and pipeline_manager:
        try:
            stats = pipeline_manager.get_enhanced_stats() if hasattr(pipeline_manager, 'get_enhanced_stats') else {}
            health_status["phase2"] = {
                "dev_workers": {
                    "min": DEV_WORKERS_MIN,
                    "max": DEV_WORKERS_MAX,
                    "active": stats.get("worker_pools", {}).get("unified", {}).get("active_workers", 0)
                },
                "qa_workers": {
                    "min": QA_WORKERS_MIN,
                    "max": QA_WORKERS_MAX,
                    "active": stats.get("worker_pools", {}).get("qa", {}).get("active_workers", 0)
                },
                "tasks": {
                    "total": stats.get("total_tasks", 0),
                    "completed": stats.get("completed_tasks", 0),
                    "failed": stats.get("failed_tasks", 0)
                },
                "cache": {
                    "hit_rate": stats.get("cache", {}).get("hit_rate", 0)
                },
                "circuit_breakers": stats.get("circuit_breakers", {})
            }
        except Exception as e:
            logger.warning(f"Could not get Phase 2 health metrics: {e}")
    
    return health_status


@app.get("/metrics")
async def get_metrics():
    """Get system metrics (Phase 2 only)."""
    if not PHASE2_ENABLED or not pipeline_manager:
        return {
            "error": "Metrics only available in Phase 2 mode",
            "phase2_enabled": PHASE2_ENABLED
        }
    
    try:
        if hasattr(pipeline_manager, 'get_enhanced_stats'):
            return pipeline_manager.get_enhanced_stats()
        else:
            return {"error": "Enhanced stats not available"}
    except Exception as e:
        logger.error(f"Metrics collection error: {e}")
        return {"error": str(e)}


@app.get("/api/deployment-status")
async def get_deployment_status():
    """Get current deployment status and statistics."""
    try:
        if not planner_agent or not planner_agent.current_plan:
            return {
                "has_active_plan": False,
                "message": "No active plan"
            }
        
        plan = planner_agent.current_plan
        
        # Count tasks by status
        dev_completed = len([
            t for t in plan.tasks 
            if t.agent_type == "dev_agent" and t.status == TaskStatus.COMPLETED
        ])
        
        qa_completed = len([
            t for t in plan.tasks 
            if t.agent_type == "qa_agent" and t.status == TaskStatus.COMPLETED
        ])
        
        ops_completed = len([
            t for t in plan.tasks 
            if t.agent_type == "ops_agent" and t.status == TaskStatus.COMPLETED
        ])
        
        return {
            "has_active_plan": True,
            "plan_id": plan.id,
            "plan_title": plan.title,
            "statistics": {
                "total_tasks": len(plan.tasks),
                "dev_completed": dev_completed,
                "qa_completed": qa_completed,
                "ops_completed": ops_completed,
                "ready_for_deployment": dev_completed > 0 and qa_completed > 0
            },
            "can_deploy": dev_completed > 0,
            "execution_mode": "phase2_parallel" if PHASE2_ENABLED else "phase1_sequential",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Deployment status check failed: {e}")
        return {"error": str(e)}

# ============================================================
# MAIN UI
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main application UI with cache-busting headers."""
    response = templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "phase2_enabled": PHASE2_ENABLED,
            "version": "2.0.0"
        }
    )
    # Add cache-busting headers to ensure fresh content
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ============================================================
# FILE MANAGEMENT ENDPOINTS
# ============================================================

@app.get("/api/files")
async def list_generated_files():
    """List generated files as a tree structure."""
    if not GENERATED_CODE_ROOT.is_dir():
        return []
    
    def scan_directory(path: Path):
        items = []
        try:
            sorted_paths = sorted(
                path.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower())
            )
            
            for item in sorted_paths:
                node = {
                    "name": item.name,
                    "path": str(item.relative_to(GENERATED_CODE_ROOT))
                }
                
                if item.is_dir():
                    node["type"] = "directory"
                    node["children"] = scan_directory(item)
                else:
                    node["type"] = "file"
                    node["size"] = item.stat().st_size
                
                items.append(node)
        except Exception as e:
            logger.error(f"Error scanning directory {path}: {e}")
        
        return items
    
    return scan_directory(GENERATED_CODE_ROOT)


@app.get("/api/file-content", response_class=PlainTextResponse)
async def get_file_content(path: str):
    """Get content of a specific file."""
    try:
        # Security: Resolve and validate path
        file_path = (GENERATED_CODE_ROOT / path).resolve()
        
        if not file_path.is_relative_to(GENERATED_CODE_ROOT.resolve()):
            raise HTTPException(
                status_code=403,
                detail="Access denied: Path outside allowed directory"
            )
        
        if ".git" in file_path.parts:
            return "[Error] Cannot view .git directory files"
        
        if not file_path.is_file():
            return "[Error] File not found or is a directory"
        
        # Try reading as text
        try:
            content = file_path.read_text(encoding="utf-8")
            return content
        except UnicodeDecodeError:
            return "[Error] File is binary or not UTF-8 encoded"
            
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return f"[Error] Could not read file: {e}"

# ============================================================
# STREAMING HELPER FUNCTIONS
# ============================================================

async def execute_dev_task_with_streaming(task: Task, websocket: WebSocket):
    """Execute Dev Agent task with streaming progress updates."""
    try:
        await websocket_manager.send_personal_message({
            "type": "dev_agent_started",
            "task_id": task.id,
            "task_title": task.title,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        # Execute the dev task
        updated_task = await dev_agent.execute_task(task)
        
        # Update plan
        if planner_agent.current_plan:
            for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                if p_task.id == updated_task.id:
                    planner_agent.current_plan.tasks[idx] = updated_task
                    break
            save_plan(planner_agent.current_plan)
        
        await websocket_manager.send_personal_message({
            "type": "task_status_update",
            "agent_id": "dev",
            "task_id": updated_task.id,
            "status": updated_task.status.value,
            "message": f"Dev Agent task '{updated_task.title}' {updated_task.status.value.lower()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        return updated_task
        
    except Exception as e:
        logger.error(f"Dev task execution error: {e}")
        await websocket_manager.send_personal_message({
            "type": "dev_task_failed",
            "task_id": task.id,
            "message": f"Dev task failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        task.status = TaskStatus.FAILED
        return task


async def execute_qa_task_with_streaming(task: Task, websocket: WebSocket):
    """
    Executes a QA task by calling the QA agent, which now handles its own streaming.
    This simplified function delegates all testing and streaming logic to the agent.
    """
    logger.info(f"🚀 Delegating QA task to agent for: {task.id} - '{task.title}'")
    
    # The QA agent's `execute_task` now handles all streaming, file loading, and logic.
    # We just need to call it and wait for the final, updated task object.
    updated_task = await qa_agent.execute_task(task)
    
    # Update the plan with the final result from the QA agent
    if planner_agent.current_plan:
        for idx, p_task in enumerate(planner_agent.current_plan.tasks):
            if p_task.id == updated_task.id:
                planner_agent.current_plan.tasks[idx] = updated_task
                break
        save_plan(planner_agent.current_plan)
        
    logger.info(f"✅ QA task execution finished for {task.id}. Final status: {updated_task.status.value}")
    
    # The QA agent is responsible for sending the final 'qa_complete' or 'qa_failed' message.
    # This function just ensures the plan is updated.
    return updated_task


async def generate_dev_summary(websocket: WebSocket):
    """Generate a comprehensive summary of all development work completed."""
    try:
        if not planner_agent or not planner_agent.current_plan:
            return
        
        plan = planner_agent.current_plan
        dev_tasks = [t for t in plan.tasks if t.agent_type == "dev_agent" and t.status == TaskStatus.COMPLETED]
        
        if not dev_tasks:
            return
        
        # Collect all files created
        all_files = []
        file_categories = {
            "backend": [],
            "frontend": [],
            "config": [],
            "tests": [],
            "docker": [],
            "other": []
        }
        
        api_keys_needed = set()
        environment_vars = set()
        
        for task in dev_tasks:
            if task.metadata and "output_directory" in task.metadata:
                output_dir = GENERATED_CODE_ROOT.parent / task.metadata["output_directory"]
                if output_dir.exists():
                    for file_path in output_dir.rglob("*"):
                        if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                            rel_path = str(file_path.relative_to(output_dir))
                            all_files.append(rel_path)
                            
                            # Categorize files
                            file_lower = rel_path.lower()
                            if any(x in file_lower for x in ['test_', 'tests/', 'conftest']):
                                file_categories["tests"].append(rel_path)
                            elif 'dockerfile' in file_lower or 'docker-compose' in file_lower:
                                file_categories["docker"].append(rel_path)
                            elif any(x in file_lower for x in ['package.json', '.env', 'requirements.txt', 'config', 'settings']):
                                file_categories["config"].append(rel_path)
                            elif any(x in file_lower for x in ['api/', 'server/', 'backend/', 'src/core/', 'src/db/', 'src/models/']):
                                file_categories["backend"].append(rel_path)
                            elif any(x in file_lower for x in ['client/', 'frontend/', 'src/components/', 'src/pages/', '.tsx', '.jsx', '.html', '.css']):
                                file_categories["frontend"].append(rel_path)
                            else:
                                file_categories["other"].append(rel_path)
                            
                            # Check for API keys and environment variables
                            if file_path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.env']:
                                try:
                                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                                    # Look for common API key patterns
                                    if 'API_KEY' in content or 'SECRET_KEY' in content or 'ACCESS_TOKEN' in content:
                                        for line in content.split('\n'):
                                            if any(key in line.upper() for key in ['API_KEY', 'SECRET_KEY', 'ACCESS_TOKEN', 'CLIENT_ID', 'CLIENT_SECRET']):
                                                # Extract variable name
                                                if '=' in line:
                                                    var_name = line.split('=')[0].strip().strip('"\'')
                                                    if var_name and not var_name.startswith('#'):
                                                        api_keys_needed.add(var_name)
                                    
                                    # Look for environment variables
                                    if 'os.getenv' in content or 'process.env' in content or '.env' in file_path.name:
                                        import re
                                        env_vars = re.findall(r'(?:os\.getenv|process\.env)\([\'"]([A-Z_]+)[\'"]', content)
                                        environment_vars.update(env_vars)
                                except:
                                    pass
        
        # Build summary message
        summary = f"## 📦 **Development Summary**\n\n"
        summary += f"✅ **{len(dev_tasks)} development tasks completed successfully!**\n\n"
        
        # List main implementations
        summary += "### 🎯 **What Was Built:**\n"
        for idx, task in enumerate(dev_tasks, 1):
            summary += f"{idx}. **{task.title}**\n"
            if task.description:
                summary += f"   _{task.description[:100]}..._\n" if len(task.description) > 100 else f"   _{task.description}_\n"
        
        summary += f"\n### 📁 **Files Created: {len(all_files)} total**\n"
        
        if file_categories["backend"]:
            summary += f"\n**Backend/API ({len(file_categories['backend'])} files):**\n"
            for f in file_categories["backend"][:5]:  # Show first 5
                summary += f"- `{f}`\n"
            if len(file_categories["backend"]) > 5:
                summary += f"  _(and {len(file_categories['backend']) - 5} more backend files)_\n"
        
        if file_categories["frontend"]:
            summary += f"\n**Frontend/UI ({len(file_categories['frontend'])} files):**\n"
            for f in file_categories["frontend"][:5]:
                summary += f"- `{f}`\n"
            if len(file_categories["frontend"]) > 5:
                summary += f"  _(and {len(file_categories['frontend']) - 5} more frontend files)_\n"
        
        if file_categories["config"]:
            summary += f"\n**Configuration ({len(file_categories['config'])} files):**\n"
            for f in file_categories["config"]:
                summary += f"- `{f}`\n"
        
        if file_categories["docker"]:
            summary += f"\n**Docker ({len(file_categories['docker'])} files):**\n"
            for f in file_categories["docker"]:
                summary += f"- `{f}`\n"
        
        if file_categories["tests"]:
            summary += f"\n**Tests ({len(file_categories['tests'])} files):**\n"
            for f in file_categories["tests"][:3]:
                summary += f"- `{f}`\n"
            if len(file_categories["tests"]) > 3:
                summary += f"  _(and {len(file_categories['tests']) - 3} more test files)_\n"
        
        # Configuration needed
        if api_keys_needed or environment_vars:
            summary += "\n### 🔐 **Configuration Required:**\n\n"
            summary += "You'll need to set up these environment variables:\n\n"
            
            all_vars = api_keys_needed.union(environment_vars)
            for var in sorted(all_vars):
                summary += f"- `{var}`\n"
            
            summary += f"\n📝 **Action Required:**\n"
            summary += f"1. Create a `.env` file in your project root\n"
            summary += f"2. Add your API keys and secrets\n"
            summary += f"3. Never commit `.env` to version control\n"
        
        # Next steps
        summary += "\n### 🚀 **Next Steps:**\n\n"
        summary += "1. **Review Files**: Check the generated code in the file viewer\n"
        summary += "2. **QA Testing**: Review QA results in the QA Agent tab\n"
        summary += "3. **Configuration**: Set up environment variables if needed\n"
        summary += "4. **Deployment**: Ops Agent will deploy to production\n\n"
        
        summary += "_All files are available in the file tree on the left. Click to view!_"
        
        # Send to chat
        await websocket_manager.send_personal_message({
            "type": "dev_summary",
            "message": summary,
            "stats": {
                "total_tasks": len(dev_tasks),
                "total_files": len(all_files),
                "backend_files": len(file_categories["backend"]),
                "frontend_files": len(file_categories["frontend"]),
                "config_files": len(file_categories["config"]),
                "test_files": len(file_categories["tests"]),
                "api_keys_needed": len(api_keys_needed),
                "env_vars": len(environment_vars)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        logger.info(f"📊 Development summary generated: {len(all_files)} files across {len(dev_tasks)} tasks")
        
    except Exception as e:
        logger.error(f"Failed to generate dev summary: {e}", exc_info=True)


async def check_and_trigger_ops_fixed(websocket: WebSocket):
    """Check if ALL dev AND qa tasks are complete, then ask user about GitHub deployment."""
    try:
        if not planner_agent or not planner_agent.current_plan:
            logger.debug("No active plan for ops check")
            return
        
        plan = planner_agent.current_plan
        
        # Get all dev tasks (exclude QA-only tasks like "Full Game Quality Assurance")
        dev_tasks = [t for t in plan.tasks if t.agent_type == "dev_agent"]
        dev_completed = [t for t in dev_tasks if t.status == TaskStatus.COMPLETED]
        dev_failed = [t for t in dev_tasks if t.status == TaskStatus.FAILED]
        
        # Get all qa tasks
        qa_tasks = [t for t in plan.tasks if t.agent_type == "qa_agent"]
        qa_completed = [t for t in qa_tasks if t.status == TaskStatus.COMPLETED]
        qa_failed = [t for t in qa_tasks if t.status == TaskStatus.FAILED]
        
        # Check if ops already triggered
        ops_tasks = [t for t in plan.tasks if t.agent_type == "ops_agent"]
        
        logger.info(f"🔍 Ops Check: Dev {len(dev_completed)}/{len(dev_tasks)}, QA {len(qa_completed)}/{len(qa_tasks)}, Ops: {len(ops_tasks)}")
        
        # NEW LOGIC: Trigger deployment if:
        # 1. At least 50% of dev tasks completed OR all dev tasks are done (success or fail)
        # 2. All QA tasks are done (success or fail)
        # 3. No ops task already exists
        all_dev_done = len(dev_completed) + len(dev_failed) == len(dev_tasks)
        all_qa_done = len(qa_completed) + len(qa_failed) == len(qa_tasks)
        at_least_half_dev_success = len(dev_completed) >= len(dev_tasks) * 0.5
        
        if not dev_tasks:
            logger.debug("No dev tasks found")
            return
        
        if not (all_dev_done and all_qa_done):
            logger.debug(f"Not all tasks done yet. Dev: {all_dev_done}, QA: {all_qa_done}")
            return
        
        if not at_least_half_dev_success:
            logger.warning(f"⚠️ Less than 50% dev tasks succeeded. Only {len(dev_completed)}/{len(dev_tasks)} passed. Deployment may not work properly.")
        
        if ops_tasks:
            logger.debug("Ops already triggered")
            return
        
        # Generate and send development summary before deployment
        await generate_dev_summary(websocket)
        
        # All checks passed - ASK user about deployment
        logger.info(f"🚀 All Dev ({len(dev_completed)}/{len(dev_tasks)}) and QA ({len(qa_completed)}/{len(qa_tasks)}) tasks complete - Asking user to trigger Ops Agent")
        
        await websocket_manager.send_personal_message({
            "type": "request_github_deployment",
            "message": f"""🎉 **Development Complete!**

✅ **Successfully Completed:**
- Dev Tasks: {len(dev_completed)}/{len(dev_tasks)}
- QA Tasks: {len(qa_completed)}/{len(qa_tasks)}

{"⚠️ **Note:** Some tasks failed, but you can still deploy the working components." if (len(dev_failed) > 0 or len(qa_failed) > 0) else ""}

Would you like to deploy this project to GitHub and Render?

**What you need:**
1. **GitHub Personal Access Token** (required)
   - Create at: https://github.com/settings/tokens/new?scopes=repo,workflow
   - Needs `repo` and `workflow` permissions

2. **Render API Key** (optional, for automatic deployment)
   - Get from: https://dashboard.render.com/account/settings#api-keys
   - If not provided, you'll need to manually deploy from GitHub

**What will be deployed:**
- All {len(dev_completed)} successfully generated modules
- Complete project structure with dependencies
- Automated setup on Render (if API key provided)""",
            "dev_tasks_count": len(dev_completed),
            "qa_tasks_count": len(qa_completed),
            "dev_failed_count": len(dev_failed),
            "qa_failed_count": len(qa_failed),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
    except Exception as e:
        logger.error(f"Ops triggering error: {e}")
        await websocket_manager.send_personal_message({
            "type": "ops_error",
            "message": f"Deployment error: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
# ...existing code...
async def execute_ops_deployment(websocket: WebSocket, github_token: Optional[str], render_api_key: Optional[str] = None):
    """Execute Ops Agent deployment with user-provided GitHub token and Render API key."""
    try:
        if not planner_agent or not planner_agent.current_plan:
            raise ValueError("Cannot deploy without an active plan.")

        plan = planner_agent.current_plan
        dev_completed = [t for t in plan.tasks if t.agent_type == "dev_agent" and t.status == TaskStatus.COMPLETED]

        # Check if user declined deployment
        if not github_token:
            await websocket_manager.send_personal_message({
                "type": "ops_deployment_status",
                "status": "skipped",
                "message": "✋ Deployment to GitHub skipped by user. Your files are ready in the generated_code folder.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, websocket)
            logger.info("User skipped GitHub deployment.")
            return

        # User confirmed - proceed with deployment
        await websocket_manager.send_personal_message({
            "type": "all_tasks_complete_init_ops",
            "message": "🚀 User confirmed deployment. Initiating GitHub repository creation and Render deployment...",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)

        # Create deployment task with GitHub token and Render API key in metadata
        deployment_task = Task(
            id=f"deployment_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            title="Production Deployment to GitHub & Render",
            description=f"Deploy {len(dev_completed)} completed components (QA verified) to GitHub and Render",
            priority=10,
            status=TaskStatus.PENDING,
            agent_type="ops_agent",
            dependencies=[],
            estimated_hours=1.0,
            complexity="medium",
            metadata={
                "github_token": github_token,  # Pass token securely to ops agent
                "render_api_key": render_api_key or os.getenv("RENDER_API_KEY"),  # Use provided or env var
                "deployment_type": "github_and_render"
            }
        )

        # Execute Ops Agent
        logger.info(f"🔧 Executing Ops Agent with GitHub token and Render API key...")
        ops_result = await ops_agent.execute_task(deployment_task)

        # Add to plan
        plan.tasks.append(ops_result)
        save_plan(plan)

        # Send final status to user
        await websocket_manager.send_personal_message({
            "type": "ops_deployment_status",
            "task_id": deployment_task.id,
            "status": ops_result.status.value,
            "message": f"🎯 Production deployment {ops_result.status.value.lower()}: {ops_result.result}",
            "deployment_urls": ops_result.metadata.get("deployment_urls", []),
            "github_url": ops_result.metadata.get("github_url"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)

        if ops_result.status == TaskStatus.COMPLETED:
            logger.info(f"✅ Deployment completed successfully!")
        else:
            logger.warning(f"⚠️ Deployment finished with status: {ops_result.status.value}")

    except Exception as e:
        logger.error(f"Ops execution error: {e}", exc_info=True)
        await websocket_manager.send_personal_message({
            "type": "ops_error",
            "message": f"❌ Deployment execution failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)

# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time agent communication."""
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info(f"🔌 WebSocket connection attempt from {client_host}")
    
    await websocket.accept()
    logger.info(f"✅ WebSocket connection accepted for {client_host}")
    
    receive_task = None
    
    try:
        await websocket_manager.connect(websocket)
        logger.info(f"📡 WebSocket connected to manager for {client_host}")
        
        # Send welcome message
        welcome_msg = {
            "type": "connection",
            "message": "Connected to Software Developer Agentic AI",
            "mode": "phase2_parallel" if PHASE2_ENABLED else "phase1_sequential",
            "version": "2.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket_manager.send_personal_message(welcome_msg, websocket)
        logger.info(f"📨 Sent welcome message to {client_host}: {welcome_msg}")
        
        while True:
            try:
                # Set a timeout for receiving messages (60 seconds)
                receive_task = asyncio.create_task(websocket.receive_json())
                data = await asyncio.wait_for(receive_task, timeout=60.0)
                
                msg_type = data.get("type")
                
                if msg_type == "start_planning":
                    requirements = data.get("requirements", "")
                    
                    if not requirements:
                        await websocket_manager.send_personal_message({
                            "type": "error",
                            "message": "Requirements are missing",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }, websocket)
                        continue
                    
                    # Route to appropriate execution flow
                    if PHASE2_ENABLED and pipeline_manager:
                        await execute_with_phase2(websocket, requirements)
                    else:
                        await execute_sequential(websocket, requirements)
                
                elif msg_type == "github_deployment_response":
                    # Handle user's response to GitHub deployment prompt
                    github_token = data.get("github_token")  # Will be None if user declined
                    render_api_key = data.get("render_api_key")  # Optional Render API key
                    await execute_ops_deployment(websocket, github_token, render_api_key)
                
                elif msg_type == "request_file_content":
                    await handle_file_content_request(websocket, data)
                
                elif msg_type == "ping":
                    # Respond to ping to keep connection alive
                    await websocket_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }, websocket)
                
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    await websocket_manager.send_personal_message({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }, websocket)
            
            except asyncio.TimeoutError:
                # Send keepalive ping after timeout
                if websocket in websocket_manager.active_connections:
                    try:
                        await websocket.send_json({
                            "type": "keepalive",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        logger.debug(f"💓 Sent keepalive to {client_host}")
                    except Exception:
                        # Connection lost
                        logger.warning(f"⚠️ Keepalive failed for {client_host} - connection lost")
                        break
                else:
                    break
            
            except WebSocketDisconnect:
                logger.info(f"🔌 Client disconnected: {client_host}")
                break
            
            except Exception as e:
                logger.error(f"❌ Error processing message from {client_host}: {e}")
                if websocket in websocket_manager.active_connections:
                    try:
                        await websocket_manager.send_personal_message({
                            "type": "error",
                            "message": f"Error: {str(e)}",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }, websocket)
                    except:
                        pass
                break
    
    except WebSocketDisconnect:
        logger.info(f"🔌 Client disconnected: {client_host}")
    except Exception as e:
        logger.exception(f"❌ WebSocket error for client {client_host}: {e}")
    finally:
        # Clean up receive task
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except (asyncio.CancelledError, Exception):
                pass
        websocket_manager.disconnect(websocket)
        logger.info(f"🔌 WebSocket cleanup complete for {client_host}")


async def handle_file_content_request(websocket: WebSocket, data: dict):
    """Handle file content requests via WebSocket."""
    file_path_str = data.get("file_path")
    
    # Handle welcome message
    if file_path_str == "welcome":
        await websocket_manager.send_personal_message({
            "type": "file_content_response",
            "file_path": "welcome",
            "content": "Welcome to AI Planning Agent\n\nYour generated code files will appear here.\nClick on files in the left panel to view their contents.",
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        return
    
    if not file_path_str:
        await websocket_manager.send_personal_message({
            "type": "file_content_response",
            "file_path": None,
            "content": None,
            "error": "File path not provided",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        return
    
    try:
        # Security: Resolve and validate path
        file_path = (GENERATED_CODE_ROOT / file_path_str).resolve()
        
        if not file_path.is_relative_to(GENERATED_CODE_ROOT.resolve()):
            raise HTTPException(
                status_code=403,
                detail="Access denied: Path outside allowed directory"
            )
        
        if ".git" in file_path.parts:
            content = "[Error] Cannot view .git directory files"
            error = "Access denied"
        elif not file_path.is_file():
            content = None
            error = "File not found or is a directory"
        else:
            try:
                content = file_path.read_text(encoding="utf-8")
                error = None
            except UnicodeDecodeError:
                content = None
                error = "File is binary or not UTF-8 encoded"
        
        await websocket_manager.send_personal_message({
            "type": "file_content_response",
            "file_path": file_path_str,
            "content": content,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
    except Exception as e:
        logger.error(f"Error reading file {file_path_str}: {e}")
        await websocket_manager.send_personal_message({
            "type": "file_content_response",
            "file_path": file_path_str,
            "content": None,
            "error": f"Error reading file: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)

# ============================================================
# EXECUTION FLOWS
# ============================================================

async def execute_sequential(websocket: WebSocket, user_request: str):
    """
    Execute using Phase 1 sequential architecture.
    
    This is the stable, production-tested flow that processes tasks one by one.
    """
    try:
        logger.info(f"🔄 Starting Phase 1 sequential execution")
        
        # Step 1: PM Agent creates plan
        await websocket_manager.send_personal_message({
            "type": "planning_started",
            "message": "PM Agent creating project plan...",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        # Stream tasks from PM Agent
        async for task_message in planner_agent.create_plan_and_stream_tasks(user_request, websocket):
            if task_message["type"] == "task_created":
                task: Task = task_message["task"]
                
                # Notify task creation
                await websocket_manager.send_personal_message({
                    "type": "pm_task_created",
                    "task_id": task.id,
                    "task_title": task.title,
                    "agent_type": task.agent_type,
                    "priority": task.priority,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, websocket)
                
                # Execute task based on agent type
                if task.agent_type == "dev_agent":
                    await execute_dev_task_sequential(task, websocket)
                    
                elif task.agent_type == "qa_agent":
                    await execute_qa_task_sequential(task, websocket)
                    
                elif task.agent_type == "ops_agent":
                    await execute_ops_task_sequential(task, websocket)
                    
                else:
                    logger.warning(f"Unknown agent type: {task.agent_type}")
                    task.status = TaskStatus.SKIPPED
                    save_plan(planner_agent.current_plan)
        
        # Check if we should trigger deployment (with fixed logic)
        if planner_agent.current_plan:
            await check_and_trigger_ops_fixed(websocket)
            
            # Send completion message
            await websocket_manager.send_personal_message({
                "type": "planning_completed",
                "message": f"All tasks completed for plan '{planner_agent.current_plan.title}'",
                "plan": planner_agent.current_plan.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, websocket)
        
    except Exception as e:
        logger.exception("Sequential execution error")
        await websocket_manager.send_personal_message({
            "type": "pipeline_failed",
            "message": f"Execution error: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)


async def execute_dev_task_sequential(task: Task, websocket: WebSocket):
    """Execute Dev Agent task in sequential mode with streaming."""
    try:
        # Use the new streaming function
        updated_task = await execute_dev_task_with_streaming(task, websocket)
        
        # Trigger QA if dev completed successfully
        if updated_task.status == TaskStatus.COMPLETED:
            await execute_qa_after_dev(updated_task, websocket)
            
    except Exception as e:
        logger.error(f"Dev task execution error: {e}")
        await websocket_manager.send_personal_message({
            "type": "dev_task_failed",
            "task_id": task.id,
            "message": f"Dev task failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)


async def execute_qa_after_dev(dev_task: Task, websocket: WebSocket):
    """Execute QA Agent after dev task completes with file-by-file streaming."""
    try:
        await websocket_manager.send_personal_message({
            "type": "dev_task_complete_init_qa",
            "task_id": dev_task.id,
            "title": dev_task.title,
            "message": f"Development completed. Initiating QA with file-by-file testing...",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        # Use the new streaming QA function
        qa_result = await execute_qa_task_with_streaming(dev_task, websocket)
        
        # Check if we should trigger Ops after this QA completes
        await check_and_trigger_ops_fixed(websocket)
        
    except Exception as e:
        logger.error(f"QA execution error: {e}")
        await websocket_manager.send_personal_message({
            "type": "qa_error",
            "task_id": dev_task.id,
            "message": f"QA failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)


async def execute_qa_task_sequential(task: Task, websocket: WebSocket):
    """Execute standalone QA Agent task with file-by-file streaming."""
    try:
        # Use the new streaming QA function
        updated_task = await execute_qa_task_with_streaming(task, websocket)
        
        # Check if we should trigger Ops after this QA completes
        await check_and_trigger_ops_fixed(websocket)
        
    except Exception as e:
        logger.error(f"QA task error: {e}")
        await websocket_manager.send_personal_message({
            "type": "qa_error",
            "task_id": task.id,
            "message": f"QA task failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)


async def execute_ops_task_sequential(task: Task, websocket: WebSocket):
    """Execute standalone Ops Agent task."""
    try:
        await websocket_manager.send_personal_message({
            "type": "task_status_update",
            "agent_id": "ops",
            "task_id": task.id,
            "status": TaskStatus.IN_PROGRESS.value,
            "message": f"Ops Agent executing task: '{task.title}'",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        updated_task = await ops_agent.execute_task(task)
        
        if planner_agent.current_plan:
            for idx, p_task in enumerate(planner_agent.current_plan.tasks):
                if p_task.id == updated_task.id:
                    planner_agent.current_plan.tasks[idx] = updated_task
                    break
            save_plan(planner_agent.current_plan)
        
        await websocket_manager.send_personal_message({
            "type": "task_status_update",
            "agent_id": "ops",
            "task_id": updated_task.id,
            "status": updated_task.status.value,
            "message": f"Ops Agent task '{updated_task.title}' {updated_task.status.value.lower()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
    except Exception as e:
        logger.error(f"Ops task error: {e}")


async def check_and_trigger_ops(websocket: WebSocket):
    """Check if all dev tasks are complete and trigger Ops deployment."""
    try:
        if not planner_agent or not planner_agent.current_plan:
            return
        
        # Get completed dev tasks
        dev_tasks_completed = [
            task for task in planner_agent.current_plan.tasks 
            if task.agent_type == "dev_agent" and task.status == TaskStatus.COMPLETED
        ]
        
        if not dev_tasks_completed:
            return
        
        logger.info(f"🚀 All dev tasks complete - Triggering Ops Agent")
        
        await websocket_manager.send_personal_message({
            "type": "all_dev_tasks_complete_init_ops",
            "message": f"All {len(dev_tasks_completed)} development tasks completed. Initiating production deployment...",
            "dev_tasks_count": len(dev_tasks_completed),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        # Create deployment task
        deployment_task = Task(
            id=f"deployment_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            title="Production Deployment",
            description=f"Deploy {len(dev_tasks_completed)} completed components to production",
            priority=10,
            status=TaskStatus.PENDING,
            agent_type="ops_agent",
            metadata={
                "trigger_type": "manual",
                "deployed_tasks": [t.id for t in dev_tasks_completed]
            }
        )
        
        # Execute Ops Agent
        ops_result = await ops_agent.execute_task(deployment_task)
        
        # Add to plan
        planner_agent.current_plan.tasks.append(ops_result)
        save_plan(planner_agent.current_plan)
        
        await websocket_manager.send_personal_message({
            "type": "ops_deployment_status",
            "task_id": deployment_task.id,
            "status": ops_result.status.value,
            "message": f"Production deployment {ops_result.status.value.lower()}: {ops_result.result}",
            "deployment_urls": ops_result.metadata.get("deployment_urls", []),
            "github_url": ops_result.metadata.get("github_url"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
    except Exception as e:
        logger.error(f"Ops triggering error: {e}")
        await websocket_manager.send_personal_message({
            "type": "ops_error",
            "message": f"Deployment error: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)


async def execute_with_phase2(websocket: WebSocket, user_request: str):
    """
    Execute using Phase 2 parallel architecture with parallel QA workers.
    
    This enables:
    - PM Agent generates plan
    - Dependency analysis for optimal execution order
    - Parallel Dev task execution (2-10 workers, auto-scaling)
    - Parallel QA task execution (2-8 workers, auto-scaling) ← NEW!
    - Circuit breaker protection
    - Result caching
    - Event-driven routing with DLQ
    - Real-time metrics
    """
    try:
        logger.info(f"⚡ Starting Phase 2 parallel execution with parallel QA workers")
        
        await websocket_manager.send_personal_message({
            "type": "planning_started",
            "message": "Phase 2: PM Agent creating plan with dependency analysis...",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        # Step 1: PM Agent creates plan
        async for task_message in planner_agent.create_plan_and_stream_tasks(user_request, websocket):
            if task_message["type"] == "task_created":
                # Just notify, don't execute yet
                task = task_message["task"]
                await websocket_manager.send_personal_message({
                    "type": "pm_task_created",
                    "task_id": task.id,
                    "task_title": task.title,
                    "agent_type": task.agent_type,
                    "priority": task.priority,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, websocket)
        
        # After streaming completes, check if plan was created
        if not planner_agent.current_plan:
            raise ValueError("No plan created by PM Agent")
        
        plan = planner_agent.current_plan
        
        await websocket_manager.send_personal_message({
            "type": "status",
            "message": f"Plan created: {len(plan.tasks)} tasks. Starting parallel execution...",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        # Step 2: Analyze dependencies and submit to pipeline
        analysis_stats = await pipeline_manager.analyze_and_submit_plan(
            plan=plan.to_dict(),
            websocket=websocket,
            project_desc=user_request
        )
        
        await websocket_manager.send_personal_message({
            "type": "phase2_execution_started",
            "message": f"Parallel execution started: {analysis_stats['batches']} dependency batches",
            "stats": analysis_stats,
            "dev_workers": f"{DEV_WORKERS_MIN}-{DEV_WORKERS_MAX}",
            "qa_workers": f"{QA_WORKERS_MIN}-{QA_WORKERS_MAX}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        # Step 3: Wait for pipeline to complete
        await pipeline_manager.wait_until_complete()
        
        # Step 4: Send completion message
        final_stats = pipeline_manager.get_enhanced_stats()
        
        await websocket_manager.send_personal_message({
            "type": "planning_completed",
            "message": f"Phase 2 parallel execution completed! {final_stats['completed_tasks']} tasks done.",
            "plan": plan.to_dict(),
            "stats": final_stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)
        
        logger.info(
            f"✅ Phase 2 execution complete: "
            f"{final_stats['completed_tasks']}/{final_stats['total_tasks']} tasks, "
            f"{final_stats.get('cache', {}).get('hit_rate', 0)}% cache hit rate"
        )
        
    except Exception as e:
        logger.exception("Phase 2 execution error")
        await websocket_manager.send_personal_message({
            "type": "pipeline_failed",
            "message": f"Phase 2 execution failed: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, websocket)

# ============================================================
# MANUAL OPS TRIGGER API
# ============================================================

@app.post("/api/trigger-ops")
async def trigger_ops_deployment():
    """Manually trigger Ops Agent deployment (for testing)."""
    try:
        if not planner_agent or not planner_agent.current_plan:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "No active plan found. Please create a plan first."
                }
            )
        
        # Get completed dev tasks
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
        deployment_id = f"manual_deploy_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
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
        logger.info(f"🚀 Manual Ops trigger: {deployment_id}")
        ops_result = await ops_agent.execute_task(deployment_task)
        
        return {
            "success": True,
            "deployment_id": deployment_id,
            "status": ops_result.status.value,
            "message": ops_result.result[:500] if ops_result.result else "Deployment initiated",
            "deployed_tasks": len(dev_tasks_completed),
            "github_url": ops_result.metadata.get("github_url"),
            "deployment_urls": ops_result.metadata.get("deployment_urls", []),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.exception("Manual Ops trigger failed")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

# ============================================================
# FILE MONITORING
# ============================================================

class FileChangeHandler(FileSystemEventHandler):
    """Monitor file system changes and notify via WebSocket."""
    
    def __init__(self, loop, manager: WebSocketManager):
        self.loop = loop
        self.manager = manager
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        try:
            relative_path = os.path.relpath(event.src_path, str(GENERATED_CODE_ROOT))
            logger.debug(f"✅ New file detected: {relative_path}")
            
            message = {
                "type": "file_generated",
                "file_path": relative_path,
                "file_name": os.path.basename(event.src_path),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Schedule on main event loop
            asyncio.run_coroutine_threadsafe(
                self.manager.broadcast_message(message),
                self.loop
            )
        except Exception as e:
            logger.error(f"File change handler error: {e}")

# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860,
        log_level=LOG_LEVEL.lower()
    )

