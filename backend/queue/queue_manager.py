import asyncio
from itertools import count
from uuid import uuid4


class QueueManager:
    """In-memory priority queue for pending requests."""

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._counter = count()

    async def enqueue(self, priority_score: int, payload: dict) -> str:
        """Add a request payload to the queue and return its queue id."""
        queue_id = str(uuid4())
        queued_payload = payload | {"queue_id": queue_id}
        await self._queue.put((-priority_score, next(self._counter), queue_id, queued_payload))
        return queue_id

    async def dequeue(self) -> dict | None:
        """Return the next queued payload, or None when the queue is empty."""
        if self._queue.empty():
            return None

        _, _, _, payload = await self._queue.get()
        return payload

    def size(self) -> int:
        """Return the current number of queued requests."""
        return self._queue.qsize()
