import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from models.project_context import ProjectContext, ProjectType, ProjectStatus

logger = logging.getLogger(__name__)


class ProjectContextStore:
    """
    Manages persistence of ProjectContext using file-based storage with JSONB-like structure.
    
    This implementation uses JSON files for storage, providing a lightweight solution
    that can be easily migrated to PostgreSQL with JSONB columns in the future.
    
    Storage structure:
    - generated_code/projects/{project_id}/context.json
    """
    
    def __init__(self, storage_root: Optional[Path] = None):
        """
        Initialize the ProjectContextStore.
        
        Args:
            storage_root: Root directory for storing project contexts.
                         Defaults to generated_code/projects/
        """
        if storage_root is None:
            from config import PROJECTS_ROOT
            storage_root = PROJECTS_ROOT
        
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"ProjectContextStore initialized with storage root: {self.storage_root}")
    
    def _get_project_dir(self, project_id: str) -> Path:
        """Get the directory path for a specific project."""
        return self.storage_root / project_id
    
    def _get_context_file(self, project_id: str) -> Path:
        """Get the context.json file path for a specific project."""
        return self._get_project_dir(project_id) / "context.json"
    
    async def save_context(self, context: ProjectContext) -> bool:
        """
        Save a project context to storage.
        
        Args:
            context: The ProjectContext to save
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Update the updated_at timestamp
            context.updated_at = datetime.utcnow()
            
            # Create project directory if it doesn't exist
            project_dir = self._get_project_dir(context.id)
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # Serialize context to JSON
            context_data = context.to_dict()
            context_file = self._get_context_file(context.id)
            
            # Write to file with pretty formatting
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(context_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully saved context for project {context.id} ({context.name})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save context for project {context.id}: {e}", exc_info=True)
            return False
    
    async def load_context(self, project_id: str) -> Optional[ProjectContext]:
        """
        Load a project context from storage.
        
        Args:
            project_id: The ID of the project to load
            
        Returns:
            ProjectContext if found, None otherwise
        """
        try:
            context_file = self._get_context_file(project_id)
            
            if not context_file.exists():
                logger.warning(f"Context file not found for project {project_id}")
                return None
            
            # Read and parse JSON
            with open(context_file, 'r', encoding='utf-8') as f:
                context_data = json.load(f)
            
            # Deserialize to ProjectContext
            context = ProjectContext.from_dict(context_data)
            logger.info(f"Successfully loaded context for project {project_id} ({context.name})")
            return context
            
        except Exception as e:
            logger.error(f"Failed to load context for project {project_id}: {e}", exc_info=True)
            return None
    
    async def update_context(self, context_or_id, context=None) -> bool:
        """
        Update a project context.
        
        Supports two call signatures for backward compatibility:
        - update_context(context: ProjectContext)
        - update_context(project_id: str, context: ProjectContext)
        
        Args:
            context_or_id: Either a ProjectContext object or a project_id string
            context: The ProjectContext object (if first arg is project_id)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Handle both signatures
            if context is None:
                # Called as update_context(context)
                ctx = context_or_id
            else:
                # Called as update_context(project_id, context)
                ctx = context
            
            # Simply save the updated context
            return await self.save_context(ctx)
            
        except Exception as e:
            logger.error(f"Failed to update context: {e}", exc_info=True)
            return False
    
    async def update_context_fields(self, project_id: str, updates: Dict) -> bool:
        """
        Update specific fields of a project context.
        
        Args:
            project_id: The ID of the project to update
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Load existing context
            context = await self.load_context(project_id)
            if context is None:
                logger.error(f"Cannot update non-existent project {project_id}")
                return False
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(context, key):
                    # Handle special cases for complex types
                    if key == 'type' and isinstance(value, str):
                        setattr(context, key, ProjectType(value))
                    elif key == 'status' and isinstance(value, str):
                        setattr(context, key, ProjectStatus(value))
                    else:
                        setattr(context, key, value)
                else:
                    logger.warning(f"Ignoring unknown field '{key}' in update")
            
            # Save updated context
            return await self.save_context(context)
            
        except Exception as e:
            logger.error(f"Failed to update context for project {project_id}: {e}", exc_info=True)
            return False
    
    async def list_contexts(self, owner_id: Optional[str] = None) -> List[ProjectContext]:
        """
        List all project contexts, optionally filtered by owner.
        
        Args:
            owner_id: Optional owner ID to filter by
            
        Returns:
            List of ProjectContext objects
        """
        contexts = []
        
        try:
            # Iterate through all project directories
            if not self.storage_root.exists():
                return contexts
            
            for project_dir in self.storage_root.iterdir():
                if not project_dir.is_dir():
                    continue
                
                context_file = project_dir / "context.json"
                if not context_file.exists():
                    continue
                
                try:
                    # Load context
                    with open(context_file, 'r', encoding='utf-8') as f:
                        context_data = json.load(f)
                    
                    # Filter by owner if specified
                    if owner_id and context_data.get('owner_id') != owner_id:
                        continue
                    
                    context = ProjectContext.from_dict(context_data)
                    contexts.append(context)
                    
                except Exception as e:
                    logger.warning(f"Failed to load context from {context_file}: {e}")
                    continue
            
            logger.info(f"Listed {len(contexts)} project contexts" + 
                       (f" for owner {owner_id}" if owner_id else ""))
            return contexts
            
        except Exception as e:
            logger.error(f"Failed to list contexts: {e}", exc_info=True)
            return contexts
    
    async def delete_context(self, project_id: str) -> bool:
        """
        Delete a project context from storage.
        
        Args:
            project_id: The ID of the project to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            context_file = self._get_context_file(project_id)
            
            if not context_file.exists():
                logger.warning(f"Context file not found for project {project_id}")
                return False
            
            # Delete the context file
            context_file.unlink()
            logger.info(f"Successfully deleted context for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete context for project {project_id}: {e}", exc_info=True)
            return False
    
    async def context_exists(self, project_id: str) -> bool:
        """
        Check if a project context exists.
        
        Args:
            project_id: The ID of the project to check
            
        Returns:
            bool: True if context exists, False otherwise
        """
        context_file = self._get_context_file(project_id)
        return context_file.exists()
    
    async def add_modification(self, project_id: str, modification: Dict) -> bool:
        """
        Add a modification record to a project's history.
        
        Args:
            project_id: The ID of the project
            modification: Dictionary containing modification details
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            context = await self.load_context(project_id)
            if context is None:
                return False
            
            from models.project_context import Modification
            mod = Modification(
                id=modification.get('id', str(datetime.utcnow().timestamp())),
                timestamp=modification.get('timestamp', datetime.utcnow()),
                description=modification['description'],
                affected_files=modification.get('affected_files', []),
                requested_by=modification.get('requested_by', 'system'),
                status=modification.get('status', 'applied')
            )
            
            context.modifications.append(mod)
            return await self.save_context(context)
            
        except Exception as e:
            logger.error(f"Failed to add modification to project {project_id}: {e}", exc_info=True)
            return False
    
    async def add_deployment(self, project_id: str, deployment: Dict) -> bool:
        """
        Add a deployment record to a project's history.
        
        Args:
            project_id: The ID of the project
            deployment: Dictionary containing deployment details
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            context = await self.load_context(project_id)
            if context is None:
                return False
            
            from models.project_context import Deployment
            dep = Deployment(
                id=deployment.get('id', str(datetime.utcnow().timestamp())),
                timestamp=deployment.get('timestamp', datetime.utcnow()),
                environment=deployment['environment'],
                platform=deployment['platform'],
                url=deployment.get('url'),
                status=deployment.get('status', 'success')
            )
            
            context.deployments.append(dep)
            context.last_deployed_at = dep.timestamp
            
            return await self.save_context(context)
            
        except Exception as e:
            logger.error(f"Failed to add deployment to project {project_id}: {e}", exc_info=True)
            return False
