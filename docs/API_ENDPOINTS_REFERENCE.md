# API Endpoints Reference Guide

## Overview
This document provides a comprehensive reference for all REST API endpoints implemented for the Production Enhancement features.

## Base URL
```
http://localhost:7860
```

## Authentication
Currently, endpoints use a simple `owner_id` parameter for user identification. Future versions will implement JWT-based authentication.

---

## Project Management Endpoints

### Create Project
**POST** `/api/projects`

Creates a new project with the specified configuration.

**Request Body:**
```json
{
  "name": "My Project",
  "description": "Project description",
  "project_type": "api",
  "owner_id": "user123"
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "project": { /* ProjectContext object */ },
  "message": "Project 'My Project' created successfully"
}
```

### List Projects
**GET** `/api/projects`

Lists all projects for a user with optional filtering.

**Query Parameters:**
- `owner_id` (string, default: "default_user") - Filter by owner
- `status` (string, optional) - Filter by status
- `limit` (integer, default: 50, max: 100) - Results per page
- `offset` (integer, default: 0) - Pagination offset

**Response:** `200 OK`
```json
{
  "success": true,
  "projects": [ /* Array of ProjectContext objects */ ],
  "pagination": {
    "total": 10,
    "limit": 50,
    "offset": 0,
    "has_more": false
  }
}
```

### Get Project
**GET** `/api/projects/{project_id}`

Retrieves complete details for a specific project.

**Response:** `200 OK`
```json
{
  "success": true,
  "project": { /* Complete ProjectContext object */ }
}
```

### Update Project
**PUT** `/api/projects/{project_id}`

Updates specified fields of an existing project.

**Request Body:**
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "status": "in_progress",
  "environment_vars": {
    "API_KEY": "new_value"
  }
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "project": { /* Updated ProjectContext */ },
  "message": "Project 'proj_123' updated successfully"
}
```

### Delete Project
**DELETE** `/api/projects/{project_id}`

Permanently deletes a project and all associated data.

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Project 'proj_123' deleted successfully"
}
```

---

## Modification Endpoints

### Request Modification
**POST** `/api/projects/{project_id}/modify`

Requests a modification to an existing project.

**Request Body:**
```json
{
  "request": "Add user authentication with JWT",
  "requested_by": "user123"
}
```

**Response:** `202 Accepted`
```json
{
  "success": true,
  "modification_plan": { /* ModificationPlan object */ },
  "message": "Modification plan generated. Please review and approve."
}
```

### List Modifications
**GET** `/api/projects/{project_id}/modifications`

Lists all modifications for a project.

**Query Parameters:**
- `status` (string, optional) - Filter by status
- `limit` (integer, default: 50)
- `offset` (integer, default: 0)

**Response:** `200 OK`
```json
{
  "success": true,
  "modifications": [ /* Array of Modification objects */ ],
  "pagination": { /* Pagination info */ }
}
```

### Get Project History
**GET** `/api/projects/{project_id}/history`

Retrieves complete project history (modifications + deployments).

**Query Parameters:**
- `limit` (integer, default: 100, max: 500)

**Response:** `200 OK`
```json
{
  "success": true,
  "project_id": "proj_123",
  "history": [ /* Array of events */ ],
  "total_events": 15
}
```

### Approve Modification
**POST** `/api/modifications/{modification_id}/approve`

Approves a modification plan for execution.

**Request Body:**
```json
{
  "approved_by": "user123"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "modification_id": "mod_123",
  "status": "approved",
  "approved_by": "user123",
  "approved_at": "2024-01-01T12:00:00Z",
  "message": "Modification approved. Ready for execution."
}
```

### Reject Modification
**POST** `/api/modifications/{modification_id}/reject`

Rejects a modification plan.

**Request Body:**
```json
{
  "reason": "Scope too large, needs to be broken down",
  "rejected_by": "user123"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "modification_id": "mod_123",
  "status": "rejected",
  "rejected_by": "user123",
  "rejected_at": "2024-01-01T12:00:00Z",
  "reason": "Scope too large, needs to be broken down",
  "message": "Modification rejected."
}
```

---

## Template Endpoints

### List Templates
**GET** `/api/templates`

Lists all available project templates.

**Query Parameters:**
- `category` (string, optional) - Filter by category
- `complexity` (string, optional) - Filter by complexity
- `limit` (integer, default: 50)
- `offset` (integer, default: 0)

**Response:** `200 OK`
```json
{
  "success": true,
  "templates": [ /* Array of ProjectTemplate objects */ ],
  "pagination": { /* Pagination info */ }
}
```

### Get Template
**GET** `/api/templates/{template_id}`

Retrieves complete template details.

**Response:** `200 OK`
```json
{
  "success": true,
  "template": { /* Complete ProjectTemplate object */ }
}
```

### Create Template
**POST** `/api/templates`

Creates a custom project template.

**Request Body:**
```json
{
  "name": "My Custom Template",
  "description": "A template for microservices",
  "category": "microservice",
  "files": {
    "main.py": "# Template content with {{variables}}",
    "README.md": "# {{project_name}}"
  },
  "required_vars": ["project_name", "author"],
  "optional_vars": ["license"],
  "tech_stack": ["FastAPI", "Docker"],
  "complexity": "medium",
  "author": "user123"
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "template": { /* Created ProjectTemplate */ },
  "message": "Template 'My Custom Template' created successfully"
}
```

### Create Project from Template
**POST** `/api/projects/from-template`

Creates a new project using a template.

**Request Body:**
```json
{
  "template_id": "tmpl_123",
  "project_name": "My New Project",
  "variables": {
    "project_name": "My New Project",
    "author": "John Doe",
    "license": "MIT"
  },
  "owner_id": "user123"
}
```

**Response:** `201 Created`
```json
{
  "success": true,
  "project": { /* Created ProjectContext */ },
  "template_used": "REST API Template",
  "message": "Project 'My New Project' created from template 'REST API Template'"
}
```

---

## Documentation Endpoints

### Get All Documentation
**GET** `/api/projects/{project_id}/docs`

Retrieves all documentation files for a project.

**Response:** `200 OK`
```json
{
  "success": true,
  "project_id": "proj_123",
  "documentation": {
    "readme": "# Project README...",
    "api": "# API Documentation...",
    "user_guide": "# User Guide...",
    "deployment": "# Deployment Guide..."
  },
  "available_docs": ["readme", "api", "user_guide", "deployment"]
}
```

### Get README
**GET** `/api/projects/{project_id}/docs/readme`

Retrieves the README documentation.

**Response:** `200 OK`
```json
{
  "success": true,
  "project_id": "proj_123",
  "content": "# Project README content...",
  "doc_type": "readme"
}
```

### Get API Documentation
**GET** `/api/projects/{project_id}/docs/api`

Retrieves the API documentation.

**Response:** `200 OK`
```json
{
  "success": true,
  "project_id": "proj_123",
  "content": "# API Documentation content...",
  "doc_type": "api"
}
```

### Get User Guide
**GET** `/api/projects/{project_id}/docs/user-guide`

Retrieves the user guide documentation.

**Response:** `200 OK`
```json
{
  "success": true,
  "project_id": "proj_123",
  "content": "# User Guide content...",
  "doc_type": "user_guide"
}
```

### Regenerate Documentation
**POST** `/api/projects/{project_id}/docs/regenerate`

Regenerates specified documentation types.

**Request Body:**
```json
{
  "doc_types": ["readme", "api", "user_guide", "deployment"]
}
```

**Response:** `202 Accepted`
```json
{
  "success": true,
  "project_id": "proj_123",
  "generated_docs": {
    "readme": true,
    "api": true,
    "user_guide": true,
    "deployment": true
  },
  "message": "Documentation regenerated for: readme, api, user_guide, deployment"
}
```

---

## Error Responses

All endpoints return consistent error responses:

### 400 Bad Request
```json
{
  "detail": "Invalid project type. Must be one of: ['api', 'web_app', ...]"
}
```

### 404 Not Found
```json
{
  "detail": "Project 'proj_123' not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error message"
}
```

---

## Data Models

### ProjectContext
```json
{
  "id": "proj_20240101_120000",
  "name": "My Project",
  "type": "api",
  "status": "created",
  "owner_id": "user123",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "last_deployed_at": null,
  "codebase": { /* filename -> content */ },
  "dependencies": [ /* Dependency objects */ ],
  "modifications": [ /* Modification objects */ ],
  "deployments": [ /* Deployment objects */ ],
  "environment_vars": { /* key -> value */ },
  "deployment_config": { /* DeploymentConfig */ },
  "test_coverage": 0.0,
  "security_score": 0.0,
  "performance_score": 0.0,
  "description": "",
  "repository_url": null
}
```

### ModificationPlan
```json
{
  "id": "mod_123",
  "project_id": "proj_123",
  "request": "Add authentication",
  "affected_files": ["auth.py", "main.py"],
  "changes": [ /* CodeChange objects */ ],
  "risk_level": "medium",
  "risk_score": 0.5,
  "estimated_hours": 4.0,
  "complexity": "medium",
  "summary": "Add JWT authentication...",
  "detailed_explanation": "...",
  "impact_description": "...",
  "recommendations": [],
  "testing_requirements": [],
  "status": "pending_approval",
  "created_at": "2024-01-01T12:00:00Z"
}
```

### ProjectTemplate
```json
{
  "id": "tmpl_123",
  "name": "REST API Template",
  "description": "FastAPI REST API with auth",
  "category": "api",
  "files": { /* filename -> template content */ },
  "required_vars": ["project_name"],
  "optional_vars": ["license"],
  "tech_stack": ["FastAPI", "PostgreSQL"],
  "estimated_setup_time": 30,
  "complexity": "medium",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z",
  "author": "system",
  "version": "1.0.0",
  "tags": []
}
```

---

## Rate Limiting

Currently not implemented. Future versions will include:
- 100 requests/hour for project operations
- 50 requests/hour for modifications
- 10 requests/hour for deployments

## Versioning

API version: v1 (implicit in current implementation)
Future versions will use explicit versioning: `/api/v1/projects`
