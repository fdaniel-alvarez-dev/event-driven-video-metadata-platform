from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3

from edvmp.shared.queue import QueueMessage


@dataclass(frozen=True)
class SqsReceived:
    message: QueueMessage
    receipt_handle: str
    attributes: dict[str, Any]


class SqsQueue:
    def __init__(self, *, region_name: str, queue_url: str):
        self._sqs = boto3.client("sqs", region_name=region_name)
        self._queue_url = queue_url

    def enqueue(self, message: QueueMessage) -> None:
        self._sqs.send_message(QueueUrl=self._queue_url, MessageBody=message.to_json())

    def receive(self, *, wait_time_s: int = 10, max_messages: int = 1) -> list[SqsReceived]:
        res = self._sqs.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_time_s,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )
        out: list[SqsReceived] = []
        for m in res.get("Messages", []) or []:
            body = m["Body"]
            out.append(
                SqsReceived(
                    message=QueueMessage.from_json(body),
                    receipt_handle=m["ReceiptHandle"],
                    attributes=m.get("Attributes") or {},
                )
            )
        return out

    def delete(self, receipt_handle: str) -> None:
        self._sqs.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt_handle)


class SqsDlq(SqsQueue):
    pass
