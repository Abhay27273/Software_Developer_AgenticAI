# ops_agent.py
import subprocess
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from models.task import Task
from models.enums import TaskStatus

# Configure logging for the OpsAgent
logger = logging.getLogger(__name__)

class OpsAgent:
    """
    The OpsAgent is responsible for taking the developed code, preparing it for deployment,
    and managing the deployment process. This includes creating a Git repository,
    generating a Dockerfile, and building a Docker image.
    """
    def __init__(self, websocket_manager, generated_code_root: Path):
        self.websocket_manager = websocket_manager
        self.generated_code_root = generated_code_root
        self.repo_path = self.generated_code_root / "repo"
        self.repo_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ops Agent initialized, repository path: {self.repo_path}")

    async def execute_task(self, task: Task):
        """
        Executes a given Ops task. The logic is divided into distinct, comment-rich sections.
        """
        task.status = TaskStatus.IN_PROGRESS
        await self.websocket_manager.broadcast_message({
            "type": "task_status_update",
            "task_id": task.id,
            "status": task.status.value,
            "message": f"Ops Agent is starting task: '{task.title}'",
            "timestamp": datetime.now().isoformat()
        })

        try:
            # --- 1. Repository Creation and Commit ---
            await self._run_git_operations()

            # --- 2. Dockerfile and Requirements Generation ---
            await self._generate_docker_artifacts()

            # --- 3. Docker Image Build ---
            await self._build_docker_image()
            
            # --- 4. Simulated CI/CD and Deployment (Suggested functionality) ---
            await self._simulate_deployment()

            task.status = TaskStatus.COMPLETED
            task.result = "Deployment artifacts created and a Docker image was built successfully."
            await self.websocket_manager.broadcast_message({
                "type": "task_status_update",
                "task_id": task.id,
                "status": task.status.value,
                "message": f"Ops Agent completed task: '{task.title}'",
                "timestamp": datetime.now().isoformat()
            })

        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed with exit code {e.returncode}: {e.cmd}")
            task.status = TaskStatus.FAILED
            task.result = f"Ops task failed. Command '{e.cmd}' returned non-zero exit code {e.returncode}. Output: {e.stdout.decode()}"
            await self.websocket_manager.broadcast_message({
                "type": "task_status_update",
                "task_id": task.id,
                "status": task.status.value,
                "message": task.result,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"An unexpected error occurred in Ops Agent: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.result = f"Ops task failed due to an unexpected error: {e}"
            await self.websocket_manager.broadcast_message({
                "type": "task_status_update",
                "task_id": task.id,
                "status": task.status.value,
                "message": task.result,
                "timestamp": datetime.now().isoformat()
            })

        return task

    async def _run_git_operations(self):
        """Initializes a git repo and commits all files in the generated code root."""
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Initializing Git repository and committing code...",
            "timestamp": datetime.now().isoformat()
        })
        
        # Check if the .git directory already exists to avoid re-initializing
        if not (self.repo_path / ".git").exists():
            subprocess.run(["git", "init"], cwd=self.repo_path, check=True)

        # Copy all generated files into the repo directory
        for item in self.generated_code_root.iterdir():
            if item.name == "repo": # Don't copy the repo directory into itself
                continue
            if item.is_dir():
                shutil.copytree(item, self.repo_path / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, self.repo_path / item.name)

        subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit of generated code"], cwd=self.repo_path, check=True)
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Code committed to local Git repository.",
            "timestamp": datetime.now().isoformat()
        })
        
    async def _generate_docker_artifacts(self):
        """Generates a basic Dockerfile and requirements.txt."""
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Generating Dockerfile and requirements.txt...",
            "timestamp": datetime.now().isoformat()
        })
        
        # A simple, generic Dockerfile for a FastAPI application
        dockerfile_content = """
# Use a slim Python image for a smaller footprint
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 7860

# Command to run the application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
"""
        # A simple requirements.txt assuming a FastAPI and Uvicorn app
        requirements_content = """
fastapi
uvicorn
"""
        (self.repo_path / "Dockerfile").write_text(dockerfile_content)
        (self.repo_path / "requirements.txt").write_text(requirements_content)
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Dockerfile and requirements.txt created.",
            "timestamp": datetime.now().isoformat()
        })

    async def _build_docker_image(self):
        """Builds a Docker image from the generated Dockerfile."""
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Building Docker image 'ai-dev-agent-app'...",
            "timestamp": datetime.now().isoformat()
        })
        
        # Build the Docker image from the repo_path
        subprocess.run(["docker", "build", "-t", "ai-dev-agent-app", "."], cwd=self.repo_path, check=True)
        
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Docker image 'ai-dev-agent-app' built successfully.",
            "timestamp": datetime.now().isoformat()
        })

    async def _simulate_deployment(self):
        """Simulates a CI/CD pipeline and deployment."""
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Initiating a simulated CI/CD pipeline...",
            "timestamp": datetime.now().isoformat()
        })
        
        # Placeholder for actual deployment logic (e.g., calling a cloud API)
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Pushing image to a container registry...",
            "timestamp": datetime.now().isoformat()
        })
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Triggering deployment to a production environment...",
            "timestamp": datetime.now().isoformat()
        })
        await self.websocket_manager.broadcast_message({
            "type": "agent_output",
            "agent_type": "ops",
            "content": "Ops Agent: Deployment simulation complete.",
            "timestamp": datetime.now().isoformat()
        })

