from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx


def _api_base() -> str:
    return os.environ.get("API_BASE", "http://localhost:8000")


def _login(client: httpx.Client) -> str:
    username = os.environ.get("AUTH_USERNAME", "demo")
    password = os.environ.get("AUTH_PASSWORD", "demo")
    r = client.post("/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def test_end_to_end_job_completes(tmp_path: Path) -> None:
    api_base = _api_base()
    sample = tmp_path / "sample.mp4"
    subprocess.run(["bash", "scripts/generate_sample_video.sh", str(sample)], check=True)

    with httpx.Client(base_url=api_base, timeout=10) as client:
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        job = client.post(
            "/jobs",
            headers=headers,
            json={"filename": "sample.mp4", "content_type": "video/mp4"},
        )
        job.raise_for_status()
        job_data = job.json()
        job_id = job_data["job_id"]
        upload_url = job_data["upload_url"]

    with httpx.Client(timeout=30) as up:
        r = up.put(upload_url, content=sample.read_bytes())
        r.raise_for_status()

    with httpx.Client(base_url=api_base, timeout=10) as client:
        token = _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        status = None
        for _ in range(60):
            resp = client.get(f"/jobs/{job_id}", headers=headers)
            resp.raise_for_status()
            status = resp.json()["status"]
            if status == "SUCCEEDED":
                break
            if status == "FAILED":
                raise AssertionError(f"Job failed: {resp.json()}")
            time.sleep(2)
        assert status == "SUCCEEDED"

        result = client.get(f"/jobs/{job_id}/result", headers=headers)
        result.raise_for_status()
        payload = result.json()
        assert payload["job_id"] == job_id
        assert "metadata" in payload
        assert "summary" in payload

        history = client.get("/history?limit=10", headers=headers)
        history.raise_for_status()
        items = history.json()["items"]
        assert any(i["job_id"] == job_id for i in items)

