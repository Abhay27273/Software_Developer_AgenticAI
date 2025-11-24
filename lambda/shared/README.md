# Shared Lambda Layer

This directory contains shared code that is packaged as a Lambda Layer and used across all Lambda functions.

## Structure

```
lambda/shared/
├── python/
│   ├── models/          # Shared data models
│   │   ├── __init__.py
│   │   ├── project.py   # ProjectContext, ProjectType, ProjectStatus
│   │   ├── task.py      # Task, TaskStatus
│   │   └── plan.py      # Plan
│   └── utils/           # Shared utilities
│       ├── __init__.py
│       ├── dynamodb_helper.py  # DynamoDB operations
│       ├── s3_helper.py        # S3 operations
│       └── response_builder.py # API response formatting
└── README.md
```

## Usage

The shared layer is automatically included in all Lambda functions via the SAM template configuration.

### Importing Models

```python
from models import ProjectContext, ProjectType, ProjectStatus
from models import Task, TaskStatus
from models import Plan

# Create a project
project = ProjectContext(
    id="proj_123",
    name="My Project",
    type=ProjectType.API,
    status=ProjectStatus.CREATED,
    owner_id="user_123"
)

# Convert to dict for DynamoDB
project_dict = project.to_dict()

# Create from dict
project = ProjectContext.from_dict(data)
```

### Using Utilities

```python
from utils import DynamoDBHelper, S3Helper, ResponseBuilder

# DynamoDB operations
db = DynamoDBHelper('agenticai-data')
item = db.get_item('PROJECT#123', 'METADATA')
db.put_item({'PK': 'PROJECT#123', 'SK': 'METADATA', ...})

# S3 operations
s3 = S3Helper('agenticai-generated-code')
s3.put_object('projects/123/main.py', code_content)
content = s3.get_object('projects/123/main.py')

# Build API responses
return ResponseBuilder.success(200, {'project': project_dict})
return ResponseBuilder.error(404, 'NOT_FOUND', 'Project not found')
```

## Deployment

The layer is deployed as part of the SAM template:

```yaml
SharedLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: agenticai-shared
    ContentUri: lambda/shared/
    CompatibleRuntimes:
      - python3.11
```

All Lambda functions reference this layer:

```yaml
ApiHandler:
  Type: AWS::Serverless::Function
  Properties:
    Layers:
      - !Ref SharedLayer
```

## Development

When developing locally, ensure the shared layer is in your Python path:

```bash
export PYTHONPATH="${PYTHONPATH}:./lambda/shared/python"
```

## Testing

Test the shared utilities:

```python
# tests/test_shared_layer.py
from models import ProjectContext, ProjectType, ProjectStatus

def test_project_context():
    project = ProjectContext(
        id="test_123",
        name="Test Project",
        type=ProjectType.API,
        status=ProjectStatus.CREATED,
        owner_id="user_123"
    )
    
    # Test serialization
    data = project.to_dict()
    assert data['id'] == "test_123"
    assert data['type'] == "api"
    
    # Test deserialization
    project2 = ProjectContext.from_dict(data)
    assert project2.id == project.id
    assert project2.name == project.name
```

## Requirements

The shared layer has minimal dependencies:
- boto3 (provided by Lambda runtime)
- botocore (provided by Lambda runtime)

No additional packages need to be installed.
