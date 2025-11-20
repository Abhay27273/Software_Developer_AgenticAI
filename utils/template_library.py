import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from models.template import ProjectTemplate

logger = logging.getLogger(__name__)


class TemplateLibrary:
    """
    Manages storage and retrieval of project templates.
    
    This implementation uses file-based storage with JSON files, providing a lightweight
    solution that can be easily migrated to PostgreSQL in the future.
    
    Storage structure:
    - generated_code/templates/{template_id}/template.json
    """
    
    def __init__(self, storage_root: Optional[Path] = None):
        """
        Initialize the TemplateLibrary.
        
        Args:
            storage_root: Root directory for storing templates.
                         Defaults to generated_code/templates/
        """
        if storage_root is None:
            from config import GENERATED_CODE_ROOT
            storage_root = GENERATED_CODE_ROOT / "templates"
        
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"TemplateLibrary initialized with storage root: {self.storage_root}")
    
    def _get_template_dir(self, template_id: str) -> Path:
        """Get the directory path for a specific template."""
        return self.storage_root / template_id
    
    def _get_template_file(self, template_id: str) -> Path:
        """Get the template.json file path for a specific template."""
        return self._get_template_dir(template_id) / "template.json"
    
    def _generate_template_id(self, name: str) -> str:
        """
        Generate a unique template ID from name.
        
        Converts name to kebab-case and adds timestamp for uniqueness.
        Handles special characters by replacing them with hyphens.
        
        Args:
            name: Template name to convert to ID
            
        Returns:
            str: Generated template ID in format "name-timestamp"
        """
        # Convert name to kebab-case: replace non-alphanumeric with hyphens
        template_id = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower()).strip('-')
        
        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        return f"{template_id}-{timestamp}"
    
    async def save_template(self, template: Union[ProjectTemplate, Dict]) -> str:
        """
        Save a template to storage.
        
        Args:
            template: ProjectTemplate object or dictionary
            
        Returns:
            str: Template ID if successful, None otherwise
        """
        try:
            # Convert dict to ProjectTemplate if needed
            if isinstance(template, dict):
                # Generate ID if not present
                if 'id' not in template:
                    template['id'] = self._generate_template_id(template.get('name', 'template'))
                template_obj = ProjectTemplate.from_dict(template)
            else:
                template_obj = template
            
            # Create template directory if it doesn't exist
            template_dir = self._get_template_dir(template_obj.id)
            template_dir.mkdir(parents=True, exist_ok=True)
            
            # Serialize template to JSON
            template_data = template_obj.to_dict()
            template_file = self._get_template_file(template_obj.id)
            
            # Write to file with pretty formatting
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully saved template {template_obj.id} ({template_obj.name})")
            return template_obj.id
            
        except Exception as e:
            logger.error(f"Failed to save template: {e}", exc_info=True)
            return None
    
    async def load_template(self, template_id: str) -> Optional[ProjectTemplate]:
        """
        Load a template from storage.
        
        Args:
            template_id: The ID of the template to load
            
        Returns:
            ProjectTemplate if found, None otherwise
        """
        try:
            template_file = self._get_template_file(template_id)
            
            if not template_file.exists():
                logger.warning(f"Template file not found for template {template_id}")
                return None
            
            # Read and parse JSON
            with open(template_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # Deserialize to ProjectTemplate
            template = ProjectTemplate.from_dict(template_data)
            logger.info(f"Successfully loaded template {template_id} ({template.name})")
            return template
            
        except Exception as e:
            logger.error(f"Failed to load template {template_id}: {e}", exc_info=True)
            return None
    
    async def get_template(self, template_id: str) -> Optional[Dict]:
        """
        Get template as dictionary for backward compatibility.
        
        Args:
            template_id: Template ID
            
        Returns:
            Template as dictionary, or None if not found
        """
        try:
            template = await self.load_template(template_id)
            if template:
                return template.to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to get template {template_id}: {e}", exc_info=True)
            return None
    
    async def list_templates(self, category: Optional[str] = None) -> List[ProjectTemplate]:
        """
        List all templates, optionally filtered by category.
        
        Args:
            category: Optional category to filter by (e.g., 'api', 'web_app')
            
        Returns:
            List of ProjectTemplate objects
        """
        templates = []
        
        try:
            # Iterate through all template directories
            if not self.storage_root.exists():
                return templates
            
            for template_dir in self.storage_root.iterdir():
                if not template_dir.is_dir():
                    continue
                
                template_file = template_dir / "template.json"
                if not template_file.exists():
                    continue
                
                try:
                    # Load template
                    with open(template_file, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    
                    # Filter by category if specified
                    if category and template_data.get('category') != category:
                        continue
                    
                    template = ProjectTemplate.from_dict(template_data)
                    templates.append(template)
                    
                except Exception as e:
                    logger.warning(f"Failed to load template from {template_file}: {e}")
                    continue
            
            logger.info(f"Listed {len(templates)} templates" + 
                       (f" in category '{category}'" if category else ""))
            return templates
            
        except Exception as e:
            logger.error(f"Failed to list templates: {e}", exc_info=True)
            return templates
    
    async def apply_template(self, template: Union[ProjectTemplate, str], variables: Dict[str, str]) -> Dict[str, str]:
        """
        Apply a template by substituting variables in template files.
        
        Args:
            template: ProjectTemplate object or template_id string
            variables: Dictionary of variable names to values
            
        Returns:
            Dictionary with 'files' key mapping filenames to customized content
        """
        try:
            # Load template if ID provided
            if isinstance(template, str):
                template_obj = await self.load_template(template)
                if not template_obj:
                    raise ValueError(f"Template not found: {template}")
            else:
                template_obj = template
            
            # Validate required variables are provided
            missing_vars = [var for var in template_obj.required_vars if var not in variables]
            if missing_vars:
                raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")
            
            # Apply variables to each file
            customized_files = {}
            
            for filename, content in template_obj.files.items():
                # Substitute variables in filename
                customized_filename = self._substitute_variables(filename, variables)
                
                # Substitute variables in content
                customized_content = self._substitute_variables(content, variables)
                
                customized_files[customized_filename] = customized_content
            
            logger.info(f"Successfully applied template {template_obj.id} with {len(variables)} variables")
            
            # Return dict with 'files' key for backward compatibility
            return {"files": customized_files}
            
        except Exception as e:
            logger.error(f"Failed to apply template: {e}", exc_info=True)
            raise
    
    def _substitute_variables(self, text: str, variables: Dict[str, str]) -> str:
        """
        Substitute variables in text using {{variable_name}} syntax.
        
        Args:
            text: Text containing variable placeholders
            variables: Dictionary of variable names to values
            
        Returns:
            Text with variables substituted
        """
        result = text
        
        # Find all {{variable}} patterns
        pattern = r'\{\{(\w+)\}\}'
        
        def replace_var(match):
            var_name = match.group(1)
            if var_name in variables:
                return variables[var_name]
            else:
                # Keep the placeholder if variable not provided
                logger.warning(f"Variable '{var_name}' not provided, keeping placeholder")
                return match.group(0)
        
        result = re.sub(pattern, replace_var, result)
        return result
    
    async def delete_template(self, template_id: str) -> bool:
        """
        Delete a template from storage.
        
        Args:
            template_id: The ID of the template to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            template_file = self._get_template_file(template_id)
            
            if not template_file.exists():
                logger.warning(f"Template file not found for template {template_id}")
                return False
            
            # Delete the template file
            template_file.unlink()
            logger.info(f"Successfully deleted template {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete template {template_id}: {e}", exc_info=True)
            return False
    
    async def template_exists(self, template_id: str) -> bool:
        """
        Check if a template exists.
        
        Args:
            template_id: The ID of the template to check
            
        Returns:
            bool: True if template exists, False otherwise
        """
        template_file = self._get_template_file(template_id)
        return template_file.exists()
    
    async def get_categories(self) -> List[str]:
        """
        Get all unique template categories.
        
        Returns:
            List of category names
        """
        categories = set()
        
        try:
            templates = await self.list_templates()
            for template in templates:
                categories.add(template.category)
            
            return sorted(list(categories))
            
        except Exception as e:
            logger.error(f"Failed to get categories: {e}", exc_info=True)
            return []
