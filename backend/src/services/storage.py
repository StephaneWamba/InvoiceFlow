import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from typing import BinaryIO, Optional
import io
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """MinIO/S3 storage service for document files"""

    def __init__(self):
        self._client: Optional[object] = None
        self.bucket = settings.MINIO_BUCKET
        self._initialized = False
        self._bucket_checked = False

    def _get_client(self):
        """Lazy initialization of S3 client"""
        if self._client is None:
            try:
                # Determine endpoint URL
                if settings.MINIO_ENDPOINT.startswith('http://') or settings.MINIO_ENDPOINT.startswith('https://'):
                    endpoint_url = settings.MINIO_ENDPOINT
                else:
                    endpoint_url = f"http://{settings.MINIO_ENDPOINT}" if not settings.MINIO_USE_SSL else f"https://{settings.MINIO_ENDPOINT}"

                self._client = boto3.client(
                    "s3",
                    endpoint_url=endpoint_url,
                    aws_access_key_id=settings.MINIO_ACCESS_KEY,
                    aws_secret_access_key=settings.MINIO_SECRET_KEY,
                    region_name="us-east-1",  # MinIO doesn't care about region
                )
                # Don't check bucket here - do it lazily when actually needed
                self._initialized = True
            except Exception as e:
                logger.warning(
                    f"Storage service client creation failed: {str(e)}")
                self._initialized = False
                # Don't raise - allow lazy retry on actual use
        return self._client

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist (lazy, only called when needed)"""
        if self._bucket_checked:
            return

        try:
            client = self._get_client()
            client.head_bucket(Bucket=self.bucket)
            self._bucket_checked = True
        except (ClientError, EndpointConnectionError) as e:
            error_code = e.response.get('Error', {}).get(
                'Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    client = self._get_client()
                    client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Created bucket: {self.bucket}")
                    self._bucket_checked = True
                except (ClientError, EndpointConnectionError) as create_error:
                    logger.warning(
                        f"Failed to create bucket: {str(create_error)}")
            else:
                logger.warning(f"Failed to check bucket existence: {str(e)}")
                # Don't raise - allow operations to fail gracefully later

    def upload_file(self, file_content: bytes, file_path: str, content_type: str = "application/pdf") -> str:
        """Upload file to storage and return the path"""
        self._ensure_bucket_exists()  # Ensure bucket exists before upload
        client = self._get_client()
        try:
            client.put_object(
                Bucket=self.bucket,
                Key=file_path,
                Body=file_content,
                ContentType=content_type,
            )
            return file_path
        except (ClientError, EndpointConnectionError) as e:
            raise Exception(f"Failed to upload file: {str(e)}")

    def get_file(self, file_path: str) -> bytes:
        """Download file from storage"""
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self.bucket, Key=file_path)
            return response["Body"].read()
        except (ClientError, EndpointConnectionError) as e:
            raise Exception(f"Failed to get file: {str(e)}")

    def delete_file(self, file_path: str):
        """Delete file from storage"""
        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket, Key=file_path)
        except (ClientError, EndpointConnectionError) as e:
            error_code = e.response.get('Error', {}).get(
                'Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
            # Don't raise error if file doesn't exist (already deleted) or connection failed
            if error_code == 'NoSuchKey' or isinstance(e, EndpointConnectionError):
                logger.warning(
                    f"File deletion skipped (file not found or storage unavailable): {file_path}")
                return
            raise Exception(f"Failed to delete file: {str(e)}")

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in storage"""
        try:
            client = self._get_client()
            client.head_object(Bucket=self.bucket, Key=file_path)
            return True
        except (ClientError, EndpointConnectionError):
            return False


# Lazy initialization - only creates client when first used
storage_service = StorageService()
