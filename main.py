# main.py
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from models.task import Task
from parse.websocket_manager import WebSocketManager
from agents.pm_agent import PlannerAgent
from agents.dev_agent import DevAgent
from agents.qa_agent import QAAgent
from models.enums import TaskStatus
import asyncio
from pathlib import Path

# Initialize FastAPI app
app = FastAPI()

# Configure templates and static files
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global managers
websocket_manager = WebSocketManager()

# Initialize agents
planner_agent = PlannerAgent(websocket_manager=websocket_manager)
dev_agent = DevAgent(websocket_manager=websocket_manager)
qa_agent = QAAgent(websocket_manager=websocket_manager)

@app.get("/", response_class=HTMLResponse)
async def get_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "start_planning":
                requirements = data.get("requirements", "")
                context = data.get("context", "")
                # Start planning and broadcast progress
                plan_id = await planner_agent.create_plan(requirements, context)
                plan_status = planner_agent.get_plan_status()
                # Send planning completed message with plan details
                await websocket_manager.broadcast_message({
                    "type": "planning_completed",
                    "plan": planner_agent.current_plan.to_dict() if planner_agent.current_plan else {},
                    "plan_id": plan_id,
                    "message": "Planning completed"
                })
            # You can handle more message types here (e.g., start_dev, start_qa, etc.)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

@app.post("/start")
async def start_pipeline(request: Request):
    data = await request.json()
    requirements = data.get("requirements", "")
    if not requirements:
        return {"error": "Requirements missing"}

    # Step 1: Planner creates a plan
    plan_id = await planner_agent.create_plan(requirements)
    plan_status = planner_agent.get_plan_status()

    # Step 2: Process each task
    for task in planner_agent.current_plan.tasks:
        if task.agent_type == "dev_agent":
            task = await dev_agent.execute_task(task)
        if task.status == TaskStatus.COMPLETED and task.agent_type == "dev_agent":
            task = await qa_agent.execute_task(task)

    return {"plan_id": plan_id, "status": "Pipeline executed"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
