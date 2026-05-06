import asyncio
import logging
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from config import config

logger = logging.getLogger(__name__)


class S3Service:
    """
    S3 file operations for the QR/Ads backend.

    All public methods are async and run boto3 blocking calls in a
    thread pool so they never stall the FastAPI event loop.
    """

    @staticmethod
    def _get_client():
        """Create and return a boto3 S3 client."""
        return boto3.client(
            "s3",
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION,
        )

    # ------------------------------------------------------------------ #
    # Upload
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sync_upload(file_content: bytes, file_name: str, content_type: str | None) -> str | None:
        """Synchronous S3 put_object — called inside a thread."""
        s3 = S3Service._get_client()
        extra = {}
        if content_type:
            extra["ContentType"] = content_type

        s3.put_object(
            Bucket=config.AWS_S3_BUCKET,
            Key=file_name,
            Body=file_content,
            **extra,
        )
        url = (
            f"https://{config.AWS_S3_BUCKET}.s3.{config.AWS_REGION}.amazonaws.com/{file_name}"
        )
        logger.info("[S3] Uploaded '%s' → %s", file_name, url)
        return url

    @staticmethod
    async def upload_file(file_content: bytes, file_name: str, content_type: str | None = None) -> str | None:
        """
        Upload bytes to S3 and return the public URL.

        Args:
            file_content:  Raw bytes to upload.
            file_name:     S3 object key (e.g. 'ads/uuid_photo.jpg').
            content_type:  MIME type string (e.g. 'image/png').

        Returns:
            Public S3 URL on success, None on failure.
        """
        if not file_content:
            logger.warning("[S3] upload_file called with empty content for key '%s'", file_name)
            return None

        try:
            return await asyncio.to_thread(
                S3Service._sync_upload, file_content, file_name, content_type
            )
        except NoCredentialsError:
            logger.error("[S3] AWS credentials not configured or invalid.")
            return None
        except ClientError as exc:
            logger.error("[S3] ClientError uploading '%s': %s", file_name, exc)
            return None
        except Exception as exc:
            logger.error("[S3] Unexpected error uploading '%s': %s", file_name, exc)
            return None

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sync_delete(file_name: str) -> bool:
        """Synchronous S3 delete_object — called inside a thread."""
        s3 = S3Service._get_client()
        s3.delete_object(Bucket=config.AWS_S3_BUCKET, Key=file_name)
        logger.info("[S3] Deleted object '%s'", file_name)
        return True

    @staticmethod
    async def delete_file(file_name: str) -> bool:
        """
        Delete an object from S3 by its key.

        Args:
            file_name: S3 object key to delete.

        Returns:
            True on success, False on failure.
        """
        if not file_name:
            return False

        try:
            return await asyncio.to_thread(S3Service._sync_delete, file_name)
        except NoCredentialsError:
            logger.error("[S3] AWS credentials not configured or invalid.")
            return False
        except ClientError as exc:
            logger.error("[S3] ClientError deleting '%s': %s", file_name, exc)
            return False
        except Exception as exc:
            logger.error("[S3] Unexpected error deleting '%s': %s", file_name, exc)
            return False
