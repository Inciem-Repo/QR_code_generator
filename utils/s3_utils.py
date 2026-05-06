import boto3
import os
from botocore.exceptions import NoCredentialsError
from config import config

class S3Service:
    @staticmethod
    def get_client():
        return boto3.client(
            's3',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION
        )

    @staticmethod
    async def upload_file(file_content, file_name, content_type=None):
        """
        Uploads a file to S3 and returns the public URL.
        file_content: bytes
        file_name: str (the key in S3)
        content_type: str (optional)
        """
        s3 = S3Service.get_client()
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            # Note: We are not setting ACL='public-read' as some buckets have block public access enabled.
            # We will rely on the bucket policy or generate a public URL.
            s3.put_object(
                Bucket=config.AWS_S3_BUCKET,
                Key=file_name,
                Body=file_content,
                **extra_args
            )
            
            url = f"https://{config.AWS_S3_BUCKET}.s3.{config.AWS_REGION}.amazonaws.com/{file_name}"
            return url
        except NoCredentialsError:
            print("Credentials not available")
            return None
        except Exception as e:
            print(f"Error uploading to S3: {e}")
            return None

    @staticmethod
    async def delete_file(file_name):
        """
        Deletes a file from S3.
        file_name: str (the key in S3)
        """
        s3 = S3Service.get_client()
        try:
            s3.delete_object(Bucket=config.AWS_S3_BUCKET, Key=file_name)
            return True
        except Exception as e:
            print(f"Error deleting from S3: {e}")
            return False
