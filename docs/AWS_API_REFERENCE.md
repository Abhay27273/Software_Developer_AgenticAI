# AWS API Reference

## Overview

This document provides comprehensive API reference documentation for the AI-powered Software Development Agentic System deployed on AWS. The API follows REST principles and returns JSON responses.

## Base URL

```
https://{api-id}.execute-api.us-east-1.amazonaws.com/prod
```

Replace `{api-id}` with your actual API Gateway ID from the deployment.

## Authentication

### API Key Authentication

All API endpoints (except `/health`) require an API key for authentication.

**Header**:
```
x-api-key: your-api-key-here
```

**Getting an API Key**:
1. Go to AWS Console → API Gateway
2. Select your API → API Keys
3. Create API Key
4. Associate with Usage Plan

**Example Request**:
```bash
curl -X GET https://your-api-endpoint.com/api/projects \
  -H "x-api-key: your-api-key-here"
```

### Rate Limits

- **Rate**: 100 requests per second per API key
- **Burst**: 200 concurrent requests
- **Quota**: 100,000 requests per month

**Rate Limit Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1700000000
```

## Common Response Formats

### Success Response

```json
{
  "success": true,
  "data": {
    // Response data
  },
  "timestamp": "2025-11-25T12:00:00Z",
  "request_id": "abc-123-def"
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      // Additional error details
    }
  },
  "timestamp": "2025-11-25T12:00:00Z",
  "request_id": "abc-123-def"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

## API Endpoints

### Health Check

Check API health status.

**Endpoint**: `GET /health`

**Authentication**: None required

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-25T12:00:00Z",
  "version": "1.0.0",
  "services": {
    "dynamodb": "healthy",
    "sqs": "healthy",
    "s3": "healthy"
  }
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/health
```

---

### Projects

#### Create Project

Create a new project from scratch or from a template.

**Endpoint**: `POST /api/projects`

**Authentication**: Required

**Request Body**:
```json
{
  "name": "My API Project",
  "type": "api",
  "description": "REST API for todo management",
  "template_id": "rest-api-fastapi",  // Optional
  "variables": {  // Required if using template
    "project_name": "todo-api",
    "db_name": "todos"
  },
  "dependencies": ["fastapi", "sqlalchemy"],  // Optional
  "environment_vars": {  // Optional
    "DATABASE_URL": "postgresql://localhost/todos"
  }
}
```

**Parameters**:
- `name` (string, required): Project name
- `type` (string, required): Project type - `api`, `web`, `mobile`, `data`, `microservice`
- `description` (string, optional): Project description
- `template_id` (string, optional): Template ID to use
- `variables` (object, optional): Template variables
- `dependencies` (array, optional): List of dependencies
- `environment_vars` (object, optional): Environment variables

**Response**: `201 Created`
```json
{
  "success": true,
  "project": {
    "id": "proj_20251125_120000",
    "name": "My API Project",
    "type": "api",
    "status": "active",
    "description": "REST API for todo management",
    "owner_id": "user_123",
    "files": {
      "main.py": "from fastapi import FastAPI...",
      "requirements.txt": "fastapi==0.104.1\n..."
    },
    "dependencies": ["fastapi", "sqlalchemy"],
    "created_at": "2025-11-25T12:00:00Z",
    "updated_at": "2025-11-25T12:00:00Z"
  }
}
```

**Example**:
```bash
curl -X POST https://your-api-endpoint.com/api/projects \
  -H "x-api-key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Todo API",
    "type": "api",
    "description": "Simple todo management API",
    "template_id": "rest-api-fastapi",
    "variables": {
      "project_name": "todo-api",
      "db_name": "todos"
    }
  }'
```

**Python Example**:
```python
import requests

url = "https://your-api-endpoint.com/api/projects"
headers = {
    "x-api-key": "your-api-key",
    "Content-Type": "application/json"
}
data = {
    "name": "Todo API",
    "type": "api",
    "template_id": "rest-api-fastapi",
    "variables": {
        "project_name": "todo-api",
        "db_name": "todos"
    }
}

response = requests.post(url, headers=headers, json=data)
project = response.json()["project"]
print(f"Created project: {project['id']}")
```

---

#### List Projects

Get a list of all projects.

**Endpoint**: `GET /api/projects`

**Authentication**: Required

**Query Parameters**:
- `status` (string, optional): Filter by status - `active`, `archived`, `deleted`
- `type` (string, optional): Filter by type - `api`, `web`, `mobile`, `data`, `microservice`
- `limit` (integer, optional): Number of results (default: 50, max: 100)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response**: `200 OK`
```json
{
  "success": true,
  "projects": [
    {
      "id": "proj_20251125_120000",
      "name": "My API Project",
      "type": "api",
      "status": "active",
      "description": "REST API for todo management",
      "created_at": "2025-11-25T12:00:00Z",
      "updated_at": "2025-11-25T12:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/projects?status=active&limit=10 \
  -H "x-api-key: your-api-key"
```

---

#### Get Project

Get details of a specific project.

**Endpoint**: `GET /api/projects/{project_id}`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Response**: `200 OK`
```json
{
  "success": true,
  "project": {
    "id": "proj_20251125_120000",
    "name": "My API Project",
    "type": "api",
    "status": "active",
    "description": "REST API for todo management",
    "owner_id": "user_123",
    "files": {
      "main.py": "from fastapi import FastAPI...",
      "requirements.txt": "fastapi==0.104.1\n...",
      "README.md": "# My API Project\n..."
    },
    "dependencies": ["fastapi", "sqlalchemy"],
    "environment_vars": {
      "DATABASE_URL": "***"
    },
    "test_coverage": 0.85,
    "security_score": 0.92,
    "performance_score": 0.88,
    "created_at": "2025-11-25T12:00:00Z",
    "updated_at": "2025-11-25T12:00:00Z"
  }
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/projects/proj_20251125_120000 \
  -H "x-api-key: your-api-key"
```

---

#### Update Project

Update project details.

**Endpoint**: `PUT /api/projects/{project_id}`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Request Body**:
```json
{
  "name": "Updated Project Name",
  "description": "Updated description",
  "status": "active",
  "environment_vars": {
    "NEW_VAR": "value"
  }
}
```

**Response**: `200 OK`
```json
{
  "success": true,
  "project": {
    "id": "proj_20251125_120000",
    "name": "Updated Project Name",
    // ... other fields
    "updated_at": "2025-11-25T13:00:00Z"
  }
}
```

**Example**:
```bash
curl -X PUT https://your-api-endpoint.com/api/projects/proj_20251125_120000 \
  -H "x-api-key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Todo API",
    "description": "Enhanced todo management API"
  }'
```

---

#### Delete Project

Delete a project (soft delete - marks as deleted).

**Endpoint**: `DELETE /api/projects/{project_id}`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Response**: `200 OK`
```json
{
  "success": true,
  "message": "Project deleted successfully",
  "project_id": "proj_20251125_120000"
}
```

**Example**:
```bash
curl -X DELETE https://your-api-endpoint.com/api/projects/proj_20251125_120000 \
  -H "x-api-key: your-api-key"
```

---


#### Request Modification

Request a modification to an existing project.

**Endpoint**: `POST /api/projects/{project_id}/modify`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Request Body**:
```json
{
  "request": "Add user authentication with JWT tokens",
  "priority": "high",
  "context": {
    "requirements": ["Secure endpoints", "Token expiration"],
    "constraints": ["Use existing database"]
  }
}
```

**Parameters**:
- `request` (string, required): Modification request description
- `priority` (string, optional): Priority level - `low`, `medium`, `high` (default: `medium`)
- `context` (object, optional): Additional context for the modification

**Response**: `202 Accepted`
```json
{
  "success": true,
  "modification": {
    "id": "mod_20251125_120500",
    "project_id": "proj_20251125_120000",
    "request": "Add user authentication with JWT tokens",
    "status": "pending",
    "priority": "high",
    "requested_by": "user_123",
    "requested_at": "2025-11-25T12:05:00Z",
    "estimated_completion": "2025-11-25T14:05:00Z"
  },
  "message": "Modification request queued for processing"
}
```

**Example**:
```bash
curl -X POST https://your-api-endpoint.com/api/projects/proj_20251125_120000/modify \
  -H "x-api-key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Add user authentication with JWT",
    "priority": "high"
  }'
```

**Python Example**:
```python
import requests
import time

# Request modification
url = f"https://your-api-endpoint.com/api/projects/{project_id}/modify"
headers = {"x-api-key": "your-api-key", "Content-Type": "application/json"}
data = {
    "request": "Add user authentication with JWT",
    "priority": "high"
}

response = requests.post(url, headers=headers, json=data)
modification_id = response.json()["modification"]["id"]

# Poll for completion
while True:
    status_url = f"https://your-api-endpoint.com/api/modifications/{modification_id}"
    status_response = requests.get(status_url, headers=headers)
    status = status_response.json()["modification"]["status"]
    
    if status == "completed":
        print("Modification completed!")
        break
    elif status == "failed":
        print("Modification failed!")
        break
    
    time.sleep(5)
```

---

#### Get Project Files

Get all files for a project.

**Endpoint**: `GET /api/projects/{project_id}/files`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Query Parameters**:
- `path` (string, optional): Filter by file path pattern

**Response**: `200 OK`
```json
{
  "success": true,
  "files": [
    {
      "path": "main.py",
      "content": "from fastapi import FastAPI...",
      "size": 1024,
      "last_modified": "2025-11-25T12:00:00Z"
    },
    {
      "path": "requirements.txt",
      "content": "fastapi==0.104.1\n...",
      "size": 256,
      "last_modified": "2025-11-25T12:00:00Z"
    }
  ],
  "total": 2
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/projects/proj_20251125_120000/files \
  -H "x-api-key: your-api-key"
```

---

#### Download Project

Get a download URL for the entire project as a ZIP file.

**Endpoint**: `GET /api/projects/{project_id}/download`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Response**: `200 OK`
```json
{
  "success": true,
  "download_url": "https://agenticai-generated-code.s3.amazonaws.com/projects/proj_20251125_120000.zip?X-Amz-...",
  "expires_at": "2025-11-25T13:00:00Z"
}
```

**Example**:
```bash
# Get download URL
curl https://your-api-endpoint.com/api/projects/proj_20251125_120000/download \
  -H "x-api-key: your-api-key"

# Download the file
curl -o project.zip "https://agenticai-generated-code.s3.amazonaws.com/..."
```

---

### Templates

#### List Templates

Get a list of available project templates.

**Endpoint**: `GET /api/templates`

**Authentication**: Required

**Query Parameters**:
- `category` (string, optional): Filter by category - `api`, `web`, `mobile`, `data`, `microservice`
- `complexity` (string, optional): Filter by complexity - `simple`, `medium`, `complex`
- `limit` (integer, optional): Number of results (default: 50)

**Response**: `200 OK`
```json
{
  "success": true,
  "templates": [
    {
      "id": "rest-api-fastapi",
      "name": "REST API with FastAPI",
      "description": "Production-ready REST API with FastAPI and PostgreSQL",
      "category": "api",
      "complexity": "medium",
      "tech_stack": ["FastAPI", "PostgreSQL", "SQLAlchemy"],
      "required_vars": ["project_name", "db_name"],
      "optional_vars": ["project_description", "port"],
      "estimated_setup_time": 15,
      "tags": ["api", "rest", "fastapi", "postgresql"]
    },
    {
      "id": "web-app-react-fastapi",
      "name": "Full-Stack Web App",
      "description": "React frontend with FastAPI backend",
      "category": "web",
      "complexity": "complex",
      "tech_stack": ["React", "FastAPI", "PostgreSQL"],
      "required_vars": ["project_name", "app_name"],
      "optional_vars": [],
      "estimated_setup_time": 30,
      "tags": ["web", "react", "fastapi", "fullstack"]
    }
  ],
  "total": 2
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/templates?category=api \
  -H "x-api-key: your-api-key"
```

---

#### Get Template

Get details of a specific template.

**Endpoint**: `GET /api/templates/{template_id}`

**Authentication**: Required

**Path Parameters**:
- `template_id` (string, required): Template ID

**Response**: `200 OK`
```json
{
  "success": true,
  "template": {
    "id": "rest-api-fastapi",
    "name": "REST API with FastAPI",
    "description": "Production-ready REST API with FastAPI and PostgreSQL",
    "category": "api",
    "complexity": "medium",
    "tech_stack": ["FastAPI", "PostgreSQL", "SQLAlchemy"],
    "required_vars": ["project_name", "db_name"],
    "optional_vars": ["project_description", "port"],
    "files": {
      "main.py": "from fastapi import FastAPI\n\napp = FastAPI(title=\"{{project_name}}\")\n...",
      "requirements.txt": "fastapi==0.104.1\nuvicorn==0.24.0\n...",
      "README.md": "# {{project_name}}\n\n{{project_description}}\n..."
    },
    "estimated_setup_time": 15,
    "tags": ["api", "rest", "fastapi", "postgresql"],
    "created_at": "2025-11-20T10:00:00Z",
    "updated_at": "2025-11-25T10:00:00Z"
  }
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/templates/rest-api-fastapi \
  -H "x-api-key: your-api-key"
```

---

#### Create Template

Create a new project template.

**Endpoint**: `POST /api/templates`

**Authentication**: Required

**Request Body**:
```json
{
  "name": "GraphQL API with Strawberry",
  "description": "GraphQL API using Strawberry and FastAPI",
  "category": "api",
  "complexity": "medium",
  "tech_stack": ["FastAPI", "Strawberry", "PostgreSQL"],
  "required_vars": ["project_name", "db_name"],
  "optional_vars": ["project_description"],
  "files": {
    "main.py": "import strawberry\nfrom fastapi import FastAPI\n...",
    "requirements.txt": "fastapi==0.104.1\nstrawberry-graphql==0.200.0\n..."
  },
  "tags": ["api", "graphql", "strawberry"]
}
```

**Response**: `201 Created`
```json
{
  "success": true,
  "template": {
    "id": "graphql-api-strawberry",
    "name": "GraphQL API with Strawberry",
    // ... other fields
    "created_at": "2025-11-25T12:00:00Z"
  }
}
```

**Example**:
```bash
curl -X POST https://your-api-endpoint.com/api/templates \
  -H "x-api-key: your-api-key" \
  -H "Content-Type: application/json" \
  -d @template.json
```

---

### Modifications

#### Get Modification Status

Get the status of a modification request.

**Endpoint**: `GET /api/modifications/{modification_id}`

**Authentication**: Required

**Path Parameters**:
- `modification_id` (string, required): Modification ID

**Response**: `200 OK`
```json
{
  "success": true,
  "modification": {
    "id": "mod_20251125_120500",
    "project_id": "proj_20251125_120000",
    "request": "Add user authentication with JWT tokens",
    "status": "in_progress",
    "priority": "high",
    "requested_by": "user_123",
    "requested_at": "2025-11-25T12:05:00Z",
    "started_at": "2025-11-25T12:06:00Z",
    "progress": 0.45,
    "current_step": "Implementing authentication middleware",
    "impact_analysis": {
      "risk_level": "medium",
      "affected_files": ["main.py", "auth.py", "models.py"],
      "estimated_time": "2 hours",
      "breaking_changes": false
    }
  }
}
```

**Status Values**:
- `pending`: Queued for processing
- `in_progress`: Currently being processed
- `completed`: Successfully completed
- `failed`: Failed with errors
- `cancelled`: Cancelled by user

**Example**:
```bash
curl https://your-api-endpoint.com/api/modifications/mod_20251125_120500 \
  -H "x-api-key: your-api-key"
```

---

#### List Modifications

Get all modifications for a project.

**Endpoint**: `GET /api/projects/{project_id}/modifications`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Query Parameters**:
- `status` (string, optional): Filter by status
- `limit` (integer, optional): Number of results (default: 50)

**Response**: `200 OK`
```json
{
  "success": true,
  "modifications": [
    {
      "id": "mod_20251125_120500",
      "request": "Add user authentication with JWT tokens",
      "status": "completed",
      "requested_at": "2025-11-25T12:05:00Z",
      "completed_at": "2025-11-25T14:05:00Z"
    }
  ],
  "total": 1
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/projects/proj_20251125_120000/modifications \
  -H "x-api-key: your-api-key"
```

---

#### Cancel Modification

Cancel a pending or in-progress modification.

**Endpoint**: `DELETE /api/modifications/{modification_id}`

**Authentication**: Required

**Path Parameters**:
- `modification_id` (string, required): Modification ID

**Response**: `200 OK`
```json
{
  "success": true,
  "message": "Modification cancelled successfully",
  "modification_id": "mod_20251125_120500"
}
```

**Example**:
```bash
curl -X DELETE https://your-api-endpoint.com/api/modifications/mod_20251125_120500 \
  -H "x-api-key: your-api-key"
```

---

### Documentation

#### Get Project Documentation

Get auto-generated documentation for a project.

**Endpoint**: `GET /api/projects/{project_id}/docs`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Query Parameters**:
- `format` (string, optional): Documentation format - `markdown`, `html`, `pdf` (default: `markdown`)

**Response**: `200 OK`
```json
{
  "success": true,
  "documentation": {
    "format": "markdown",
    "content": "# My API Project\n\n## Overview\n...",
    "sections": [
      {
        "title": "Overview",
        "content": "This is a REST API for todo management..."
      },
      {
        "title": "API Endpoints",
        "content": "### GET /todos\n..."
      },
      {
        "title": "Installation",
        "content": "```bash\npip install -r requirements.txt\n```"
      }
    ],
    "generated_at": "2025-11-25T12:00:00Z"
  }
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/projects/proj_20251125_120000/docs \
  -H "x-api-key: your-api-key"
```

---

### Testing

#### Run Tests

Trigger test execution for a project.

**Endpoint**: `POST /api/projects/{project_id}/test`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Request Body**:
```json
{
  "test_type": "unit",
  "coverage": true
}
```

**Parameters**:
- `test_type` (string, optional): Test type - `unit`, `integration`, `e2e`, `all` (default: `all`)
- `coverage` (boolean, optional): Generate coverage report (default: `true`)

**Response**: `202 Accepted`
```json
{
  "success": true,
  "test_run": {
    "id": "test_20251125_120000",
    "project_id": "proj_20251125_120000",
    "test_type": "unit",
    "status": "running",
    "started_at": "2025-11-25T12:00:00Z"
  }
}
```

**Example**:
```bash
curl -X POST https://your-api-endpoint.com/api/projects/proj_20251125_120000/test \
  -H "x-api-key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"test_type": "unit", "coverage": true}'
```

---

#### Get Test Results

Get test results for a project.

**Endpoint**: `GET /api/projects/{project_id}/test-results`

**Authentication**: Required

**Path Parameters**:
- `project_id` (string, required): Project ID

**Query Parameters**:
- `test_run_id` (string, optional): Specific test run ID

**Response**: `200 OK`
```json
{
  "success": true,
  "test_results": {
    "test_run_id": "test_20251125_120000",
    "status": "completed",
    "summary": {
      "total": 45,
      "passed": 43,
      "failed": 2,
      "skipped": 0,
      "duration": 12.5
    },
    "coverage": {
      "line_coverage": 0.85,
      "branch_coverage": 0.78,
      "files": [
        {
          "path": "main.py",
          "coverage": 0.92
        }
      ]
    },
    "failures": [
      {
        "test": "test_user_authentication",
        "error": "AssertionError: Expected 200, got 401",
        "traceback": "..."
      }
    ],
    "completed_at": "2025-11-25T12:00:15Z"
  }
}
```

**Example**:
```bash
curl https://your-api-endpoint.com/api/projects/proj_20251125_120000/test-results \
  -H "x-api-key: your-api-key"
```

---

## WebSocket API

### Connection

Connect to receive real-time updates.

**Endpoint**: `wss://{websocket-url}/ws`

**Authentication**: Query parameter

**Connection URL**:
```
wss://your-websocket-endpoint.com/ws?api_key=your-api-key&project_id=proj_123
```

**Query Parameters**:
- `api_key` (string, required): API key for authentication
- `project_id` (string, optional): Subscribe to specific project updates

### Message Format

**Client → Server**:
```json
{
  "action": "subscribe",
  "project_id": "proj_20251125_120000"
}
```

**Server → Client**:
```json
{
  "type": "project_update",
  "project_id": "proj_20251125_120000",
  "event": "modification_started",
  "data": {
    "modification_id": "mod_20251125_120500",
    "status": "in_progress"
  },
  "timestamp": "2025-11-25T12:00:00Z"
}
```

### Event Types

- `project_created`: New project created
- `project_updated`: Project details updated
- `modification_started`: Modification processing started
- `modification_progress`: Modification progress update
- `modification_completed`: Modification completed
- `modification_failed`: Modification failed
- `test_started`: Test execution started
- `test_completed`: Test execution completed

### Example (JavaScript)

```javascript
const ws = new WebSocket('wss://your-websocket-endpoint.com/ws?api_key=your-api-key');

ws.onopen = () => {
  console.log('Connected');
  
  // Subscribe to project updates
  ws.send(JSON.stringify({
    action: 'subscribe',
    project_id: 'proj_20251125_120000'
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
  
  if (message.type === 'modification_progress') {
    console.log(`Progress: ${message.data.progress * 100}%`);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected');
};
```

### Example (Python)

```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"Received: {data}")
    
    if data['type'] == 'modification_completed':
        print("Modification completed!")
        ws.close()

def on_open(ws):
    print("Connected")
    ws.send(json.dumps({
        'action': 'subscribe',
        'project_id': 'proj_20251125_120000'
    }))

ws = websocket.WebSocketApp(
    'wss://your-websocket-endpoint.com/ws?api_key=your-api-key',
    on_message=on_message,
    on_open=on_open
)

ws.run_forever()
```

---

## Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `INVALID_REQUEST` | Request body is malformed | Check request format |
| `VALIDATION_ERROR` | Input validation failed | Check required fields |
| `RESOURCE_NOT_FOUND` | Resource doesn't exist | Verify resource ID |
| `UNAUTHORIZED` | Missing or invalid API key | Check API key |
| `RATE_LIMIT_EXCEEDED` | Too many requests | Wait and retry |
| `INTERNAL_ERROR` | Server error | Contact support |
| `SERVICE_UNAVAILABLE` | Service temporarily unavailable | Retry later |
| `TEMPLATE_NOT_FOUND` | Template doesn't exist | Check template ID |
| `PROJECT_ALREADY_EXISTS` | Project with same name exists | Use different name |
| `MODIFICATION_IN_PROGRESS` | Another modification is running | Wait for completion |
| `INSUFFICIENT_PERMISSIONS` | User lacks permissions | Check permissions |

---

## SDK Examples

### Python SDK

```python
import requests
from typing import Dict, Optional

class AgenticAIClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json'
        }
    
    def create_project(self, name: str, project_type: str, 
                      template_id: Optional[str] = None,
                      variables: Optional[Dict] = None) -> Dict:
        """Create a new project."""
        data = {
            'name': name,
            'type': project_type
        }
        if template_id:
            data['template_id'] = template_id
            data['variables'] = variables or {}
        
        response = requests.post(
            f'{self.base_url}/api/projects',
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()['project']
    
    def get_project(self, project_id: str) -> Dict:
        """Get project details."""
        response = requests.get(
            f'{self.base_url}/api/projects/{project_id}',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()['project']
    
    def request_modification(self, project_id: str, 
                           request: str, priority: str = 'medium') -> Dict:
        """Request a project modification."""
        data = {
            'request': request,
            'priority': priority
        }
        response = requests.post(
            f'{self.base_url}/api/projects/{project_id}/modify',
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()['modification']
    
    def get_modification_status(self, modification_id: str) -> Dict:
        """Get modification status."""
        response = requests.get(
            f'{self.base_url}/api/modifications/{modification_id}',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()['modification']

# Usage
client = AgenticAIClient(
    api_key='your-api-key',
    base_url='https://your-api-endpoint.com'
)

# Create project
project = client.create_project(
    name='My Todo API',
    project_type='api',
    template_id='rest-api-fastapi',
    variables={'project_name': 'todo-api', 'db_name': 'todos'}
)

print(f"Created project: {project['id']}")

# Request modification
modification = client.request_modification(
    project_id=project['id'],
    request='Add user authentication',
    priority='high'
)

print(f"Modification ID: {modification['id']}")
```

### JavaScript/TypeScript SDK

```typescript
class AgenticAIClient {
  private apiKey: string;
  private baseUrl: string;

  constructor(apiKey: string, baseUrl: string) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
  }

  private async request(method: string, path: string, body?: any) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        'x-api-key': this.apiKey,
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  async createProject(data: {
    name: string;
    type: string;
    template_id?: string;
    variables?: Record<string, any>;
  }) {
    const result = await this.request('POST', '/api/projects', data);
    return result.project;
  }

  async getProject(projectId: string) {
    const result = await this.request('GET', `/api/projects/${projectId}`);
    return result.project;
  }

  async requestModification(projectId: string, request: string, priority = 'medium') {
    const result = await this.request('POST', `/api/projects/${projectId}/modify`, {
      request,
      priority,
    });
    return result.modification;
  }

  async getModificationStatus(modificationId: string) {
    const result = await this.request('GET', `/api/modifications/${modificationId}`);
    return result.modification;
  }
}

// Usage
const client = new AgenticAIClient(
  'your-api-key',
  'https://your-api-endpoint.com'
);

// Create project
const project = await client.createProject({
  name: 'My Todo API',
  type: 'api',
  template_id: 'rest-api-fastapi',
  variables: { project_name: 'todo-api', db_name: 'todos' },
});

console.log(`Created project: ${project.id}`);
```

---

## Best Practices

### 1. Error Handling

Always handle errors gracefully:

```python
try:
    project = client.create_project(...)
except requests.HTTPError as e:
    if e.response.status_code == 429:
        # Rate limit exceeded - wait and retry
        time.sleep(60)
        project = client.create_project(...)
    elif e.response.status_code == 400:
        # Validation error - check input
        error = e.response.json()['error']
        print(f"Validation error: {error['message']}")
    else:
        # Other error
        raise
```

### 2. Polling for Status

Use exponential backoff when polling:

```python
import time

def wait_for_modification(client, modification_id, max_wait=3600):
    start_time = time.time()
    wait_time = 1
    
    while time.time() - start_time < max_wait:
        status = client.get_modification_status(modification_id)
        
        if status['status'] in ['completed', 'failed']:
            return status
        
        time.sleep(wait_time)
        wait_time = min(wait_time * 2, 60)  # Max 60 seconds
    
    raise TimeoutError("Modification timed out")
```

### 3. Use WebSockets for Real-Time Updates

Instead of polling, use WebSockets for better performance:

```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    if data['type'] == 'modification_completed':
        print("Done!")
        ws.close()

ws = websocket.WebSocketApp(
    f'wss://your-websocket-endpoint.com/ws?api_key={api_key}',
    on_message=on_message
)
ws.run_forever()
```

### 4. Batch Operations

When creating multiple projects, use batch operations:

```python
projects = []
for config in project_configs:
    project = client.create_project(**config)
    projects.append(project)
    time.sleep(0.1)  # Avoid rate limits
```

### 5. Caching

Cache frequently accessed data:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_template(template_id):
    return client.get_template(template_id)
```

---

## Rate Limiting

### Limits

- 100 requests per second per API key
- 200 burst capacity
- 100,000 requests per month

### Handling Rate Limits

When you receive a `429 Too Many Requests` response:

1. Check the `Retry-After` header
2. Wait the specified time
3. Retry the request

```python
import time

def make_request_with_retry(func, *args, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', 60))
                time.sleep(retry_after)
            else:
                raise
    raise Exception("Max retries exceeded")
```

---

## Support

- **Documentation**: https://docs.agenticai.com
- **API Status**: https://status.agenticai.com
- **Support Email**: support@agenticai.com
- **GitHub Issues**: https://github.com/your-org/agenticai-system/issues

---

## Changelog

### v1.0.0 (2025-11-25)
- Initial API release
- Project CRUD operations
- Template management
- Modification requests
- WebSocket support
- Documentation generation
- Test execution
