from __future__ import annotations

import json
from typing import Any, cast

import redis


class RedisEventStream:
    def __init__(self, client: redis.Redis, stream_name: str):
        self._client = client
        self._stream_name = stream_name

    def publish(self, event: dict[str, Any]) -> str:
        message_id = self._client.xadd(
            self._stream_name,
            fields={"event": json.dumps(event)},
            maxlen=10_000,
            approximate=True,
        )
        return cast(str, message_id)

    def ensure_consumer_group(self, group_name: str) -> None:
        try:
            self._client.xgroup_create(
                name=self._stream_name, groupname=group_name, id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                return
            raise

    def read_group(
        self,
        *,
        group_name: str,
        consumer_name: str,
        block_ms: int = 5_000,
        count: int = 10,
    ) -> list[tuple[str, dict[str, Any]]]:
        items = self._client.xreadgroup(
            groupname=group_name,
            consumername=consumer_name,
            streams={self._stream_name: ">"},
            count=count,
            block=block_ms,
        )
        out: list[tuple[str, dict[str, Any]]] = []
        for _, messages in items:
            for message_id, fields in messages:
                event = json.loads(fields[b"event"].decode("utf-8"))
                out.append((message_id.decode("utf-8"), event))
        return out

    def ack(self, group_name: str, message_id: str) -> None:
        self._client.xack(self._stream_name, group_name, message_id)
