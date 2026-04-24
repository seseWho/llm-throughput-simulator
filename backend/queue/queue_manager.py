import asyncio
import time
from itertools import count
from uuid import uuid4


class QueueManager:
    """In-memory priority queue for pending requests."""

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._counter = count()
        self.results: dict[str, dict] = {}

    async def enqueue(self, priority_score: int, payload: dict) -> str:
        """Add a request payload to the queue and return its queue id."""
        queue_id = str(uuid4())
        queued_payload = payload | {"queue_id": queue_id, "enqueued_at": time.monotonic()}
        await self._queue.put((-priority_score, next(self._counter), queue_id, queued_payload))
        self.results[queue_id] = {
            "request_id": queue_id,
            "status": "queued",
            "message": "Request queued for background processing",
        }
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

    def set_result(self, request_id: str, result: dict) -> None:
        """Store a completed or intermediate request result."""
        self.results[request_id] = result

    def get_result(self, request_id: str) -> dict | None:
        """Return a stored request result by id."""
        return self.results.get(request_id)

    def mark_failed(self, request_id: str, error: str) -> None:
        """Store a failed request result."""
        self.results[request_id] = {
            "request_id": request_id,
            "status": "failed",
            "message": error,
        }

    def completed_count(self) -> int:
        """Return the number of completed requests."""
        return sum(1 for result in self.results.values() if result.get("status") == "completed")

    def failed_count(self) -> int:
        """Return the number of failed requests."""
        return sum(1 for result in self.results.values() if result.get("status") == "failed")
