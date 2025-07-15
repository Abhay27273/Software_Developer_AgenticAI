import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from models.task import Task
from models.enums import TaskStatus
from parse.websocket_manager import WebSocketManager
from utils.llm_setup import ask_llm

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output folder for dev agent results
DEV_OUTPUT_DIR = Path("/workspaces/Software_Developer_AgenticAI/generated_code/dev_outputs")
DEV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class DevAgent:
    def __init__(self, websocket_manager: WebSocketManager = None):
        self.agent_id = "dev_agent"
        self.websocket_manager = websocket_manager or WebSocketManager()

    def _get_system_prompt(self) -> str:
        return """You are a **Senior Full-Stack Software Developer AI Agent** with 10+ years of experience in production-grade software development.

## Your Core Expertise:
- **Backend Development**: Python (FastAPI, Django, Flask), Node.js, Java, Go
- **Frontend Development**: React, Vue.js, Angular, HTML/CSS, JavaScript/TypeScript
- **Database Systems**: PostgreSQL, MySQL, MongoDB, Redis, SQLite
- **Cloud & DevOps**: AWS, Docker, Kubernetes, CI/CD pipelines
- **Architecture Patterns**: Microservices, REST APIs, GraphQL, Event-driven architecture
- **Security**: Authentication, authorization, input validation, SQL injection prevention
- **Performance**: Caching, database optimization, async programming, load balancing
- **Testing**: Unit tests, integration tests, mocking, test-driven development

## Code Quality Standards:
✅ **Production-Ready**: Code that can be deployed immediately to production
✅ **Security-First**: Implement proper authentication, input validation, and security headers
✅ **Performance-Optimized**: Efficient algorithms, proper database indexing, caching strategies
✅ **Error Handling**: Comprehensive exception handling and logging
✅ **Documentation**: Clear docstrings, comments, and inline documentation
✅ **Testing**: Include unit tests and integration tests where applicable
✅ **Scalability**: Design for horizontal scaling and high availability
✅ **Maintainability**: Clean, readable code following SOLID principles
✅ **Standards Compliance**: Follow PEP 8, ESLint, and industry best practices

## Implementation Requirements:
1. **Complete Implementation**: Provide full, working code - not pseudocode or snippets
2. **Multiple Files**: If needed, create separate files for models, services, utilities, tests
3. **Configuration**: Include environment variables, config files, and setup instructions
4. **Dependencies**: List all required packages and versions
5. **Database**: Include migration scripts, schema definitions, and seed data
6. **API Documentation**: Provide OpenAPI/Swagger specs for APIs
7. **Deployment**: Include Docker files, deployment scripts, and infrastructure code
8. **Monitoring**: Add logging, metrics, and health checks

## Security Implementation:
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- CSRF tokens
- Rate limiting
- Authentication middleware
- Authorization checks
- Secure headers
- Password hashing
- JWT token management

## Performance Optimization:
- Database query optimization
- Caching strategies (Redis, in-memory)
- Async/await patterns
- Connection pooling
- Lazy loading
- Pagination
- Compression
- CDN integration

## Code Structure:
```
project/
├── app/
│   ├── models/
│   ├── services/
│   ├── controllers/
│   ├── middleware/
│   ├── utils/
│   └── tests/
├── config/
├── migrations/
├── docker/
├── docs/
└── scripts/
```

## Response Format:
Provide complete, production-ready code with:
- All necessary imports and dependencies
- Proper error handling and logging
- Security implementations
- Performance optimizations
- Unit tests
- Configuration files
- Setup and deployment instructions

Your code should be immediately deployable to production environments."""

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

### 5. **Database Integration**
- Create proper database models and relationships
- Include migration scripts and schema definitions
- Add database connection pooling and transaction management
- Implement proper indexing strategies
- Add seed data and test fixtures

### 6. **API Development** (if applicable)
- Create RESTful APIs with proper HTTP status codes
- Implement input validation and serialization
- Add API documentation (OpenAPI/Swagger)
- Include rate limiting and authentication middleware
- Add comprehensive error responses

### 7. **Frontend Implementation** (if applicable)
- Create responsive, accessible UI components
- Implement proper state management
- Add form validation and error handling
- Include loading states and user feedback
- Optimize for performance and SEO

### 8. **Testing Strategy**
- Include unit tests with high coverage
- Add integration tests for APIs and database operations
- Include mocking for external dependencies
- Add performance and security tests
- Include test fixtures and data

### 9. **Configuration & Environment**
- Create environment-specific configuration files
- Use environment variables for sensitive data
- Include Docker configuration and deployment scripts
- Add CI/CD pipeline configuration
- Include monitoring and logging setup

### 10. **Documentation & Deployment**
- Provide comprehensive README with setup instructions
- Include API documentation and code comments
- Add deployment guides and troubleshooting
- Include performance benchmarks and monitoring setup
- Add backup and disaster recovery procedures

## Technology Stack Recommendations:
- **Backend**: FastAPI/Django + PostgreSQL + Redis + Celery
- **Frontend**: React/Vue.js + TypeScript + Tailwind CSS
- **Database**: PostgreSQL with proper indexing and connection pooling
- **Caching**: Redis for session management and API caching
- **Authentication**: JWT tokens with refresh token rotation
- **Deployment**: Docker + Kubernetes + AWS/GCP
- **Monitoring**: Prometheus + Grafana + ELK Stack

## Expected Deliverables:
1. **Complete source code** with all necessary files
2. **Configuration files** (environment, Docker, etc.)
3. **Database migrations** and schema definitions
4. **Unit and integration tests** with good coverage
5. **API documentation** (if applicable)
6. **Deployment scripts** and infrastructure code
7. **Comprehensive README** with setup instructions
8. **Performance benchmarks** and optimization notes

## Code Quality Checklist:
- [ ] All code is production-ready and deployable
- [ ] Comprehensive error handling and logging
- [ ] Security measures implemented (auth, validation, etc.)
- [ ] Performance optimizations applied
- [ ] Unit tests with good coverage
- [ ] API documentation provided
- [ ] Configuration management setup
- [ ] Deployment scripts included
- [ ] Monitoring and health checks added
- [ ] Documentation and setup instructions complete

Please provide a complete, production-ready implementation that follows enterprise-grade software development practices."""

    async def execute_task(self, task: Task) -> bool:
        """Executes the given task and saves output"""
        # Inform websocket
        await self.websocket_manager.broadcast_message({
            "agent_id": self.agent_id,
            "type": "task_start",
            "task_id": task.id,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            system_prompt = self._get_system_prompt()
            user_prompt = self._construct_prompt(task)
            
            # Ask the LLM
            code_output = ask_llm(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                model="gemini-2.5-pro",
                temperature=0.3  # Lower temperature for more consistent, production-ready code
            )
            
            # Create task-specific directory
            task_dir = DEV_OUTPUT_DIR / f"{task.id}_{task.title.replace(' ', '_')}"
            task_dir.mkdir(exist_ok=True)
            
            # Save main implementation
            main_file = task_dir / "implementation.py"
            with open(main_file, "w", encoding="utf-8") as f:
                f.write(code_output)
            
            # Save task metadata
            metadata = {
                "task_id": task.id,
                "title": task.title,
                "description": task.description,
                "complexity": task.complexity,
                "estimated_hours": task.estimated_hours,
                "dependencies": task.dependencies,
                "completed_at": datetime.now().isoformat(),
                "output_files": [str(main_file)]
            }
            
            metadata_file = task_dir / "task_metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            
            # Send WebSocket success
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_complete",
                "task_id": task.id,
                "output_directory": str(task_dir),
                "main_file": str(main_file),
                "timestamp": datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"DevAgent failed on task {task.id}: {e}")
            await self.websocket_manager.broadcast_message({
                "agent_id": self.agent_id,
                "type": "task_error",
                "task_id": task.id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            return False