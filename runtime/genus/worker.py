"""BasicWorker agent for PiGenus.

Pulls the next pending task from the queue, processes it, and records the
outcome in the task and agent ledgers.

Supported task types:
    echo     – returns the message from payload back in the result
    noop     – does nothing; returns {"noop": True}
    classify – resolves a task_type string to a problem category
"""

import time

from .queue import TaskQueue
from .ledger import Ledger
from .logger import get_logger
from .matcher import match
from .problem_matrix import ProblemMatrix

logger = get_logger()

# Module-level ProblemMatrix instance used by the classify handler.
_problem_matrix_instance = ProblemMatrix()

# Efficiency normalisation baseline: tasks completing in this many milliseconds
# score 0.0; tasks completing in 0 ms score 1.0.
_EFFICIENCY_BASELINE_MS = 10_000.0

# Neutral placeholder scores used when no measurement is available.
_NEUTRAL_RESOURCE_SCORE = 0.5
_NEUTRAL_LEARNING_SCORE = 0.5


class BasicWorker:
    """Minimal worker: handles 'echo', 'noop', and 'classify' task types."""

    NAME = "basic_worker"

    def __init__(self, queue: TaskQueue, task_ledger: Ledger, agent_ledger: Ledger):
        self._queue = queue
        self._task_ledger = task_ledger
        self._agent_ledger = agent_ledger

    def run_once(self) -> bool:
        """Process one pending task.

        Returns True when a task was found and processed (regardless of
        success/failure), False when the queue was empty.
        """
        task = self._queue.dequeue()
        if task is None:
            return False

        logger.info(
            "Worker picked up task %s (type=%s)", task["id"], task["type"]
        )
        self._agent_ledger.record(
            {
                "event": "task_start",
                "agent": self.NAME,
                "task_id": task["id"],
                "task_type": task["type"],
            }
        )

        # Resolve category via matcher (same logic as orchestrator).
        category, _agent = match(task)

        t_start = time.monotonic()
        try:
            result = self._process(task)
            duration_ms = (time.monotonic() - t_start) * 1000.0
            self._queue.mark_done(task["id"], result)
            self._task_ledger.record(
                {
                    "event": "task_done",
                    "task_id": task["id"],
                    "task_type": task["type"],
                    "category": category,
                    "agent_name": self.NAME,
                    "result": result,
                    "success_score": 1.0,
                    "efficiency_score": max(0.0, min(1.0, 1.0 - duration_ms / _EFFICIENCY_BASELINE_MS)),
                    "stability_score": 1.0,
                    "resource_score": _NEUTRAL_RESOURCE_SCORE,
                    "learning_score": _NEUTRAL_LEARNING_SCORE,
                    "duration_ms": duration_ms,
                }
            )
            logger.info("Task %s done: %s", task["id"], result)
        except Exception as exc:
            duration_ms = (time.monotonic() - t_start) * 1000.0
            reason = str(exc)
            self._queue.mark_failed(task["id"], reason)
            self._task_ledger.record(
                {
                    "event": "task_failed",
                    "task_id": task["id"],
                    "task_type": task["type"],
                    "category": category,
                    "agent_name": self.NAME,
                    "reason": reason,
                    "success_score": 0.0,
                    "efficiency_score": max(0.0, min(1.0, 1.0 - duration_ms / _EFFICIENCY_BASELINE_MS)),
                    "stability_score": 0.0,
                    "resource_score": _NEUTRAL_RESOURCE_SCORE,
                    "learning_score": _NEUTRAL_LEARNING_SCORE,
                    "duration_ms": duration_ms,
                }
            )
            logger.error("Task %s failed: %s", task["id"], reason)

        return True

    def _process(self, task: dict) -> dict:
        """Dispatch to the appropriate handler; raise on unknown type."""
        task_type = task["type"]
        payload = task.get("payload", {})

        if task_type == "echo":
            message = payload.get("message", "")
            return {"echo": message}
        elif task_type == "noop":
            return {"noop": True}
        elif task_type == "classify":
            task_type_to_classify = payload.get("task_type", "")
            category = _problem_matrix_instance.categorize(task_type_to_classify)
            return {"category": category, "task_type": task_type_to_classify}
        else:
            raise ValueError(f"Unknown task type: {task_type!r}")
