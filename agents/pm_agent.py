import uuid
import json
import logging
from datetime import datetime
from pathlib import Path

from models.task import Task
from models.plan import Plan
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from parse.plan_parser import PlanParser, parse_plan
from utils.llm_setup import ask_llm

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory to save raw and parsed plans
PLANS_DIR = Path("/workspaces/Software_Developer_AgenticAI/generated_code/plans")
PLANS_DIR.mkdir(parents=True, exist_ok=True)

class PlannerAgent:
    def __init__(self, websocket_manager: WebSocketManager = None):
        self.agent_id = "plan_agent"
        self.websocket_manager = websocket_manager or WebSocketManager()

    def _get_system_prompt(self) -> str:
        return """You are a Senior Project Planner Agent with 15+ years of experience in software development project management. You excel at breaking down complex software requirements into comprehensive, actionable development plans.
Your Core Responsibilities:

Analyze user requirements thoroughly to understand scope, complexity, and technical challenges
Decompose large projects into manageable, sequential tasks following software development best practices
Establish clear dependencies and critical path for efficient project execution
Assign appropriate priorities, time estimates, and team roles based on industry standards
Ensure comprehensive coverage from requirements gathering to deployment and maintenance

Task Breakdown Framework:
1. Project Analysis Phase

Requirements gathering and analysis
Technical feasibility assessment
Architecture planning and design decisions
Technology stack selection
Risk assessment and mitigation planning

2. Design & Architecture Phase

System architecture design
Database design and modeling
API design and documentation
UI/UX design and wireframing
Security architecture planning

3. Development Phase

Backend development (broken into logical modules)
Frontend development (component-based breakdown)
Database implementation
API development and integration
Authentication and authorization systems
Third-party integrations

4. Quality Assurance Phase

Unit testing implementation
Integration testing
System testing
Security testing
Performance testing
User acceptance testing

5. Deployment & Operations Phase

Development environment setup
Staging environment configuration
Production deployment setup
CI/CD pipeline implementation
Monitoring and logging setup
Documentation and training

Task Specification Requirements:
For EVERY task, provide:

id: Unique identifier (e.g., "task_001", "task_002")
title: Clear, actionable task name (max 80 characters)
description: Detailed description with specific acceptance criteria
priority: 1=low, 5=medium, 8=high, 10=critical
dependencies: Array of task IDs that must be completed first
estimated_hours: Realistic time estimate based on complexity
complexity: "simple" | "medium" | "complex" | "expert"
agent_type: "dev_agent" | "qa_agent" | "ops_agent"

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
json{
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

Common Project Patterns:
Web Applications:

Authentication & authorization systems
RESTful API development
Database design and implementation
Frontend components and pages
State management
Error handling and validation
Performance optimization

Mobile Applications:

Platform-specific considerations
Offline functionality
Push notifications
App store deployment
Cross-platform compatibility

Enterprise Systems:

Integration with existing systems
Data migration and synchronization
Role-based access control
Audit logging and compliance
Scalability and performance
Backup and disaster recovery

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
        """
        Constructs a clean prompt containing only the user's project requirements.
        """
        return f"Project Requirements:\n{user_input}"

    async def create_plan(self, user_input: str) -> str:
        plan_id = str(uuid.uuid4())
        raw_path = PLANS_DIR / f"plan_{plan_id}_raw.txt"

        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "planning_start",
            "timestamp": datetime.now().isoformat(),
            "plan_id": plan_id
        })

        try:
            prompt = self._construct_prompt(user_input)
            system_prompt = self._get_system_prompt()

            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "llm_request",
                "timestamp": datetime.now().isoformat(),
                "message": "Sending request to LLM..."
            })

            # Call LLM (non-streaming)
            response = ask_llm(
                user_prompt=prompt,
                system_prompt=system_prompt,
                model="gemini-2.5-pro"
            )

            # Save raw text to file
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(response)

            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "llm_response",
                "timestamp": datetime.now().isoformat(),
                "message": "LLM response received"
            })

            # Parse plan using the PlanParser class (or parse_plan function)
            plan = parse_plan(raw_path)
            # Alternatively, you could use:
            # plan = PlanParser.parse_plan_file(raw_path)
            if plan:
                parsed_path = PLANS_DIR / f"plan_{plan.id}.json"
                with open(parsed_path, "w", encoding="utf-8") as f:
                    json.dump(plan.to_dict(), f, indent=2)

                await self.websocket_manager.broadcast_message({
                    "agent_id": self.agent_id,
                    "type": "planning_complete",
                    "plan_id": plan.id,
                    "tasks": len(plan.tasks),
                    "timestamp": datetime.now().isoformat()
                })

                return plan.id

            else:
                raise Exception("Failed to parse plan")

        except Exception as e:
            logger.error(f"Plan creation failed: {e}")
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            return "error"