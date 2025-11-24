"""
DynamoDB adapter for ModificationPlan storage.

Implements single-table design pattern with proper PK/SK structure
for efficient querying and storage of modification plans.
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from models.modification_plan import (
    ModificationPlan, ModificationStatus, CodeChange
)

logger = logging.getLogger(__name__)


class DynamoDBModificationStore:
    """
    DynamoDB adapter for ModificationPlan with single-table design.
    
    Table structure:
    - PK: PROJECT#<project_id>
    - SK: MOD#<modification_id>
    - GSI1PK: STATUS#<status>
    - GSI1SK: MOD#<created_at>
    - GSI2PK: MOD#<modification_id>
    - GSI2SK: METADATA
    """
    
    def __init__(self, table_name: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize DynamoDB modification store.
        
        Args:
            table_name: DynamoDB table name (defaults to env var DYNAMODB_TABLE_NAME)
            region: AWS region (defaults to env var AWS_REGION or us-east-1)
        """
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE_NAME', 'agenticai-data')
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize DynamoDB client
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)
        
        logger.info(f"DynamoDBModificationStore initialized with table: {self.table_name}")
    
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
    
    def _modification_to_item(self, modification: ModificationPlan) -> Dict:
        """Convert ModificationPlan to DynamoDB item."""
        item = {
            'PK': f'PROJECT#{modification.project_id}',
            'SK': f'MOD#{modification.id}',
            'GSI1PK': f'STATUS#{modification.status.value}',
            'GSI1SK': f'MOD#{modification.created_at.isoformat()}',
            'GSI2PK': f'MOD#{modification.id}',
            'GSI2SK': 'METADATA',
            'EntityType': 'Modification',
            'id': modification.id,
            'project_id': modification.project_id,
            'request': modification.request,
            'affected_files': modification.affected_files,
            'changes': [
                {
                    'file_path': c.file_path,
                    'change_type': c.change_type,
                    'description': c.description,
                    'before_snippet': c.before_snippet,
                    'after_snippet': c.after_snippet,
                    'line_start': c.line_start,
                    'line_end': c.line_end
                }
                for c in modification.changes
            ],
            'risk_level': modification.risk_level,
            'risk_score': modification.risk_score,
            'estimated_hours': modification.estimated_hours,
            'complexity': modification.complexity,
            'summary': modification.summary,
            'detailed_explanation': modification.detailed_explanation,
            'impact_description': modification.impact_description,
            'recommendations': modification.recommendations,
            'testing_requirements': modification.testing_requirements,
            'status': modification.status.value,
            'created_at': modification.created_at.isoformat(),
            'approved_at': modification.approved_at.isoformat() if modification.approved_at else None,
            'approved_by': modification.approved_by,
            'started_at': modification.started_at.isoformat() if modification.started_at else None,
            'completed_at': modification.completed_at.isoformat() if modification.completed_at else None,
            'error_message': modification.error_message
        }
        
        # Convert floats to Decimal for DynamoDB
        return self._python_to_dynamodb(item)
    
    def _item_to_modification(self, item: Dict) -> ModificationPlan:
        """Convert DynamoDB item to ModificationPlan."""
        # Convert Decimal to float
        item = self._dynamodb_to_python(item)
        
        # Parse code changes
        changes = [
            CodeChange(
                file_path=c['file_path'],
                change_type=c['change_type'],
                description=c['description'],
                before_snippet=c.get('before_snippet'),
                after_snippet=c.get('after_snippet'),
                line_start=c.get('line_start'),
                line_end=c.get('line_end')
            )
            for c in item.get('changes', [])
        ]
        
        return ModificationPlan(
            id=item['id'],
            project_id=item['project_id'],
            request=item['request'],
            affected_files=item.get('affected_files', []),
            changes=changes,
            risk_level=item.get('risk_level', 'medium'),
            risk_score=item.get('risk_score', 0.5),
            estimated_hours=item.get('estimated_hours', 0.0),
            complexity=item.get('complexity', 'medium'),
            summary=item.get('summary', ''),
            detailed_explanation=item.get('detailed_explanation', ''),
            impact_description=item.get('impact_description', ''),
            recommendations=item.get('recommendations', []),
            testing_requirements=item.get('testing_requirements', []),
            status=ModificationStatus(item.get('status', 'pending_approval')),
            created_at=datetime.fromisoformat(item['created_at']),
            approved_at=datetime.fromisoformat(item['approved_at']) if item.get('approved_at') else None,
            approved_by=item.get('approved_by'),
            started_at=datetime.fromisoformat(item['started_at']) if item.get('started_at') else None,
            completed_at=datetime.fromisoformat(item['completed_at']) if item.get('completed_at') else None,
            error_message=item.get('error_message')
        )
    
    async def save_modification(self, modification: ModificationPlan) -> bool:
        """
        Save a modification plan to DynamoDB.
        
        Args:
            modification: The ModificationPlan to save
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            item = self._modification_to_item(modification)
            self.table.put_item(Item=item)
            
            logger.info(f"Successfully saved modification {modification.id} for project {modification.project_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to save modification {modification.id}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving modification {modification.id}: {e}", exc_info=True)
            return False
    
    async def load_modification(self, project_id: str, modification_id: str) -> Optional[ModificationPlan]:
        """
        Load a modification plan from DynamoDB.
        
        Args:
            project_id: The ID of the project
            modification_id: The ID of the modification
            
        Returns:
            ModificationPlan if found, None otherwise
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'PROJECT#{project_id}',
                    'SK': f'MOD#{modification_id}'
                }
            )
            
            if 'Item' not in response:
                logger.warning(f"Modification {modification_id} not found for project {project_id}")
                return None
            
            modification = self._item_to_modification(response['Item'])
            logger.info(f"Successfully loaded modification {modification_id}")
            return modification
            
        except ClientError as e:
            logger.error(f"Failed to load modification {modification_id}: {e.response['Error']['Message']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading modification {modification_id}: {e}", exc_info=True)
            return None
    
    async def update_modification(self, modification: ModificationPlan) -> bool:
        """
        Update a modification plan (alias for save_modification).
        
        Args:
            modification: The ModificationPlan to update
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        return await self.save_modification(modification)
    
    async def delete_modification(self, project_id: str, modification_id: str) -> bool:
        """
        Delete a modification plan from DynamoDB.
        
        Args:
            project_id: The ID of the project
            modification_id: The ID of the modification
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            self.table.delete_item(
                Key={
                    'PK': f'PROJECT#{project_id}',
                    'SK': f'MOD#{modification_id}'
                }
            )
            
            logger.info(f"Successfully deleted modification {modification_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete modification {modification_id}: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting modification {modification_id}: {e}", exc_info=True)
            return False
    
    async def list_modifications_by_project(self, project_id: str, limit: int = 100) -> List[ModificationPlan]:
        """
        List all modifications for a specific project.
        
        Args:
            project_id: The ID of the project
            limit: Maximum number of results to return
            
        Returns:
            List of ModificationPlan objects
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'PROJECT#{project_id}') & Key('SK').begins_with('MOD#'),
                Limit=limit
            )
            
            modifications = []
            for item in response.get('Items', []):
                try:
                    modification = self._item_to_modification(item)
                    modifications.append(modification)
                except Exception as e:
                    logger.warning(f"Failed to parse modification item: {e}")
                    continue
            
            logger.info(f"Found {len(modifications)} modifications for project {project_id}")
            return modifications
            
        except ClientError as e:
            logger.error(f"Failed to list modifications for project {project_id}: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing modifications: {e}", exc_info=True)
            return []
    
    async def list_modifications_by_status(self, status: str, limit: int = 100) -> List[ModificationPlan]:
        """
        List all modifications with a specific status using GSI1.
        
        Args:
            status: The status to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of ModificationPlan objects
        """
        try:
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq(f'STATUS#{status}'),
                Limit=limit,
                ScanIndexForward=False  # Sort by created_at descending
            )
            
            modifications = []
            for item in response.get('Items', []):
                try:
                    modification = self._item_to_modification(item)
                    modifications.append(modification)
                except Exception as e:
                    logger.warning(f"Failed to parse modification item: {e}")
                    continue
            
            logger.info(f"Found {len(modifications)} modifications with status {status}")
            return modifications
            
        except ClientError as e:
            logger.error(f"Failed to list modifications by status {status}: {e.response['Error']['Message']}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing modifications by status: {e}", exc_info=True)
            return []
    
    async def update_modification_status(
        self, 
        project_id: str, 
        modification_id: str, 
        status: ModificationStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update the status of a modification plan.
        
        Args:
            project_id: The ID of the project
            modification_id: The ID of the modification
            status: The new status
            error_message: Optional error message if status is FAILED
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Load existing modification
            modification = await self.load_modification(project_id, modification_id)
            if modification is None:
                logger.error(f"Cannot update status for non-existent modification {modification_id}")
                return False
            
            # Update status and timestamps
            modification.status = status
            
            if status == ModificationStatus.IN_PROGRESS and modification.started_at is None:
                modification.started_at = datetime.utcnow()
            elif status == ModificationStatus.COMPLETED:
                modification.completed_at = datetime.utcnow()
            elif status == ModificationStatus.FAILED:
                modification.error_message = error_message
            
            # Save updated modification
            return await self.save_modification(modification)
            
        except Exception as e:
            logger.error(f"Failed to update modification status: {e}", exc_info=True)
            return False
    
    async def approve_modification(self, project_id: str, modification_id: str, approved_by: str) -> bool:
        """
        Approve a modification plan.
        
        Args:
            project_id: The ID of the project
            modification_id: The ID of the modification
            approved_by: User ID who approved the modification
            
        Returns:
            bool: True if approval was successful, False otherwise
        """
        try:
            modification = await self.load_modification(project_id, modification_id)
            if modification is None:
                return False
            
            modification.status = ModificationStatus.APPROVED
            modification.approved_at = datetime.utcnow()
            modification.approved_by = approved_by
            
            return await self.save_modification(modification)
            
        except Exception as e:
            logger.error(f"Failed to approve modification {modification_id}: {e}", exc_info=True)
            return False
    
    async def reject_modification(self, project_id: str, modification_id: str) -> bool:
        """
        Reject a modification plan.
        
        Args:
            project_id: The ID of the project
            modification_id: The ID of the modification
            
        Returns:
            bool: True if rejection was successful, False otherwise
        """
        try:
            modification = await self.load_modification(project_id, modification_id)
            if modification is None:
                return False
            
            modification.status = ModificationStatus.REJECTED
            
            return await self.save_modification(modification)
            
        except Exception as e:
            logger.error(f"Failed to reject modification {modification_id}: {e}", exc_info=True)
            return False
    
    def batch_get_modifications(self, keys: List[tuple]) -> List[ModificationPlan]:
        """
        Batch load multiple modifications.
        
        Args:
            keys: List of (project_id, modification_id) tuples
            
        Returns:
            List of ModificationPlan objects
        """
        modifications = []
        
        try:
            # Prepare batch get request
            batch_keys = [
                {'PK': f'PROJECT#{project_id}', 'SK': f'MOD#{mod_id}'}
                for project_id, mod_id in keys
            ]
            
            # Batch get items (max 100 at a time)
            for i in range(0, len(batch_keys), 100):
                batch = batch_keys[i:i+100]
                response = self.dynamodb.batch_get_item(
                    RequestItems={
                        self.table_name: {
                            'Keys': batch
                        }
                    }
                )
                
                # Convert items to ModificationPlan objects
                for item in response.get('Responses', {}).get(self.table_name, []):
                    try:
                        modification = self._item_to_modification(item)
                        modifications.append(modification)
                    except Exception as e:
                        logger.warning(f"Failed to parse modification item: {e}")
                        continue
            
            logger.info(f"Batch loaded {len(modifications)} modifications")
            return modifications
            
        except ClientError as e:
            logger.error(f"Failed to batch get modifications: {e.response['Error']['Message']}")
            return modifications
        except Exception as e:
            logger.error(f"Unexpected error in batch get: {e}", exc_info=True)
            return modifications
    
    async def modification_exists(self, project_id: str, modification_id: str) -> bool:
        """
        Check if a modification exists.
        
        Args:
            project_id: The ID of the project
            modification_id: The ID of the modification
            
        Returns:
            bool: True if modification exists, False otherwise
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'PROJECT#{project_id}',
                    'SK': f'MOD#{modification_id}'
                }
            )
            return 'Item' in response
        except Exception as e:
            logger.error(f"Error checking if modification {modification_id} exists: {e}")
            return False
