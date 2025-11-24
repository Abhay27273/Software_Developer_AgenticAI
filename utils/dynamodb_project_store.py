"""
DynamoDB adapter for ProjectContext storage.

Implements single-table design pattern with proper PK/SK structure
for efficient querying and storage of project data.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from models.project_context import (
    ProjectContext, ProjectType, ProjectStatus,
    Dependency, Modification, Deployment, DeploymentConfig
)

logger = logging.getLogger(__name__)


class DynamoDBProjectStore:
    """
    DynamoDB adapter for ProjectContext with single-table design.
    
    Table structure:
    - PK: PROJECT#<project_id>
    - SK: METADATA | FILE#<file_path>
    - GSI1PK: OWNER#<owner_id>
    - GSI1SK: PROJECT#<created_at>
    - GSI2PK: STATUS#<status>
    - GSI2SK: PROJECT#<project_id>
    """
    
    def __init__(self, table_name: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize DynamoDB project store.
        
        Args:
            table_name: DynamoDB table name (defaults to env var DYNAMODB_TABLE_NAME)
            region: AWS region (defaults to env var AWS_REGION or us-east-1)
        """
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE_NAME', 'agenticai-data')
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize DynamoDB client
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)
        
        logger.info(f"DynamoDBProjectStore initialized with table: {self.table_name}")
    
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
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._dynamodb_to_python(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._dynamodb_to_python(item) for item in obj]
        return obj
    
    def _project_to_metadata_item(self, project: ProjectContext) -> Dict:
        """Convert ProjectContext to DynamoDB metadata item."""
        item = {
            'PK': f'PROJECT#{project.id}',
            'SK': 'METADATA',
            'GSI1PK': f'OWNER#{project.owner_id}',
            'GSI1SK': f'PROJECT#{project.created_at.isoformat()}',
            'GSI2PK': f'STATUS#{project.status.value}',
            'GSI2SK': f'PROJECT#{project.id}',
            'EntityType': 'Project',
            'id': project.id,
            'name': project.name,
            'type': project.type.value,
            'status': project.status.value,
            'owner_id': project.owner_id,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
            'last_deployed_at': project.last_deployed_at.isoformat() if project.last_deployed_at else None,
            'description': project.description,
            'repository_url': project.repository_url,
            'test_coverage': project.test_coverage,
            'security_score': project.security_score,
            'performance_score': project.performance_score,
            'dependencies': [
                {'name': d.name, 'version': d.version, 'type': d.type}
                for d in project.dependencies
            ],
            'modifications': [
                {
                    'id': m.id,
                    'timestamp': m.timestamp.isoformat(),
                    'description': m.description,
                    'affected_files': m.affected_files,
                    'requested_by': m.requested_by,
                    'status': m.status
                }
                for m in project.modifications
            ],
            'deployments': [
                {
                    'id': d.id,
                    'timestamp': d.timestamp.isoformat(),
                    'environment': d.environment,
                    'platform': d.platform,
                    'url': d.url,
                    'status': d.status
                }
                for d in project.deployments
            ],
            'environment_vars': project.environment_vars,
            'deployment_config': {
                'platform': project.deployment_config.platform,
                'environment': project.deployment_config.environment,
                'auto_deploy': project.deployment_config.auto_deploy,
                'health_check_enabled': project.deployment_config.health_check_enabled,
                'monitoring_enabled': project.deployment_config.monitoring_enabled
            }
        }
        
        # Convert floats to Decimal for DynamoDB
        return self._python_to_dynamodb(item)
    
    def _project_files_to_items(self, project: ProjectContext) -> List[Dict]:
        """Convert project files to DynamoDB items."""
        items = []
        for file_path, content in project.codebase.items():
            item = {
                'PK': f'PROJECT#{project.id}',
                'SK': f'FILE#{file_path}',
                'EntityType': 'ProjectFile',
                'file_path': file_path,
                'content': content,
                'size': len(content),
                'last_modified': project.updated_at.isoformat()
            }
            items.append(item)
        return items
    
    def _metadata_item_to_project(self, item: Dict) -> ProjectContext:
        """Convert DynamoDB metadata item to ProjectContext."""
        # Convert Decimal to float
        item = self._dynamodb_to_python(item)
        
        # Parse dependencies
        dependencies = [
            Dependency(
                name=d['name'],
                version=d['version'],
                type=d['type']
            )
            for d in item.get('dependencies', [])
        ]
        
        # Parse modifications
        modifications = [
            Modification(
                id=m['id'],
                timestamp=datetime.fromisoformat(m['timestamp']),
                description=m['description'],
                affected_files=m['affected_files'],
                requested_by=m['requested_by'],
                status=m['status']
            )
            for m in item.get('modifications', [])
        ]
        
        # Parse deployments
        deployments = [
            Deployment(
                id=d['id'],
                timestamp=datetime.fromisoformat(d['timestamp']),
                environment=d['environment'],
                platform=d['platform'],
                url=d.get('url'),
                status=d['status']
            )
            for d in item.get('deployments', [])
        ]
        
        # Parse deployment config
        dc_data = item.get('deployment_config', {})
        deployment_config = DeploymentConfig(
            platform=dc_data.get('platform', 'render'),
            environment=dc_data.get('environment', 'production'),
            auto_deploy=dc_data.get('auto_deploy', False),
            health_check_enabled=dc_data.get('health_check_enabled', True),
            monitoring_enabled=dc_data.get('monitoring_enabled', False)
        )
        
        return ProjectContext(
            id=item['id'],
            name=item['name'],
            type=ProjectType(item['type']),
            status=ProjectStatus(item['status']),
            owner_id=item.get('owner_id', 'default_user'),
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at']),
            last_deployed_at=datetime.fromisoformat(item['last_deployed_at']) if item.get('last_deployed_at') else None,
            codebase={},  # Will be populated separately
            dependencies=dependencies,
            modifications=modifications,
            deployments=deployments,
            environment_vars=item.get('environment_vars', {}),
            deployment_config=deployment_config,
            test_coverage=item.get('test_coverage', 0.0),
            security_score=item.get('security_score', 0.0),
            performance_score=item.get('performance_score', 0.0),
            description=item.get('description', ''),
            repository_url=item.get('repository_url')
        )
    
    async def save_context(self, context: ProjectContext) -> bool:
        """
        Save a project context to DynamoDB.
        
        Args:
            context: The ProjectContext to save
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Update timestamp
            context.updated_at = datetime.utcnow()
            
            # Prepare items
            metadata_item = self._project_to_metadata_item(context)
            file_items = self._project_files_to_items(context)
            
            # Batch write all items
            with self.table.batch_writer() as batch:
                # Write metadata
                batch.put_item(Item=metadata_item)
                
                # Write files
                for file_item in file_items:
                    batch.put_item(Item=file_item)
            
            logger.info(f"Successfully saved project {context.id} with {len(file_items)} files")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to save project {context.id}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving project {context.id}: {e}", exc_info=True)
            return False
    
    async def load_context(self, project_id: str) -> Optional[ProjectContext]:
        """
        Load a project context from DynamoDB.
        
        Args:
            project_id: The ID of the project to load
            
        Returns:
            ProjectContext if found, None otherwise
        """
        try:
            # Load metadata
            response = self.table.get_item(
                Key={
                    'PK': f'PROJECT#{project_id}',
                    'SK': 'METADATA'
                }
            )
            
            if 'Item' not in response:
                logger.warning(f"Project {project_id} not found")
                return None
            
            # Convert metadata to ProjectContext
            project = self._metadata_item_to_project(response['Item'])
            
            # Load project files
            file_response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'PROJECT#{project_id}') & Key('SK').begins_with('FILE#')
            )
            
            # Populate codebase
            for item in file_response.get('Items', []):
                file_path = item['file_path']
                content = item['content']
                project.codebase[file_path] = content
            
            logger.info(f"Successfully loaded project {project_id} with {len(project.codebase)} files")
            return project
            
        except ClientError as e:
            logger.error(f"Failed to load project {project_id}: {e.response['Error']['Message']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading project {project_id}: {e}", exc_info=True)
            return None
    
    async def update_context(self, context: ProjectContext) -> bool:
        """
        Update a project context (alias for save_context).
        
        Args:
            context: The ProjectContext to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        return await self.save_context(context)
    
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
    
    async def delete_context(self, project_id: str) -> bool:
        """
        Delete a project context from DynamoDB.
        
        Args:
            project_id: The ID of the project to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # Query all items for this project
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'PROJECT#{project_id}')
            )
            
            if not response.get('Items'):
                logger.warning(f"Project {project_id} not found")
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
            
            logger.info(f"Successfully deleted project {project_id} with {len(response['Items'])} items")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete project {project_id}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting project {project_id}: {e}", exc_info=True)
            return False
    
    async def context_exists(self, project_id: str) -> bool:
        """
        Check if a project context exists.
        
        Args:
            project_id: The ID of the project to check
            
        Returns:
            bool: True if context exists, False otherwise
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'PROJECT#{project_id}',
                    'SK': 'METADATA'
                }
            )
            return 'Item' in response
        except Exception as e:
            logger.error(f"Error checking if project {project_id} exists: {e}")
            return False
    
    async def list_contexts(self, owner_id: Optional[str] = None, status: Optional[str] = None) -> List[ProjectContext]:
        """
        List all project contexts, optionally filtered by owner or status.
        
        Args:
            owner_id: Optional owner ID to filter by (uses GSI1)
            status: Optional status to filter by (uses GSI2)
            
        Returns:
            List of ProjectContext objects
        """
        contexts = []
        
        try:
            if owner_id:
                # Query by owner using GSI1
                response = self.table.query(
                    IndexName='GSI1',
                    KeyConditionExpression=Key('GSI1PK').eq(f'OWNER#{owner_id}')
                )
            elif status:
                # Query by status using GSI2
                response = self.table.query(
                    IndexName='GSI2',
                    KeyConditionExpression=Key('GSI2PK').eq(f'STATUS#{status}')
                )
            else:
                # Scan for all projects (less efficient, but works)
                response = self.table.scan(
                    FilterExpression=Attr('EntityType').eq('Project')
                )
            
            # Convert items to ProjectContext objects
            for item in response.get('Items', []):
                try:
                    project = self._metadata_item_to_project(item)
                    # Note: codebase is not loaded for list operations (performance optimization)
                    contexts.append(project)
                except Exception as e:
                    logger.warning(f"Failed to parse project item: {e}")
                    continue
            
            logger.info(f"Listed {len(contexts)} project contexts")
            return contexts
            
        except ClientError as e:
            logger.error(f"Failed to list contexts: {e.response['Error']['Message']}")
            return contexts
        except Exception as e:
            logger.error(f"Unexpected error listing contexts: {e}", exc_info=True)
            return contexts
    
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
    
    def batch_get_contexts(self, project_ids: List[str]) -> List[ProjectContext]:
        """
        Batch load multiple project contexts (metadata only, no files).
        
        Args:
            project_ids: List of project IDs to load
            
        Returns:
            List of ProjectContext objects
        """
        contexts = []
        
        try:
            # Prepare batch get request
            keys = [
                {'PK': f'PROJECT#{pid}', 'SK': 'METADATA'}
                for pid in project_ids
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
                
                # Convert items to ProjectContext objects
                for item in response.get('Responses', {}).get(self.table_name, []):
                    try:
                        project = self._metadata_item_to_project(item)
                        contexts.append(project)
                    except Exception as e:
                        logger.warning(f"Failed to parse project item: {e}")
                        continue
            
            logger.info(f"Batch loaded {len(contexts)} project contexts")
            return contexts
            
        except ClientError as e:
            logger.error(f"Failed to batch get contexts: {e.response['Error']['Message']}")
            return contexts
        except Exception as e:
            logger.error(f"Unexpected error in batch get: {e}", exc_info=True)
            return contexts
    
    async def query_by_owner(self, owner_id: str, limit: int = 100) -> List[ProjectContext]:
        """
        Query projects by owner using GSI1.
        
        Args:
            owner_id: The owner ID to query
            limit: Maximum number of results to return
            
        Returns:
            List of ProjectContext objects
        """
        try:
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq(f'OWNER#{owner_id}'),
                Limit=limit,
                ScanIndexForward=False  # Sort by created_at descending
            )
            
            contexts = []
            for item in response.get('Items', []):
                try:
                    project = self._metadata_item_to_project(item)
                    contexts.append(project)
                except Exception as e:
                    logger.warning(f"Failed to parse project item: {e}")
                    continue
            
            logger.info(f"Found {len(contexts)} projects for owner {owner_id}")
            return contexts
            
        except ClientError as e:
            logger.error(f"Failed to query by owner {owner_id}: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying by owner: {e}", exc_info=True)
            return []
    
    async def query_by_status(self, status: str, limit: int = 100) -> List[ProjectContext]:
        """
        Query projects by status using GSI2.
        
        Args:
            status: The status to query
            limit: Maximum number of results to return
            
        Returns:
            List of ProjectContext objects
        """
        try:
            response = self.table.query(
                IndexName='GSI2',
                KeyConditionExpression=Key('GSI2PK').eq(f'STATUS#{status}'),
                Limit=limit
            )
            
            contexts = []
            for item in response.get('Items', []):
                try:
                    project = self._metadata_item_to_project(item)
                    contexts.append(project)
                except Exception as e:
                    logger.warning(f"Failed to parse project item: {e}")
                    continue
            
            logger.info(f"Found {len(contexts)} projects with status {status}")
            return contexts
            
        except ClientError as e:
            logger.error(f"Failed to query by status {status}: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying by status: {e}", exc_info=True)
            return []
