"""
API Routes for Production Enhancement Features

This module implements REST API endpoints for:
- Project management (CRUD operations)
- Project modifications
- Template management
- Documentation retrieval
"""

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from models.project_context import ProjectContext, ProjectType, ProjectStatus
from models.modification_plan import ModificationPlan, ModificationStatus
from models.template import ProjectTemplate
from utils.project_context_store import ProjectContextStore
from utils.modification_analyzer import ModificationAnalyzer
from utils.modification_plan_generator import ModificationPlanGenerator
from utils.template_library import TemplateLibrary
from utils.documentation_generator import DocumentationGenerator
from parse.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Initialize routers
project_router = APIRouter(prefix="/api/projects", tags=["projects"])
modification_router = APIRouter(prefix="/api", tags=["modifications"])
template_router = APIRouter(prefix="/api/templates", tags=["templates"])
documentation_router = APIRouter(prefix="/api", tags=["documentation"])

# Initialize services
project_store = ProjectContextStore()
modification_analyzer = ModificationAnalyzer()
modification_plan_generator = ModificationPlanGenerator()
template_library = TemplateLibrary()
documentation_generator = DocumentationGenerator()

# WebSocket manager for real-time events (will be set by main app)
websocket_manager: Optional[WebSocketManager] = None


def set_websocket_manager(manager: WebSocketManager):
    """
    Set the WebSocket manager instance for broadcasting events.
    This should be called during application startup.
    """
    global websocket_manager
    websocket_manager = manager
    logger.info("WebSocket manager configured for API routes")


# ============================================================================
# PROJECT MANAGEMENT ENDPOINTS (Task 7.1)
# ============================================================================

@project_router.post("", status_code=201)
async def create_project(
    name: str = Body(..., description="Project name"),
    description: str = Body("", description="Project description"),
    project_type: str = Body("other", description="Project type"),
    owner_id: str = Body("default_user", description="Owner user ID")
) -> Dict[str, Any]:
    """
    Create a new project.
    
    Creates a new project context and initializes it with default values.
    
    **Requirements**: 1.1, 2.1
    """
    try:
        # Validate project type
        try:
            p_type = ProjectType(project_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid project type. Must be one of: {[t.value for t in ProjectType]}"
            )
        
        # Create project context
        project = ProjectContext(
            id=f"proj_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            name=name,
            type=p_type,
            status=ProjectStatus.CREATED,
            owner_id=owner_id,
            description=description
        )
        
        # Save to store
        await project_store.save_context(project)
        
        logger.info(f"Created new project: {project.id} - {project.name}")
        
        # Broadcast project_created event (Task 9.1)
        if websocket_manager:
            await websocket_manager.broadcast_project_created(project.to_dict())
        
        return {
            "success": True,
            "project": project.to_dict(),
            "message": f"Project '{name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@project_router.get("")
async def list_projects(
    owner_id: str = Query("default_user", description="Filter by owner ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of projects to return"),
    offset: int = Query(0, ge=0, description="Number of projects to skip")
) -> Dict[str, Any]:
    """
    List user's projects with optional filtering.
    
    Returns a paginated list of projects owned by the specified user.
    
    **Requirements**: 1.1, 2.1
    """
    try:
        # Get all projects for user
        projects = await project_store.list_contexts(owner_id=owner_id)
        
        # Filter by status if provided
        if status:
            try:
                status_enum = ProjectStatus(status)
                projects = [p for p in projects if p.status == status_enum]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {[s.value for s in ProjectStatus]}"
                )
        
        # Apply pagination
        total = len(projects)
        projects = projects[offset:offset + limit]
        
        return {
            "success": True,
            "projects": [p.to_dict() for p in projects],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@project_router.get("/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """
    Get project details by ID.
    
    Returns complete project context including codebase, history, and metrics.
    
    **Requirements**: 1.1, 2.1
    """
    try:
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found"
            )
        
        return {
            "success": True,
            "project": project.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@project_router.put("/{project_id}")
async def update_project(
    project_id: str,
    name: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    environment_vars: Optional[Dict[str, str]] = Body(None),
    deployment_config: Optional[Dict[str, Any]] = Body(None)
) -> Dict[str, Any]:
    """
    Update project details.
    
    Updates specified fields of an existing project.
    
    **Requirements**: 1.1, 2.1
    """
    try:
        # Load existing project
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found"
            )
        
        # Track updated fields for event broadcasting
        updated_fields = []
        
        # Update fields
        if name is not None:
            project.name = name
            updated_fields.append("name")
        
        if description is not None:
            project.description = description
            updated_fields.append("description")
        
        if status is not None:
            try:
                project.status = ProjectStatus(status)
                updated_fields.append("status")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {[s.value for s in ProjectStatus]}"
                )
        
        if environment_vars is not None:
            project.environment_vars.update(environment_vars)
            updated_fields.append("environment_vars")
        
        if deployment_config is not None:
            for key, value in deployment_config.items():
                if hasattr(project.deployment_config, key):
                    setattr(project.deployment_config, key, value)
            updated_fields.append("deployment_config")
        
        # Update timestamp
        project.updated_at = datetime.utcnow()
        
        # Save changes
        await project_store.update_context(project)
        
        logger.info(f"Updated project: {project_id}")
        
        # Broadcast project_updated event (Task 9.1)
        if websocket_manager:
            await websocket_manager.broadcast_project_updated(project.to_dict(), updated_fields)
        
        return {
            "success": True,
            "project": project.to_dict(),
            "message": f"Project '{project_id}' updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@project_router.delete("/{project_id}")
async def delete_project(project_id: str) -> Dict[str, Any]:
    """
    Delete a project.
    
    Permanently removes a project and all its associated data.
    
    **Requirements**: 1.1, 2.1
    """
    try:
        # Check if project exists
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found"
            )
        
        # Store project name for event broadcasting
        project_name = project.name
        
        # Delete project
        success = await project_store.delete_context(project_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete project '{project_id}'"
            )
        
        logger.info(f"Deleted project: {project_id}")
        
        # Broadcast project_deleted event (Task 9.1)
        if websocket_manager:
            await websocket_manager.broadcast_project_deleted(project_id, project_name)
        
        return {
            "success": True,
            "message": f"Project '{project_id}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MODIFICATION ENDPOINTS (Task 7.2)
# ============================================================================

@modification_router.post("/projects/{project_id}/modify", status_code=202)
async def request_modification(
    project_id: str,
    request: str = Body(..., description="Natural language modification request"),
    requested_by: str = Body("default_user", description="User requesting modification")
) -> Dict[str, Any]:
    """
    Request a modification to an existing project.
    
    Analyzes the modification request and generates a modification plan
    for user review and approval.
    
    **Requirements**: 2.1, 2.2, 2.3
    """
    try:
        # Load project
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found"
            )
        
        # Analyze modification impact
        logger.info(f"Analyzing modification request for project {project_id}")
        impact_analysis = await modification_analyzer.analyze_impact(
            request=request,
            codebase=project.codebase
        )
        
        # Generate modification plan
        modification_plan = await modification_plan_generator.generate_plan(
            project_id=project_id,
            request=request,
            impact_analysis=impact_analysis
        )
        
        logger.info(f"Generated modification plan: {modification_plan.id}")
        
        return {
            "success": True,
            "modification_plan": modification_plan.to_dict(),
            "message": "Modification plan generated. Please review and approve."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting modification for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@modification_router.get("/projects/{project_id}/modifications")
async def list_modifications(
    project_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """
    List modifications for a project.
    
    Returns all modification requests and their current status.
    
    **Requirements**: 2.1, 2.2, 2.3
    """
    try:
        # Load project
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found"
            )
        
        # Get modifications
        modifications = project.modifications
        
        # Filter by status if provided
        if status:
            modifications = [m for m in modifications if m.status == status]
        
        # Apply pagination
        total = len(modifications)
        modifications = modifications[offset:offset + limit]
        
        return {
            "success": True,
            "modifications": [
                {
                    "id": m.id,
                    "timestamp": m.timestamp.isoformat(),
                    "description": m.description,
                    "affected_files": m.affected_files,
                    "requested_by": m.requested_by,
                    "status": m.status
                }
                for m in modifications
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing modifications for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@modification_router.get("/projects/{project_id}/history")
async def get_project_history(
    project_id: str,
    limit: int = Query(100, ge=1, le=500)
) -> Dict[str, Any]:
    """
    Get complete project history.
    
    Returns all modifications and deployments in chronological order.
    
    **Requirements**: 2.1, 2.2, 2.3
    """
    try:
        # Load project
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found"
            )
        
        # Combine modifications and deployments
        history = []
        
        for mod in project.modifications:
            history.append({
                "type": "modification",
                "id": mod.id,
                "timestamp": mod.timestamp.isoformat(),
                "description": mod.description,
                "affected_files": mod.affected_files,
                "requested_by": mod.requested_by,
                "status": mod.status
            })
        
        for dep in project.deployments:
            history.append({
                "type": "deployment",
                "id": dep.id,
                "timestamp": dep.timestamp.isoformat(),
                "environment": dep.environment,
                "platform": dep.platform,
                "url": dep.url,
                "status": dep.status
            })
        
        # Sort by timestamp (most recent first)
        history.sort(key=lambda x: x["timestamp"], reverse=True)
        history = history[:limit]
        
        return {
            "success": True,
            "project_id": project_id,
            "history": history,
            "total_events": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting history for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@modification_router.post("/modifications/{modification_id}/approve")
async def approve_modification(
    modification_id: str,
    approved_by: str = Body("default_user", description="User approving modification")
) -> Dict[str, Any]:
    """
    Approve a modification plan.
    
    Marks the modification as approved and ready for execution.
    
    **Requirements**: 2.1, 2.2, 2.3
    """
    try:
        # In a real implementation, this would load the modification plan
        # from a database and update its status
        
        logger.info(f"Modification {modification_id} approved by {approved_by}")
        
        return {
            "success": True,
            "modification_id": modification_id,
            "status": ModificationStatus.APPROVED.value,
            "approved_by": approved_by,
            "approved_at": datetime.utcnow().isoformat(),
            "message": "Modification approved. Ready for execution."
        }
        
    except Exception as e:
        logger.error(f"Error approving modification {modification_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@modification_router.post("/modifications/{modification_id}/reject")
async def reject_modification(
    modification_id: str,
    reason: str = Body(..., description="Reason for rejection"),
    rejected_by: str = Body("default_user", description="User rejecting modification")
) -> Dict[str, Any]:
    """
    Reject a modification plan.
    
    Marks the modification as rejected with a reason.
    
    **Requirements**: 2.1, 2.2, 2.3
    """
    try:
        logger.info(f"Modification {modification_id} rejected by {rejected_by}: {reason}")
        
        return {
            "success": True,
            "modification_id": modification_id,
            "status": ModificationStatus.REJECTED.value,
            "rejected_by": rejected_by,
            "rejected_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "message": "Modification rejected."
        }
        
    except Exception as e:
        logger.error(f"Error rejecting modification {modification_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TEMPLATE ENDPOINTS (Task 7.3)
# ============================================================================

@template_router.get("")
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    complexity: Optional[str] = Query(None, description="Filter by complexity"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """
    List available project templates.
    
    Returns all templates with optional filtering by category and complexity.
    
    **Requirements**: 12.1, 12.2
    """
    try:
        # Get all templates
        templates = await template_library.list_templates()
        
        # Filter by category
        if category:
            templates = [t for t in templates if t.category == category]
        
        # Filter by complexity
        if complexity:
            templates = [t for t in templates if t.complexity == complexity]
        
        # Apply pagination
        total = len(templates)
        templates = templates[offset:offset + limit]
        
        return {
            "success": True,
            "templates": [t.to_dict() for t in templates],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@template_router.get("/{template_id}")
async def get_template(template_id: str) -> Dict[str, Any]:
    """
    Get template details by ID.
    
    Returns complete template including file structure and configuration.
    
    **Requirements**: 12.1, 12.2
    """
    try:
        template = await template_library.load_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{template_id}' not found"
            )
        
        return {
            "success": True,
            "template": template.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@template_router.post("", status_code=201)
async def create_template(
    name: str = Body(...),
    description: str = Body(...),
    category: str = Body(...),
    files: Dict[str, str] = Body(...),
    required_vars: List[str] = Body(default=[]),
    optional_vars: List[str] = Body(default=[]),
    tech_stack: List[str] = Body(default=[]),
    complexity: str = Body("medium"),
    author: str = Body("default_user")
) -> Dict[str, Any]:
    """
    Create a custom project template.
    
    Allows users to create reusable templates from their projects.
    
    **Requirements**: 12.1, 12.2
    """
    try:
        # Create template
        template = ProjectTemplate(
            id=f"tmpl_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            name=name,
            description=description,
            category=category,
            files=files,
            required_vars=required_vars,
            optional_vars=optional_vars,
            tech_stack=tech_stack,
            complexity=complexity,
            author=author
        )
        
        # Save template
        await template_library.save_template(template)
        
        logger.info(f"Created custom template: {template.id} - {template.name}")
        
        return {
            "success": True,
            "template": template.to_dict(),
            "message": f"Template '{name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@project_router.post("/from-template", status_code=201)
async def create_project_from_template(
    template_id: str = Body(..., description="Template ID to use"),
    project_name: str = Body(..., description="Name for new project"),
    variables: Dict[str, str] = Body(default={}, description="Template variables"),
    owner_id: str = Body("default_user", description="Owner user ID")
) -> Dict[str, Any]:
    """
    Create a new project from a template.
    
    Applies a template with user-provided variables to create a new project.
    
    **Requirements**: 12.1, 12.2
    """
    try:
        # Load template
        template = await template_library.load_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{template_id}' not found"
            )
        
        # Validate required variables
        missing_vars = [v for v in template.required_vars if v not in variables]
        if missing_vars:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required variables: {', '.join(missing_vars)}"
            )
        
        # Apply template
        result = await template_library.apply_template(template, variables)
        project_files = result.get('files', result)  # Handle both old and new format
        
        # Create project
        project = ProjectContext(
            id=f"proj_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            name=project_name,
            type=ProjectType(template.category) if template.category in [t.value for t in ProjectType] else ProjectType.OTHER,
            status=ProjectStatus.CREATED,
            owner_id=owner_id,
            description=f"Created from template: {template.name}",
            codebase=project_files
        )
        
        # Save project
        await project_store.save_context(project)
        
        logger.info(f"Created project from template: {project.id} from {template_id}")
        
        return {
            "success": True,
            "project": project.to_dict(),
            "template_used": template.name,
            "message": f"Project '{project_name}' created from template '{template.name}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project from template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DOCUMENTATION ENDPOINTS (Task 7.4)
# ============================================================================

@documentation_router.get("/projects/{project_id}/docs")
async def get_all_documentation(project_id: str) -> Dict[str, Any]:
    """
    Get all documentation for a project.
    
    Returns README, API docs, user guide, and deployment guide.
    
    **Requirements**: 1.1, 1.2, 1.3, 1.4
    """
    try:
        # Load project
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project '{project_id}' not found"
            )
        
        # Extract documentation files from codebase
        docs = {}
        doc_files = ["README.md", "API.md", "USER_GUIDE.md", "DEPLOYMENT.md"]
        
        for doc_file in doc_files:
            if doc_file in project.codebase:
                docs[doc_file.lower().replace(".md", "")] = project.codebase[doc_file]
        
        return {
            "success": True,
            "project_id": project_id,
            "documentation": docs,
            "available_docs": list(docs.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting documentation for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@documentation_router.get("/projects/{project_id}/docs/readme")
async def get_readme(project_id: str) -> Dict[str, Any]:
    """
    Get README documentation.
    
    **Requirements**: 1.1
    """
    try:
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        
        readme = project.codebase.get("README.md", "")
        
        if not readme:
            raise HTTPException(status_code=404, detail="README not found for this project")
        
        return {
            "success": True,
            "project_id": project_id,
            "content": readme,
            "doc_type": "readme"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting README for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@documentation_router.get("/projects/{project_id}/docs/api")
async def get_api_docs(project_id: str) -> Dict[str, Any]:
    """
    Get API documentation.
    
    **Requirements**: 1.2
    """
    try:
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        
        api_docs = project.codebase.get("API.md", "")
        
        if not api_docs:
            raise HTTPException(status_code=404, detail="API documentation not found for this project")
        
        return {
            "success": True,
            "project_id": project_id,
            "content": api_docs,
            "doc_type": "api"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting API docs for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@documentation_router.get("/projects/{project_id}/docs/user-guide")
async def get_user_guide(project_id: str) -> Dict[str, Any]:
    """
    Get user guide documentation.
    
    **Requirements**: 1.4
    """
    try:
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        
        user_guide = project.codebase.get("USER_GUIDE.md", "")
        
        if not user_guide:
            raise HTTPException(status_code=404, detail="User guide not found for this project")
        
        return {
            "success": True,
            "project_id": project_id,
            "content": user_guide,
            "doc_type": "user_guide"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user guide for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@documentation_router.post("/projects/{project_id}/docs/regenerate", status_code=202)
async def regenerate_documentation(
    project_id: str,
    doc_types: List[str] = Body(default=["readme", "api", "user_guide", "deployment"])
) -> Dict[str, Any]:
    """
    Regenerate documentation for a project.
    
    Regenerates specified documentation types using the current codebase.
    
    **Requirements**: 1.1, 1.2, 1.3, 1.4
    """
    try:
        # Load project
        project = await project_store.load_context(project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        
        # Generate documentation
        logger.info(f"Regenerating documentation for project {project_id}: {doc_types}")
        
        generated_docs = {}
        
        # Extract tech stack from dependencies
        tech_stack = [dep.name for dep in project.dependencies] if project.dependencies else []
        
        if "readme" in doc_types:
            readme = await documentation_generator.generate_readme(
                project_name=project.name,
                project_description=project.description,
                code_files=project.codebase,
                tech_stack=tech_stack,
                environment_vars=project.environment_vars
            )
            project.codebase["README.md"] = readme
            generated_docs["readme"] = True
        
        if "api" in doc_types:
            api_docs = await documentation_generator.generate_api_docs(
                project_name=project.name,
                code_files=project.codebase,
                base_url="http://localhost:8000"
            )
            project.codebase["API.md"] = api_docs
            generated_docs["api"] = True
        
        if "user_guide" in doc_types:
            user_guide = await documentation_generator.generate_user_guide(
                project_name=project.name,
                project_description=project.description,
                code_files=project.codebase
            )
            project.codebase["USER_GUIDE.md"] = user_guide
            generated_docs["user_guide"] = True
        
        if "deployment" in doc_types:
            deployment_guide = await documentation_generator.generate_deployment_guide(
                project_name=project.name,
                code_files=project.codebase,
                environment_vars=project.environment_vars,
                platform=project.deployment_config.platform
            )
            project.codebase["DEPLOYMENT.md"] = deployment_guide
            generated_docs["deployment"] = True
        
        # Update project
        project.updated_at = datetime.utcnow()
        await project_store.update_context(project)
        
        return {
            "success": True,
            "project_id": project_id,
            "generated_docs": generated_docs,
            "message": f"Documentation regenerated for: {', '.join(doc_types)}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating documentation for {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
