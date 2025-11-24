"""
DynamoDB helper utilities for Lambda functions.
"""

import logging
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DynamoDBHelper:
    """
    Helper class for DynamoDB operations.
    
    Provides common DynamoDB operations with error handling and logging.
    """
    
    def __init__(self, table_name: str):
        """
        Initialize DynamoDB helper.
        
        Args:
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
    
    def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """
        Get an item from DynamoDB.
        
        Args:
            pk: Partition key value
            sk: Sort key value
            
        Returns:
            Item dictionary or None if not found
        """
        try:
            response = self.table.get_item(
                Key={'PK': pk, 'SK': sk}
            )
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Error getting item {pk}#{sk}: {e}")
            raise
    
    def put_item(self, item: Dict[str, Any]) -> None:
        """
        Put an item into DynamoDB.
        
        Args:
            item: Item dictionary to store
        """
        try:
            self.table.put_item(Item=item)
            logger.info(f"Stored item: {item.get('PK')}#{item.get('SK')}")
        except ClientError as e:
            logger.error(f"Error putting item: {e}")
            raise
    
    def update_item(
        self,
        pk: str,
        sk: str,
        update_expression: str,
        expression_values: Dict[str, Any],
        expression_names: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Update an item in DynamoDB.
        
        Args:
            pk: Partition key value
            sk: Sort key value
            update_expression: DynamoDB update expression
            expression_values: Expression attribute values
            expression_names: Expression attribute names (optional)
            
        Returns:
            Updated item attributes
        """
        try:
            kwargs = {
                'Key': {'PK': pk, 'SK': sk},
                'UpdateExpression': update_expression,
                'ExpressionAttributeValues': expression_values,
                'ReturnValues': 'ALL_NEW'
            }
            
            if expression_names:
                kwargs['ExpressionAttributeNames'] = expression_names
            
            response = self.table.update_item(**kwargs)
            return response.get('Attributes', {})
        except ClientError as e:
            logger.error(f"Error updating item {pk}#{sk}: {e}")
            raise
    
    def delete_item(self, pk: str, sk: str) -> None:
        """
        Delete an item from DynamoDB.
        
        Args:
            pk: Partition key value
            sk: Sort key value
        """
        try:
            self.table.delete_item(
                Key={'PK': pk, 'SK': sk}
            )
            logger.info(f"Deleted item: {pk}#{sk}")
        except ClientError as e:
            logger.error(f"Error deleting item {pk}#{sk}: {e}")
            raise
    
    def query(
        self,
        key_condition_expression: str,
        expression_values: Dict[str, Any],
        index_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query items from DynamoDB.
        
        Args:
            key_condition_expression: Key condition expression
            expression_values: Expression attribute values
            index_name: GSI name (optional)
            limit: Maximum number of items to return (optional)
            
        Returns:
            List of items
        """
        try:
            kwargs = {
                'KeyConditionExpression': key_condition_expression,
                'ExpressionAttributeValues': expression_values
            }
            
            if index_name:
                kwargs['IndexName'] = index_name
            
            if limit:
                kwargs['Limit'] = limit
            
            response = self.table.query(**kwargs)
            return response.get('Items', [])
        except ClientError as e:
            logger.error(f"Error querying table: {e}")
            raise
    
    def batch_write(self, items: List[Dict[str, Any]]) -> None:
        """
        Batch write items to DynamoDB.
        
        Args:
            items: List of items to write
        """
        try:
            with self.table.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=item)
            logger.info(f"Batch wrote {len(items)} items")
        except ClientError as e:
            logger.error(f"Error batch writing items: {e}")
            raise
