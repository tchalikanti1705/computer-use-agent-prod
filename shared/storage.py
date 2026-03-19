import boto3
from botocore.config import Config as BotoConfig
from shared.config import get_settings
import structlog
logger = structlog.get_logger()

def get_s3_client():
    s = get_settings()
    return boto3.client("s3", endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key, aws_secret_access_key=s.s3_secret_key,
        config=BotoConfig(signature_version="s3v4"))

class ArtifactStore:
    def __init__(self):
        self.client = get_s3_client()
        self.bucket = get_settings().s3_bucket
        try: self.client.head_bucket(Bucket=self.bucket)
        except: 
            try: self.client.create_bucket(Bucket=self.bucket)
            except: pass
    def upload_screenshot(self, key: str, png_bytes: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=png_bytes, ContentType="image/png")
        return key
    def get_screenshot(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
    def upload_json(self, key: str, data: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data.encode(), ContentType="application/json")
        return key
