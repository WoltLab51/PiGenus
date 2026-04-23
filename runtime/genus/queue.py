"""Task queue for PiGenus.

FIFO queue persisted to data/queue.json.  All mutations are written to disk
immediately so no tasks are lost on an unexpected restart.
"""

import json
import os
import uuid
from typing import Optional

# Resolve data/ relative to this file's parent directory (runtime/)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
QUEUE_FILE = os.path.join(DATA_DIR, "queue.json")


class TaskQueue:
    """FIFO queue with JSON persistence.

    Each task is a dict with the keys:
        id       – unique UUID string
        type     – task type string (e.g. "echo", "noop")
        payload  – arbitrary dict of task parameters
        status   – one of "pending", "processing", "done", "failed"
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._queue: list = []
        self.load()

    def load(self):
        """Load queue from disk; start with an empty list when absent."""
        if os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, "r") as fh:
                self._queue = json.load(fh)
        else:
            self._queue = []

    def save(self):
        """Persist current queue state to disk."""
        with open(QUEUE_FILE, "w") as fh:
            json.dump(self._queue, fh, indent=2)

    def enqueue(self, task_type: str, payload: Optional[dict] = None) -> dict:
        """Add a new task and return it."""
        task = {
            "id": str(uuid.uuid4()),
            "type": task_type,
            "payload": payload or {},
            "status": "pending",
        }
        self._queue.append(task)
        self.save()
        return task

    def dequeue(self) -> Optional[dict]:
        """Pop the next pending task (sets status to "processing")."""
        for task in self._queue:
            if task["status"] == "pending":
                task["status"] = "processing"
                self.save()
                return task
        return None

    def mark_done(self, task_id: str, result: Optional[dict] = None):
        """Mark a task as successfully completed."""
        for task in self._queue:
            if task["id"] == task_id:
                task["status"] = "done"
                task["result"] = result or {}
                break
        self.save()

    def mark_failed(self, task_id: str, reason: str = ""):
        """Mark a task as failed."""
        for task in self._queue:
            if task["id"] == task_id:
                task["status"] = "failed"
                task["reason"] = reason
                break
        self.save()

    def pending_count(self) -> int:
        """Return the number of tasks still waiting to be processed."""
        return sum(1 for t in self._queue if t["status"] == "pending")

    def __len__(self) -> int:
        return len(self._queue)
