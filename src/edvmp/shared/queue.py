from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import redis


@dataclass(frozen=True)
class QueueMessage:
    message_type: str
    payload: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps({"message_type": self.message_type, "payload": self.payload})

    @staticmethod
    def from_json(raw: str) -> QueueMessage:
        data = json.loads(raw)
        return QueueMessage(message_type=data["message_type"], payload=data["payload"])


class RedisQueue:
    def __init__(self, client: redis.Redis, queue_name: str):
        self._client = client
        self._queue_name = queue_name

    def enqueue(self, message: QueueMessage) -> None:
        self._client.rpush(self._queue_name, message.to_json())

    def dequeue_blocking(self, timeout_s: int = 5) -> QueueMessage | None:
        item = self._client.blpop(self._queue_name, timeout=timeout_s)
        if not item:
            return None
        _, raw = item
        return QueueMessage.from_json(raw.decode("utf-8"))


class RedisDlq:
    def __init__(self, client: redis.Redis, dlq_name: str):
        self._client = client
        self._dlq_name = dlq_name

    def push(self, message: dict[str, Any]) -> None:
        self._client.rpush(self._dlq_name, json.dumps(message))

    def drain(self, max_items: int = 1000) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for _ in range(max_items):
            raw = self._client.lpop(self._dlq_name)
            if raw is None:
                break
            items.append(json.loads(raw.decode("utf-8")))
        return items
