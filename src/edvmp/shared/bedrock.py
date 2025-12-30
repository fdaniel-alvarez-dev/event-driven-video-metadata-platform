from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, cast

import boto3


@dataclass(frozen=True)
class BedrockClient:
    mode: str  # mock|aws
    model_id: str
    region_name: str

    def summarize(self, *, metadata: dict[str, Any]) -> str:
        if self.mode != "aws":
            # Deterministic mock summary (same shape as a real "model text" output)
            duration = metadata.get("format", {}).get("duration")
            codec = metadata.get("streams", [{}])[0].get("codec_name")
            width = metadata.get("streams", [{}])[0].get("width")
            height = metadata.get("streams", [{}])[0].get("height")
            return (
                "Mock Bedrock Summary: "
                f"video codec={codec}, resolution={width}x{height}, duration_s={duration}."
            )

        bedrock_runtime = boto3.client("bedrock-runtime", region_name=self.region_name)
        prompt = (
            "Summarize the following extracted video metadata in 1-2 sentences for a job status page.\n\n"
            + json.dumps(metadata)
        )
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        response = bedrock_runtime.invoke_model(modelId=self.model_id, body=body)
        payload = json.loads(response["body"].read())
        # Anthropics responses are typically: { "content": [ { "text": "..." } ] }
        return cast(str, payload["content"][0]["text"])
