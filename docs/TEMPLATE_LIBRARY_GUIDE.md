# Template Library User Guide

## Overview

The Template Library provides pre-built project templates that allow you to quickly bootstrap new projects with best practices and common patterns. This guide explains how to use the template system.

## Available Templates

### 1. REST API with FastAPI
- **ID**: `rest-api-fastapi`
- **Category**: api
- **Description**: Production-ready REST API with authentication, database, and tests
- **Tech Stack**: FastAPI, PostgreSQL, SQLAlchemy, Pydantic, Pytest
- **Setup Time**: ~15 minutes
- **Required Variables**:
  - `project_name` - Name of your API project
  - `db_name` - Database name
- **Optional Variables**:
  - `project_description` - Description for README

### 2. Web App (React + FastAPI)
- **ID**: `web-app-react-fastapi`
- **Category**: web_app
- **Description**: Full-stack web application with React frontend and FastAPI backend
- **Tech Stack**: React, FastAPI, Axios
- **Setup Time**: ~20 minutes
- **Required Variables**:
  - `project_name` - Name of your web app
- **Optional Variables**:
  - `project_description` - Description for README

### 3. Mobile Backend API
- **ID**: `mobile-backend-api`
- **Category**: mobile_backend
- **Description**: API optimized for mobile apps with offline sync and push notifications
- **Tech Stack**: FastAPI, JWT, Push Notifications
- **Setup Time**: ~15 minutes
- **Required Variables**:
  - `project_name` - Name of your mobile backend
- **Optional Variables**:
  - `project_description` - Description for README

### 4. Data Pipeline (ETL)
- **ID**: `data-pipeline-etl`
- **Category**: data_pipeline
- **Description**: ETL pipeline with scheduling, monitoring, and error handling
- **Tech Stack**: Python, Schedule, Pandas, SQLAlchemy
- **Setup Time**: ~20 minutes
- **Required Variables**:
  - `project_name` - Name of your pipeline
- **Optional Variables**:
  - `project_description` - Description for README

### 5. Microservice with Observability
- **ID**: `microservice-observability`
- **Category**: microservice
- **Description**: Single microservice with health checks, metrics, and logging
- **Tech Stack**: FastAPI, Prometheus, Docker, Docker Compose
- **Setup Time**: ~15 minutes
- **Required Variables**:
  - `service_name` - Name of your microservice
- **Optional Variables**:
  - `service_description` - Description for README

## Using Templates Programmatically

### Initialize Templates (First Time Setup)

```bash
python initialize_templates.py
```

This creates all 5 starter templates in the template library.

### List Available Templates

```python
from agents.pm_agent import PlannerAgent

pm_agent = PlannerAgent()

# List all templates
templates = await pm_agent.list_available_templates()

for template in templates:
    print(f"{template['name']} ({template['category']})")
    print(f"  Setup Time: {template['estimated_setup_time']} minutes")
    print(f"  Complexity: {template['complexity']}")
    print()

# List templates by category
api_templates = await pm_agent.list_available_templates(category="api")
```

### Get Template Details

```python
# Get detailed information about a template
details = await pm_agent.get_template_details("rest-api-fastapi")

print(f"Name: {details['name']}")
print(f"Description: {details['description']}")
print(f"Tech Stack: {', '.join(details['tech_stack'])}")
print(f"Files: {details['file_count']}")
print(f"Required Variables: {', '.join(details['required_vars'])}")
```

### Check Required Variables

```python
# Get required and optional variables for a template
variables = await pm_agent.prompt_for_template_variables("rest-api-fastapi")

print("Required variables:")
for var in variables['required']:
    print(f"  - {var}")

print("\nOptional variables:")
for var in variables['optional']:
    print(f"  - {var}")
```

### Create Project from Template

```python
# Create a new project from a template
project = await pm_agent.create_project_from_template(
    template_id="rest-api-fastapi",
    variables={
        "project_name": "My Todo API",
        "db_name": "tododb",
        "project_description": "A simple todo list API"
    },
    project_name="Todo API Project"
)

if project:
    print(f"Project created successfully!")
    print(f"Project ID: {project.id}")
    print(f"Files created: {len(project.codebase)}")
    
    # Access the generated files
    for filename, content in project.codebase.items():
        print(f"  - {filename}")
```

## Variable Substitution

Templates use `{{variable_name}}` syntax for customization. When you apply a template, these placeholders are replaced with your provided values.

### Example

**Template content:**
```python
app = FastAPI(title="{{project_name}}", version="1.0.0")
DATABASE_URL = "postgresql://user:pass@localhost/{{db_name}}"
```

**After applying with variables:**
```python
variables = {
    "project_name": "My API",
    "db_name": "mydb"
}
```

**Result:**
```python
app = FastAPI(title="My API", version="1.0.0")
DATABASE_URL = "postgresql://user:pass@localhost/mydb"
```

## Template Structure

Each template is stored as a JSON file with the following structure:

```json
{
  "id": "template-id",
  "name": "Template Name",
  "description": "Template description",
  "category": "api",
  "files": {
    "filename.py": "file content with {{variables}}",
    "another.py": "more content"
  },
  "required_vars": ["var1", "var2"],
  "optional_vars": ["var3"],
  "tech_stack": ["FastAPI", "PostgreSQL"],
  "estimated_setup_time": 15,
  "complexity": "medium",
  "tags": ["api", "rest"]
}
```

## Storage Location

Templates are stored in:
```
generated_code/
└── templates/
    ├── rest-api-fastapi/
    │   └── template.json
    ├── web-app-react-fastapi/
    │   └── template.json
    └── ...
```

Projects created from templates are stored in:
```
generated_code/
└── projects/
    └── {project_id}/
        ├── context.json
        └── (project files in context.json)
```

## Error Handling

### Missing Required Variables

If you don't provide all required variables, you'll get an error:

```python
# This will fail - missing 'db_name'
project = await pm_agent.create_project_from_template(
    template_id="rest-api-fastapi",
    variables={"project_name": "My API"},  # Missing db_name!
    project_name="My Project"
)
# Error: Missing required variables: db_name
```

### Template Not Found

If you specify an invalid template ID:

```python
project = await pm_agent.create_project_from_template(
    template_id="invalid-template",
    variables={},
    project_name="My Project"
)
# Returns None, logs error: Template 'invalid-template' not found
```

## Best Practices

1. **Always check required variables** before creating a project:
   ```python
   vars = await pm_agent.prompt_for_template_variables(template_id)
   # Collect all required variables from user
   ```

2. **Provide meaningful names** for projects and variables:
   ```python
   variables = {
       "project_name": "Customer Management API",  # Good
       "db_name": "customer_db"                    # Good
   }
   ```

3. **Review template details** before using:
   ```python
   details = await pm_agent.get_template_details(template_id)
   # Check tech stack, complexity, setup time
   ```

4. **Use appropriate templates** for your project type:
   - Building an API? → Use `rest-api-fastapi`
   - Building a web app? → Use `web-app-react-fastapi`
   - Building a mobile backend? → Use `mobile-backend-api`
   - Building a data pipeline? → Use `data-pipeline-etl`
   - Building a microservice? → Use `microservice-observability`

## Testing

Run the integration tests to verify template functionality:

```bash
python test_template_integration.py
```

This will test:
- Listing templates
- Filtering by category
- Getting template details
- Getting required variables
- Creating projects from templates

## Future Enhancements

Planned improvements:
- Custom user templates
- Template versioning
- Template marketplace
- Template preview in UI
- More starter templates (GraphQL, Serverless, ML, etc.)

## Support

For issues or questions about templates:
1. Check the template's README.md after creation
2. Review the tech stack documentation
3. Check the implementation summary in `generated_code/TASK_3_TEMPLATE_LIBRARY_SUMMARY.md`
