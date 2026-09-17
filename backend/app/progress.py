import asyncio
from dataclasses import dataclass


@dataclass
class ProgressEvent:
    stage: str  # "cloning" | "parsing" | "saving" | "done" | "error"
    message: str


class ProgressBroker:
    """In-memory pub/sub for analysis progress, keyed by repo_id.

    Keeps the last event per repo_id so a subscriber that connects after the
    mutation has already started (or finished) still gets the current state
    instead of hanging forever waiting for a stage it missed.
    """

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._last_event: dict[str, ProgressEvent] = {}

    def subscribe(self, repo_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(repo_id, []).append(queue)
        last = self._last_event.get(repo_id)
        if last is not None:
            queue.put_nowait(last)
        return queue

    def unsubscribe(self, repo_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(repo_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs:
            self._subscribers.pop(repo_id, None)

    async def publish(self, repo_id: str, event: ProgressEvent) -> None:
        self._last_event[repo_id] = event
        for queue in list(self._subscribers.get(repo_id, [])):
            await queue.put(event)


broker = ProgressBroker()
