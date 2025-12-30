from __future__ import annotations

import boto3
from botocore.stub import Stubber

from edvmp.shared.s3 import ensure_bucket_exists


def test_ensure_bucket_exists_creates_on_missing() -> None:
    s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="x",
        aws_secret_access_key="y",
    )
    stubber = Stubber(s3)
    stubber.add_client_error("head_bucket", service_error_code="404", expected_params={"Bucket": "b"})
    stubber.add_response("create_bucket", service_response={}, expected_params={"Bucket": "b"})
    with stubber:
        ensure_bucket_exists(s3, "b")

