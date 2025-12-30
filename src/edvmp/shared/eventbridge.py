from __future__ import annotations

import boto3


def put_event(*, region_name: str, bus_name: str, source: str, detail_type: str, detail: str) -> None:
    events = boto3.client("events", region_name=region_name)
    events.put_events(
        Entries=[
            {
                "EventBusName": bus_name,
                "Source": source,
                "DetailType": detail_type,
                "Detail": detail,
            }
        ]
    )

