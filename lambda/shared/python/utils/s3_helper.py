"""
S3 helper utilities for Lambda functions.
"""

import logging
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Helper:
    """
    Helper class for S3 operations.
    
    Provides common S3 operations with error handling and logging.
    """
    
    def __init__(self, bucket_name: str):
        """
        Initialize S3 helper.
        
        Args:
            bucket_name: Name of the S3 bucket
        """
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name
    
    def put_object(
        self,
        key: str,
        body: str,
        content_type: str = 'text/plain',
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Put an object into S3.
        
        Args:
            key: S3 object key
            body: Object content
            content_type: Content type
            metadata: Object metadata (optional)
        """
        try:
            kwargs = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': body,
                'ContentType': content_type
            }
            
            if metadata:
                kwargs['Metadata'] = metadata
            
            self.s3_client.put_object(**kwargs)
            logger.info(f"Stored object: s3://{self.bucket_name}/{key}")
        except ClientError as e:
            logger.error(f"Error putting object {key}: {e}")
            raise
    
    def get_object(self, key: str) -> str:
        """
        Get an object from S3.
        
        Args:
            key: S3 object key
            
        Returns:
            Object content as string
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response['Body'].read().decode('utf-8')
        except ClientError as e:
            logger.error(f"Error getting object {key}: {e}")
            raise
    
    def delete_object(self, key: str) -> None:
        """
        Delete an object from S3.
        
        Args:
            key: S3 object key
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            logger.info(f"Deleted object: s3://{self.bucket_name}/{key}")
        except ClientError as e:
            logger.error(f"Error deleting object {key}: {e}")
            raise
    
    def list_objects(self, prefix: str = '') -> list:
        """
        List objects in S3 with a given prefix.
        
        Args:
            prefix: Object key prefix
            
        Returns:
            List of object keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append(obj['Key'])
            
            return objects
        except ClientError as e:
            logger.error(f"Error listing objects with prefix {prefix}: {e}")
            raise
    
    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        http_method: str = 'GET'
    ) -> str:
        """
        Generate a presigned URL for S3 object access.
        
        Args:
            key: S3 object key
            expiration: URL expiration time in seconds
            http_method: HTTP method (GET or PUT)
            
        Returns:
            Presigned URL
        """
        try:
            client_method = 'get_object' if http_method == 'GET' else 'put_object'
            
            url = self.s3_client.generate_presigned_url(
                client_method,
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated presigned URL for {key}")
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL for {key}: {e}")
            raise
