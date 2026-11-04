"""Photo storage: S3 in production, a local folder for development."""
from pathlib import Path


class LocalStorage:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes) -> None:
        (self.folder / key).write_bytes(data)

    def url(self, key: str) -> str:
        return f"/api/photos/{key}"

    def path(self, key: str) -> Path:
        return self.folder / key

    def load(self, key: str) -> bytes:
        return (self.folder / key).read_bytes()


class S3Storage:
    def __init__(self, bucket: str, region: str):
        import boto3

        self.bucket = bucket
        self.s3 = boto3.client("s3", region_name=region)

    def save(self, key: str, data: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=f"photos/{key}", Body=data, ContentType="image/jpeg")

    def load(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=f"photos/{key}")["Body"].read()

    def url(self, key: str) -> str:
        return self.s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": f"photos/{key}"}, ExpiresIn=3600)
