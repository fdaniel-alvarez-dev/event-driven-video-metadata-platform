from __future__ import annotations

from edvmp.worker.dlq_analyzer import analyze_messages


def test_dlq_analyzer_classifies_messages() -> None:
    report = analyze_messages(
        [
            {"job_id": "j1", "error_message": "ffprobe_failed: Invalid data found when processing input"},
            {"job_id": "j2", "error_message": "Timeout while calling upstream"},
        ]
    )
    assert report["total_messages"] == 2
    assert report["categories"]["bad_media"] == 1
    assert report["categories"]["timeout"] == 1

