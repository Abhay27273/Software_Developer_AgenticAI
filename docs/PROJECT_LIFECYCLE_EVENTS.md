# Project Lifecycle WebSocket Events

## Overview

The system broadcasts real-time WebSocket events for project lifecycle operations, allowing connected clients to receive instant notifications when projects are created, updated, or deleted.

**Implementation**: Task 9.1  
**Requirements**: 1.1

## Event Types

### 1. project_created

Broadcast when a new project is created.

**Event Structure**:
```json
{
  "event_type": "project_created",
  "timestamp": "2023-11-19T12:00:00.000000",
  "data": {
    "project_id": "proj_20231119_120000",
    "name": "My New Project",
    "type": "api",
    "status": "created",
    "owner_id": "user_123",
    "description": "Project description"
  }
}
```

**Triggered By**: `POST /api/projects`

### 2. project_updated

Broadcast when a project is updated.

**Event Structure**:
```json
{
  "event_type": "project_updated",
  "timestamp": "2023-11-19T12:05:00.000000",
  "data": {
    "project_id": "proj_20231119_120000",
    "name": "Updated Project Name",
    "type": "api",
    "status": "in_progress",
    "updated_fields": ["name", "status"],
    "description": "Updated description"
  }
}
```

**Triggered By**: `PUT /api/projects/{project_id}`

**Note**: The `updated_fields` array indicates which fields were modified in the update.

### 3. project_deleted

Broadcast when a project is deleted.

**Event Structure**:
```json
{
  "event_type": "project_deleted",
  "timestamp": "2023-11-19T12:10:00.000000",
  "data": {
    "project_id": "proj_20231119_120000",
    "name": "Deleted Project"
  }
}
```

**Triggered By**: `DELETE /api/projects/{project_id}`

## Usage

### Backend Integration

The WebSocket manager is automatically configured when the application starts:

```python
from parse.websocket_manager import WebSocketManager
from api.routes import set_websocket_manager

# Initialize WebSocket manager
websocket_manager = WebSocketManager()

# Configure it for API routes
set_websocket_manager(websocket_manager)
```

Events are automatically broadcast when using the API endpoints:

```python
# Create project - automatically broadcasts project_created
response = await client.post("/api/projects", json={
    "name": "My Project",
    "project_type": "api"
})

# Update project - automatically broadcasts project_updated
response = await client.put("/api/projects/proj_123", json={
    "status": "in_progress"
})

# Delete project - automatically broadcasts project_deleted
response = await client.delete("/api/projects/proj_123")
```

### Frontend Integration

Connect to the WebSocket endpoint and listen for events:

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

// Listen for messages
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.event_type) {
    case 'project_created':
      console.log('New project created:', message.data);
      // Update UI to show new project
      break;
      
    case 'project_updated':
      console.log('Project updated:', message.data);
      console.log('Updated fields:', message.data.updated_fields);
      // Update UI to reflect changes
      break;
      
    case 'project_deleted':
      console.log('Project deleted:', message.data.project_id);
      // Remove project from UI
      break;
  }
};
```

## Implementation Details

### WebSocketManager Methods

Three new methods were added to the `WebSocketManager` class:

1. **broadcast_project_created(project_data)**
   - Broadcasts project creation event to all connected clients
   - Includes full project details in the event data

2. **broadcast_project_updated(project_data, updated_fields)**
   - Broadcasts project update event to all connected clients
   - Includes list of fields that were updated
   - Helps clients optimize UI updates

3. **broadcast_project_deleted(project_id, project_name)**
   - Broadcasts project deletion event to all connected clients
   - Includes minimal data (ID and name) since project is deleted

### API Routes Integration

The API routes module maintains a reference to the WebSocket manager:

```python
# Global WebSocket manager reference
websocket_manager: Optional[WebSocketManager] = None

def set_websocket_manager(manager: WebSocketManager):
    """Set the WebSocket manager for broadcasting events."""
    global websocket_manager
    websocket_manager = manager
```

Each CRUD endpoint checks if the WebSocket manager is available and broadcasts the appropriate event:

```python
# Example from create_project endpoint
if websocket_manager:
    await websocket_manager.broadcast_project_created(project.to_dict())
```

## Testing

Comprehensive tests are available in `tests/test_project_lifecycle_events.py`:

```bash
# Run tests
python -m pytest tests/test_project_lifecycle_events.py -v
```

Test coverage includes:
- Broadcasting each event type
- Multiple connected clients
- No clients connected (graceful handling)
- Minimal data scenarios
- API routes integration

## Benefits

1. **Real-time Updates**: Clients receive instant notifications without polling
2. **Efficient**: Only changed data is transmitted
3. **Scalable**: Broadcasts to all connected clients simultaneously
4. **Reliable**: Gracefully handles disconnected clients
5. **Informative**: Includes context about what changed (updated_fields)

## Future Enhancements

Additional lifecycle events planned for future tasks:
- Modification events (Task 9.2)
- Documentation generation events (Task 9.3)
- Test generation events (Task 9.4)

## Related Documentation

- [WebSocket Manager](../parse/websocket_manager.py)
- [API Routes](../api/routes.py)
- [Project Context Model](../models/project_context.py)
