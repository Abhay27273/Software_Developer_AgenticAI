# Quick Start Usage Guide

## Your Deployed API

**Base URL**: `https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod/`

This guide shows you how to use your deployed AI-powered Software Development Agentic System.

## Table of Contents

1. [API Overview](#api-overview)
2. [Basic Usage Examples](#basic-usage-examples)
3. [Full Agent Workflow](#full-agent-workflow)
4. [Integration Examples](#integration-examples)
5. [Monitoring & Debugging](#monitoring--debugging)

## API Overview

Your system has 4 AI agents working together:

- **PM Agent**: Creates project plans and task breakdowns
- **Dev Agent**: Generates code, tests, and documentation
- **QA Agent**: Reviews code quality and runs tests
- **Ops Agent**: Handles deployment and infrastructure

### Available Endpoints

```
GET  /health                          - Health check
POST /api/projects                    - Create new project
GET  /api/projects                    - List all projects
GET  /api/projects/{id}               - Get project details
PUT  /api/projects/{id}               - Update project
POST /api/projects/{id}/tasks         - Add tasks to project
GET  /api/templates                   - List available templates
POST /api/templates                   - Create custom template
POST /api/generate                    - Generate code from template
```

## Basic Usage Examples

### 1. Health Check

```bash
curl https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod/health
```

**Response**:
```json
{
  "success": true,
  "status": "healthy",
  "timestamp": "2025-11-28T08:38:34.544188",
  "service": "api-handler"
}
```

### 2. Create a Project

```bash
curl -X POST https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My REST API",
    "type": "api",
    "description": "A FastAPI REST API with authentication",
    "requirements": {
      "framework": "fastapi",
      "database": "postgresql",
      "auth": "jwt"
    }
  }'
```

**Response**:
```json
{
  "success": true,
  "project": {
    "PK": "PROJECT#proj_20251128_083846",
    "SK": "METADATA",
    "project_id": "proj_20251128_083846",
    "name": "My REST API",
    "type": "api",
    "status": "active",
    "created_at": "2025-11-28T08:38:46.659795",
    "owner": "default_user"
  }
}
```

### 3. List All Projects

```bash
curl https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod/api/projects
```

**Response**:
```json
{
  "success": true,
  "projects": [
    {
      "project_id": "proj_20251128_083846",
      "name": "My REST API",
      "type": "api",
      "status": "active",
      "created_at": "2025-11-28T08:38:46.659795"
    }
  ],
  "count": 1
}
```

### 4. Get Project Details

```bash
curl https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod/api/projects/proj_20251128_083846
```

### 5. List Available Templates

```bash
curl https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod/api/templates
```

**Response**:
```json
{
  "success": true,
  "templates": [
    {
      "id": "rest-api-fastapi",
      "name": "REST API (FastAPI)",
      "description": "Production-ready REST API with FastAPI",
      "category": "api"
    },
    {
      "id": "web-app-react-fastapi",
      "name": "Full-Stack Web App",
      "description": "React frontend + FastAPI backend",
      "category": "fullstack"
    }
  ]
}
```

## Full Agent Workflow

Let's walk through a complete example: creating a REST API project from scratch.

### Step 1: Create Project (PM Agent)

The PM Agent analyzes your requirements and creates a project plan.

```bash
# Save your API endpoint
export API_ENDPOINT="https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod"

# Create project
curl -X POST $API_ENDPOINT/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Task Management API",
    "type": "api",
    "description": "REST API for task management with user authentication",
    "requirements": {
      "framework": "fastapi",
      "database": "postgresql",
      "auth": "jwt",
      "features": ["CRUD operations", "user management", "task assignment"]
    }
  }' | jq '.'

# Save the project_id from the response
export PROJECT_ID="proj_XXXXXXXXXX"
```

### Step 2: Generate Code (Dev Agent)

The Dev Agent generates the code based on the project plan.

```bash
# Generate code from template
curl -X POST $API_ENDPOINT/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "'$PROJECT_ID'",
    "template_id": "rest-api-fastapi",
    "parameters": {
      "project_name": "task-management-api",
      "database": "postgresql",
      "auth_type": "jwt",
      "include_tests": true,
      "include_docker": true
    }
  }' | jq '.'
```

**Response includes**:
- Generated code files
- Project structure
- Configuration files
- Tests
- Documentation

### Step 3: Review Code (QA Agent)

The QA Agent automatically reviews the generated code.

```bash
# Get project status (includes QA review)
curl $API_ENDPOINT/api/projects/$PROJECT_ID | jq '.project.qa_review'
```

### Step 4: Deploy (Ops Agent)

The Ops Agent can help with deployment configurations.

```bash
# Get deployment configuration
curl $API_ENDPOINT/api/projects/$PROJECT_ID/deployment | jq '.'
```

## Integration Examples

### Python Integration

```python
import requests

API_ENDPOINT = "https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod"

class AgenticAIClient:
    def __init__(self, api_endpoint):
        self.api_endpoint = api_endpoint
    
    def create_project(self, name, project_type, description, requirements=None):
        """Create a new project"""
        response = requests.post(
            f"{self.api_endpoint}/api/projects",
            json={
                "name": name,
                "type": project_type,
                "description": description,
                "requirements": requirements or {}
            }
        )
        return response.json()
    
    def list_projects(self):
        """List all projects"""
        response = requests.get(f"{self.api_endpoint}/api/projects")
        return response.json()
    
    def get_project(self, project_id):
        """Get project details"""
        response = requests.get(f"{self.api_endpoint}/api/projects/{project_id}")
        return response.json()
    
    def generate_code(self, project_id, template_id, parameters):
        """Generate code for a project"""
        response = requests.post(
            f"{self.api_endpoint}/api/generate",
            json={
                "project_id": project_id,
                "template_id": template_id,
                "parameters": parameters
            }
        )
        return response.json()

# Usage
client = AgenticAIClient(API_ENDPOINT)

# Create project
project = client.create_project(
    name="My API",
    project_type="api",
    description="A REST API for my app",
    requirements={"framework": "fastapi"}
)

print(f"Created project: {project['project']['project_id']}")

# List projects
projects = client.list_projects()
print(f"Total projects: {projects['count']}")
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');

const API_ENDPOINT = 'https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod';

class AgenticAIClient {
  constructor(apiEndpoint) {
    this.apiEndpoint = apiEndpoint;
  }

  async createProject(name, type, description, requirements = {}) {
    const response = await axios.post(`${this.apiEndpoint}/api/projects`, {
      name,
      type,
      description,
      requirements
    });
    return response.data;
  }

  async listProjects() {
    const response = await axios.get(`${this.apiEndpoint}/api/projects`);
    return response.data;
  }

  async getProject(projectId) {
    const response = await axios.get(`${this.apiEndpoint}/api/projects/${projectId}`);
    return response.data;
  }

  async generateCode(projectId, templateId, parameters) {
    const response = await axios.post(`${this.apiEndpoint}/api/generate`, {
      project_id: projectId,
      template_id: templateId,
      parameters
    });
    return response.data;
  }
}

// Usage
const client = new AgenticAIClient(API_ENDPOINT);

(async () => {
  // Create project
  const project = await client.createProject(
    'My API',
    'api',
    'A REST API for my app',
    { framework: 'fastapi' }
  );
  
  console.log(`Created project: ${project.project.project_id}`);
  
  // List projects
  const projects = await client.listProjects();
  console.log(`Total projects: ${projects.count}`);
})();
```

### cURL Scripts

Save this as `test_api.sh`:

```bash
#!/bin/bash

API_ENDPOINT="https://xx4apeixl1.execute-api.us-east-1.amazonaws.com/prod"

echo "=== Testing AgenticAI API ==="

# 1. Health Check
echo -e "\n1. Health Check:"
curl -s $API_ENDPOINT/health | jq '.'

# 2. Create Project
echo -e "\n2. Creating Project:"
PROJECT_RESPONSE=$(curl -s -X POST $API_ENDPOINT/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test API Project",
    "type": "api",
    "description": "Testing the API",
    "requirements": {"framework": "fastapi"}
  }')

echo $PROJECT_RESPONSE | jq '.'
PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r '.project.project_id')

# 3. List Projects
echo -e "\n3. Listing Projects:"
curl -s $API_ENDPOINT/api/projects | jq '.'

# 4. Get Project Details
echo -e "\n4. Getting Project Details:"
curl -s $API_ENDPOINT/api/projects/$PROJECT_ID | jq '.'

# 5. List Templates
echo -e "\n5. Listing Templates:"
curl -s $API_ENDPOINT/api/templates | jq '.'

echo -e "\n=== Test Complete ==="
```

Make it executable and run:
```bash
chmod +x test_api.sh
./test_api.sh
```

## Monitoring & Debugging

### View CloudWatch Logs

```bash
# List log groups
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/agenticai

# Tail API Handler logs
aws logs tail /aws/lambda/agenticai-stack-ApiHandler-XXXXX --follow

# Tail Dev Agent logs
aws logs tail /aws/lambda/agenticai-stack-DevAgentWorker-XXXXX --follow
```

### Check DynamoDB Data

```bash
# Scan all projects
aws dynamodb scan --table-name agenticai-data \
  --filter-expression "begins_with(PK, :pk)" \
  --expression-attribute-values '{":pk":{"S":"PROJECT#"}}' \
  | jq '.Items'

# Get specific project
aws dynamodb get-item --table-name agenticai-data \
  --key '{"PK":{"S":"PROJECT#proj_20251128_083846"},"SK":{"S":"METADATA"}}' \
  | jq '.Item'
```

### Check SQS Queues

```bash
# Get queue URLs
aws sqs list-queues --queue-name-prefix agenticai

# Check queue depth
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name agenticai-dev-queue --query 'QueueUrl' --output text) \
  --attribute-names ApproximateNumberOfMessages \
  | jq '.Attributes.ApproximateNumberOfMessages'
```

### Monitor API Gateway

```bash
# Get API Gateway metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=agenticai-stack \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## Common Use Cases

### 1. Generate a Microservice

```bash
curl -X POST $API_ENDPOINT/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "User Service",
    "type": "microservice",
    "description": "User management microservice",
    "requirements": {
      "framework": "fastapi",
      "database": "postgresql",
      "auth": "jwt",
      "features": ["user CRUD", "authentication", "authorization"]
    }
  }'
```

### 2. Generate a Data Pipeline

```bash
curl -X POST $API_ENDPOINT/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ETL Pipeline",
    "type": "data-pipeline",
    "description": "Extract, transform, load data pipeline",
    "requirements": {
      "source": "s3",
      "destination": "redshift",
      "transformation": "pandas",
      "schedule": "daily"
    }
  }'
```

### 3. Generate a Full-Stack App

```bash
curl -X POST $API_ENDPOINT/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Task Manager App",
    "type": "fullstack",
    "description": "Full-stack task management application",
    "requirements": {
      "frontend": "react",
      "backend": "fastapi",
      "database": "postgresql",
      "auth": "jwt",
      "deployment": "docker"
    }
  }'
```

## Next Steps

1. **Explore the API**: Try different project types and templates
2. **Integrate with your apps**: Use the Python or JavaScript client examples
3. **Monitor usage**: Check CloudWatch logs and metrics
4. **Review documentation**: See `AWS_API_REFERENCE.md` for complete API docs
5. **Set up automation**: Create scripts to automate your workflows

## Troubleshooting

### Issue: API returns 500 error

**Check Lambda logs**:
```bash
aws logs tail /aws/lambda/agenticai-stack-ApiHandler-XXXXX --since 10m
```

### Issue: Project creation is slow

**Check SQS queue depth** - agents might be processing other tasks:
```bash
aws sqs get-queue-attributes \
  --queue-url YOUR_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages
```

### Issue: Generated code not appearing

**Check S3 bucket**:
```bash
aws s3 ls s3://agenticai-generated-code/ --recursive
```

## Support

- **Documentation**: See `docs/` folder for detailed guides
- **API Reference**: `AWS_API_REFERENCE.md`
- **Operations**: `AWS_OPERATIONS_RUNBOOK.md`
- **Issues**: Report bugs in the GitHub repository

---

**Your API is ready to use!** Start building amazing software with AI agents. 🚀
