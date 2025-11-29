"""
DynamoDB adapter for ProjectTemplate storage.

Implements single-table design pattern with proper PK/SK structure
for efficient querying and storage of project templates.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from models.template import ProjectTemplate

logger = logging.getLogger(__name__)


class DynamoDBTemplateStore:
    """
    DynamoDB adapter for ProjectTemplate with single-table design.
    
    Table structure:
    - PK: TEMPLATE#<template_id>
    - SK: METADATA | FILE#<file_path>
    - GSI1PK: CATEGORY#<category>
    - GSI1SK: TEMPLATE#<created_at>
    - GSI2PK: TAG#<tag>
    - GSI2SK: TEMPLATE#<template_id>
    """
    
    def __init__(self, table_name: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize DynamoDB template store.
        
        Args:
            table_name: DynamoDB table name (defaults to env var DYNAMODB_TABLE_NAME)
            region: AWS region (defaults to env var AWS_REGION or us-east-1)
        """
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE_NAME', 'agenticai-data')
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize DynamoDB client
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)
        
        logger.info(f"DynamoDBTemplateStore initialized with table: {self.table_name}")
    
    def _python_to_dynamodb(self, obj):
        """Convert Python types to DynamoDB-compatible types."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._python_to_dynamodb(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._python_to_dynamodb(item) for item in obj]
        return obj
    
    def _dynamodb_to_python(self, obj):
        """Convert DynamoDB types to Python types."""
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 else int(obj)
        elif isinstance(obj, dict):
            return {k: self._dynamodb_to_python(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._dynamodb_to_python(item) for item in obj]
        return obj
    
    def _template_to_metadata_item(self, template: ProjectTemplate) -> Dict:
        """Convert ProjectTemplate to DynamoDB metadata item."""
        item = {
            'PK': f'TEMPLATE#{template.id}',
            'SK': 'METADATA',
            'GSI1PK': f'CATEGORY#{template.category}',
            'GSI1SK': f'TEMPLATE#{template.created_at.isoformat()}',
            'EntityType': 'Template',
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'category': template.category,
            'required_vars': template.required_vars,
            'optional_vars': template.optional_vars,
            'tech_stack': template.tech_stack,
            'estimated_setup_time': template.estimated_setup_time,
            'complexity': template.complexity,
            'created_at': template.created_at.isoformat(),
            'updated_at': template.updated_at.isoformat(),
            'author': template.author,
            'version': template.version,
            'tags': template.tags
        }
        
        # Convert floats to Decimal for DynamoDB
        return self._python_to_dynamodb(item)
    
    def _template_files_to_items(self, template: ProjectTemplate) -> List[Dict]:
        """Convert template files to DynamoDB items."""
        items = []
        for file_path, content in template.files.items():
            item = {
                'PK': f'TEMPLATE#{template.id}',
                'SK': f'FILE#{file_path}',
                'EntityType': 'TemplateFile',
                'file_path': file_path,
                'content': content,
                'size': len(content),
                'last_modified': template.updated_at.isoformat()
            }
            items.append(item)
        return items
    
    def _metadata_item_to_template(self, item: Dict) -> ProjectTemplate:
        """Convert DynamoDB metadata item to ProjectTemplate."""
        # Convert Decimal to Python types
        item = self._dynamodb_to_python(item)
        
        return ProjectTemplate(
            id=item['id'],
            name=item['name'],
            description=item['description'],
            category=item['category'],
            files={},  # Will be populated separately
            required_vars=item.get('required_vars', []),
            optional_vars=item.get('optional_vars', []),
            tech_stack=item.get('tech_stack', []),
            estimated_setup_time=item.get('estimated_setup_time', 30),
            complexity=item.get('complexity', 'medium'),
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at']),
            author=item.get('author', 'system'),
            version=item.get('version', '1.0.0'),
            tags=item.get('tags', [])
        )
    
    async def save_template(self, template: ProjectTemplate) -> bool:
        """
        Save a project template to DynamoDB.
        
        Args:
            template: The ProjectTemplate to save
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Update timestamp
            template.updated_at = datetime.utcnow()
            
            # Prepare items
            metadata_item = self._template_to_metadata_item(template)
            file_items = self._template_files_to_items(template)
            
            # Batch write all items
            with self.table.batch_writer() as batch:
                # Write metadata
                batch.put_item(Item=metadata_item)
                
                # Write files
                for file_item in file_items:
                    batch.put_item(Item=file_item)
                
                # Write tag index items for GSI2
                for tag in template.tags:
                    tag_item = {
                        'PK': f'TEMPLATE#{template.id}',
                        'SK': f'TAG#{tag}',
                        'GSI2PK': f'TAG#{tag}',
                        'GSI2SK': f'TEMPLATE#{template.id}',
                        'EntityType': 'TemplateTag',
                        'template_id': template.id,
                        'tag': tag
                    }
                    batch.put_item(Item=tag_item)
            
            logger.info(f"Successfully saved template {template.id} with {len(file_items)} files and {len(template.tags)} tags")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to save template {template.id}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving template {template.id}: {e}", exc_info=True)
            return False
    
    async def load_template(self, template_id: str) -> Optional[ProjectTemplate]:
        """
        Load a project template from DynamoDB.
        
        Args:
            template_id: The ID of the template to load
            
        Returns:
            ProjectTemplate if found, None otherwise
        """
        try:
            # Load metadata
            response = self.table.get_item(
                Key={
                    'PK': f'TEMPLATE#{template_id}',
                    'SK': 'METADATA'
                }
            )
            
            if 'Item' not in response:
                logger.warning(f"Template {template_id} not found")
                return None
            
            # Convert metadata to ProjectTemplate
            template = self._metadata_item_to_template(response['Item'])
            
            # Load template files
            file_response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'TEMPLATE#{template_id}') & Key('SK').begins_with('FILE#')
            )
            
            # Populate files
            for item in file_response.get('Items', []):
                file_path = item['file_path']
                content = item['content']
                template.files[file_path] = content
            
            logger.info(f"Successfully loaded template {template_id} with {len(template.files)} files")
            return template
            
        except ClientError as e:
            logger.error(f"Failed to load template {template_id}: {e.response['Error']['Message']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading template {template_id}: {e}", exc_info=True)
            return None
    
    async def update_template(self, template: ProjectTemplate) -> bool:
        """
        Update a project template (alias for save_template).
        
        Args:
            template: The ProjectTemplate to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        return await self.save_template(template)
    
    async def delete_template(self, template_id: str) -> bool:
        """
        Delete a project template from DynamoDB.
        
        Args:
            template_id: The ID of the template to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # Query all items for this template
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'TEMPLATE#{template_id}')
            )
            
            if not response.get('Items'):
                logger.warning(f"Template {template_id} not found")
                return False
            
            # Batch delete all items
            with self.table.batch_writer() as batch:
                for item in response['Items']:
                    batch.delete_item(
                        Key={
                            'PK': item['PK'],
                            'SK': item['SK']
                        }
                    )
            
            logger.info(f"Successfully deleted template {template_id} with {len(response['Items'])} items")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete template {template_id}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting template {template_id}: {e}", exc_info=True)
            return False
    
    async def template_exists(self, template_id: str) -> bool:
        """
        Check if a template exists.
        
        Args:
            template_id: The ID of the template to check
            
        Returns:
            bool: True if template exists, False otherwise
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'TEMPLATE#{template_id}',
                    'SK': 'METADATA'
                }
            )
            return 'Item' in response
        except Exception as e:
            logger.error(f"Error checking if template {template_id} exists: {e}")
            return False
    
    async def list_templates(self, category: Optional[str] = None, limit: int = 100) -> List[ProjectTemplate]:
        """
        List all templates, optionally filtered by category.
        
        Args:
            category: Optional category to filter by (uses GSI1)
            limit: Maximum number of results to return
            
        Returns:
            List of ProjectTemplate objects (metadata only, no files)
        """
        templates = []
        
        try:
            if category:
                # Query by category using GSI1
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression=Key('GSI1PK').eq(f'CATEGORY#{category}'),
                    Limit=limit,
                    ScanIndexForward=False  # Sort by created_at descending
                )
            else:
                # Scan for all templates (less efficient, but works)
                response = self.table.scan(
                    FilterExpression=Attr('EntityType').eq('Template'),
                    Limit=limit
                )
            
            # Convert items to ProjectTemplate objects
            for item in response.get('Items', []):
                try:
                    template = self._metadata_item_to_template(item)
                    # Note: files are not loaded for list operations (performance optimization)
                    templates.append(template)
                except Exception as e:
                    logger.warning(f"Failed to parse template item: {e}")
                    continue
            
            logger.info(f"Listed {len(templates)} templates")
            return templates
            
        except ClientError as e:
            logger.error(f"Failed to list templates: {e.response['Error']['Message']}")
            return templates
        except Exception as e:
            logger.error(f"Unexpected error listing templates: {e}", exc_info=True)
            return templates
    
    async def list_templates_by_tag(self, tag: str, limit: int = 100) -> List[ProjectTemplate]:
        """
        List templates by tag using GSI2.
        
        Args:
            tag: The tag to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of ProjectTemplate objects (metadata only, no files)
        """
        templates = []
        
        try:
            # Query by tag using GSI2
            response = self.table.query(
                IndexName='GSI2',
                KeyConditionExpression=Key('GSI2PK').eq(f'TAG#{tag}'),
                Limit=limit
            )
            
            # Get template IDs from tag items
            template_ids = [item['template_id'] for item in response.get('Items', [])]
            
            # Batch get template metadata
            if template_ids:
                templates = await self._batch_get_template_metadata(template_ids)
            
            logger.info(f"Found {len(templates)} templates with tag '{tag}'")
            return templates
            
        except ClientError as e:
            logger.error(f"Failed to list templates by tag {tag}: {e.response['Error']['Message']}")
            return templates
        except Exception as e:
            logger.error(f"Unexpected error listing templates by tag: {e}", exc_info=True)
            return templates
    
    async def _batch_get_template_metadata(self, template_ids: List[str]) -> List[ProjectTemplate]:
        """
        Batch load template metadata (no files).
        
        Args:
            template_ids: List of template IDs to load
            
        Returns:
            List of ProjectTemplate objects
        """
        templates = []
        
        try:
            # Prepare batch get request
            keys = [
                {'PK': f'TEMPLATE#{tid}', 'SK': 'METADATA'}
                for tid in template_ids
            ]
            
            # Batch get items (max 100 at a time)
            for i in range(0, len(keys), 100):
                batch_keys = keys[i:i+100]
                response = self.dynamodb.batch_get_item(
                    RequestItems={
                        self.table_name: {
                            'Keys': batch_keys
                        }
                    }
                )
                
                # Convert items to ProjectTemplate objects
                for item in response.get('Responses', {}).get(self.table_name, []):
                    try:
                        template = self._metadata_item_to_template(item)
                        templates.append(template)
                    except Exception as e:
                        logger.warning(f"Failed to parse template item: {e}")
                        continue
            
            return templates
            
        except ClientError as e:
            logger.error(f"Failed to batch get templates: {e.response['Error']['Message']}")
            return templates
        except Exception as e:
            logger.error(f"Unexpected error in batch get: {e}", exc_info=True)
            return templates
    
    async def search_templates(
        self, 
        query: str, 
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[ProjectTemplate]:
        """
        Search templates by name, description, or tech stack.
        
        Args:
            query: Search query string
            category: Optional category filter
            tags: Optional list of tags to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of ProjectTemplate objects matching the search criteria
        """
        templates = []
        
        try:
            # Build filter expression
            filter_expr = Attr('EntityType').eq('Template')
            
            # Add text search conditions
            if query:
                query_lower = query.lower()
                filter_expr = filter_expr & (
                    Attr('name').contains(query) |
                    Attr('description').contains(query) |
                    Attr('tech_stack').contains(query)
                )
            
            # Add category filter
            if category:
                filter_expr = filter_expr & Attr('category').eq(category)
            
            # Execute scan with filters
            response = self.table.scan(
                FilterExpression=filter_expr,
                Limit=limit
            )
            
            # Convert items to ProjectTemplate objects
            for item in response.get('Items', []):
                try:
                    template = self._metadata_item_to_template(item)
                    
                    # Additional tag filtering (if specified)
                    if tags:
                        if any(tag in template.tags for tag in tags):
                            templates.append(template)
                    else:
                        templates.append(template)
                        
                except Exception as e:
                    logger.warning(f"Failed to parse template item: {e}")
                    continue
            
            logger.info(f"Search found {len(templates)} templates matching query '{query}'")
            return templates
            
        except ClientError as e:
            logger.error(f"Failed to search templates: {e.response['Error']['Message']}")
            return templates
        except Exception as e:
            logger.error(f"Unexpected error searching templates: {e}", exc_info=True)
            return templates
    
    async def get_template_file(self, template_id: str, file_path: str) -> Optional[str]:
        """
        Get a specific file from a template.
        
        Args:
            template_id: The ID of the template
            file_path: The path of the file to retrieve
            
        Returns:
            File content if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'TEMPLATE#{template_id}',
                    'SK': f'FILE#{file_path}'
                }
            )
            
            if 'Item' not in response:
                logger.warning(f"File {file_path} not found in template {template_id}")
                return None
            
            return response['Item']['content']
            
        except ClientError as e:
            logger.error(f"Failed to get template file: {e.response['Error']['Message']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting template file: {e}", exc_info=True)
            return None
    
    async def list_template_files(self, template_id: str) -> List[str]:
        """
        List all file paths in a template.
        
        Args:
            template_id: The ID of the template
            
        Returns:
            List of file paths
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'TEMPLATE#{template_id}') & Key('SK').begins_with('FILE#'),
                ProjectionExpression='file_path'
            )
            
            file_paths = [item['file_path'] for item in response.get('Items', [])]
            logger.info(f"Template {template_id} has {len(file_paths)} files")
            return file_paths
            
        except ClientError as e:
            logger.error(f"Failed to list template files: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing template files: {e}", exc_info=True)
            return []
    
    async def update_template_metadata(self, template_id: str, updates: Dict) -> bool:
        """
        Update specific metadata fields of a template without loading files.
        
        Args:
            template_id: The ID of the template to update
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Build update expression
            update_expr_parts = []
            expr_attr_names = {}
            expr_attr_values = {}
            
            # Add updated_at timestamp
            updates['updated_at'] = datetime.utcnow().isoformat()
            
            for key, value in updates.items():
                placeholder = f"#{key}"
                value_placeholder = f":{key}"
                update_expr_parts.append(f"{placeholder} = {value_placeholder}")
                expr_attr_names[placeholder] = key
                expr_attr_values[value_placeholder] = self._python_to_dynamodb(value)
            
            update_expr = "SET " + ", ".join(update_expr_parts)
            
            # Execute update
            self.table.update_item(
                Key={
                    'PK': f'TEMPLATE#{template_id}',
                    'SK': 'METADATA'
                },
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values
            )
            
            logger.info(f"Successfully updated template {template_id} metadata")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to update template metadata: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating template metadata: {e}", exc_info=True)
            return False
    
    def batch_get_templates(self, template_ids: List[str]) -> List[ProjectTemplate]:
        """
        Batch load multiple templates (metadata only, no files).
        
        Args:
            template_ids: List of template IDs to load
            
        Returns:
            List of ProjectTemplate objects
        """
        templates = []
        
        try:
            # Prepare batch get request
            keys = [
                {'PK': f'TEMPLATE#{tid}', 'SK': 'METADATA'}
                for tid in template_ids
            ]
            
            # Batch get items (max 100 at a time)
            for i in range(0, len(keys), 100):
                batch_keys = keys[i:i+100]
                response = self.dynamodb.batch_get_item(
                    RequestItems={
                        self.table_name: {
                            'Keys': batch_keys
                        }
                    }
                )
                
                # Convert items to ProjectTemplate objects
                for item in response.get('Responses', {}).get(self.table_name, []):
                    try:
                        template = self._metadata_item_to_template(item)
                        templates.append(template)
                    except Exception as e:
                        logger.warning(f"Failed to parse template item: {e}")
                        continue
            
            logger.info(f"Batch loaded {len(templates)} templates")
            return templates
            
        except ClientError as e:
            logger.error(f"Failed to batch get templates: {e.response['Error']['Message']}")
            return templates
        except Exception as e:
            logger.error(f"Unexpected error in batch get: {e}", exc_info=True)
            return templates
    
    async def get_categories(self) -> List[str]:
        """
        Get all unique template categories.
        
        Returns:
            List of category names
        """
        try:
            response = self.table.scan(
                FilterExpression=Attr('EntityType').eq('Template'),
                ProjectionExpression='category'
            )
            
            categories = list(set(item['category'] for item in response.get('Items', [])))
            logger.info(f"Found {len(categories)} template categories")
            return sorted(categories)
            
        except ClientError as e:
            logger.error(f"Failed to get categories: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting categories: {e}", exc_info=True)
            return []
    
    async def get_all_tags(self) -> List[str]:
        """
        Get all unique tags across all templates.
        
        Returns:
            List of tag names
        """
        try:
            response = self.table.scan(
                FilterExpression=Attr('EntityType').eq('Template'),
                ProjectionExpression='tags'
            )
            
            # Flatten all tags
            all_tags = set()
            for item in response.get('Items', []):
                all_tags.update(item.get('tags', []))
            
            logger.info(f"Found {len(all_tags)} unique tags")
            return sorted(list(all_tags))
            
        except ClientError as e:
            logger.error(f"Failed to get tags: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting tags: {e}", exc_info=True)
            return []
