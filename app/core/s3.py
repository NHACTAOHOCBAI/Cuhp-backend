import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from app.core.config import settings
from loguru import logger

def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region
    )

def upload_file_to_s3(file_data: bytes, file_name: str, content_type: str) -> str:
    """
    Uploads a file to AWS S3 in the 'phucnd' directory.
    Returns the CloudFront URL.
    """
    s3_client = get_s3_client()
    bucket = settings.s3_bucket
    
    # Path on S3 bucket: 'phucnd/' subfolder
    s3_key = f"phucnd/{file_name}"
    
    try:
        logger.info(f"Uploading file {file_name} ({len(file_data)} bytes) to S3 bucket {bucket} at key {s3_key}")
        
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=file_data,
            ContentType=content_type
        )
        logger.info(f"Successfully uploaded {s3_key} to S3 bucket {bucket}")
        
        # Build CloudFront URL
        base_url = settings.s3_public_base_url.rstrip("/")
        return f"{base_url}/{s3_key}"
        
    except NoCredentialsError:
        logger.error("AWS credentials not found or invalid.")
        raise Exception("AWS credentials not found or invalid.")
    except ClientError as e:
        logger.error(f"Failed to upload to S3: {e}")
        raise e
