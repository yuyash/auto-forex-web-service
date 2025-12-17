from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Strategy(ABC):
    """Runtime strategy interface used by Celery tasks.

    The task runners persist and pass `state` as a JSON-serializable dict.
    Implementations should treat dicts as an I/O boundary and use typed
    models internally.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.raw_config = config

    @abstractmethod
    def on_tick(
        self, *, tick: dict[str, Any], state: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        raise NotImplementedError

    def on_start(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return state, []

    def on_pause(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return state, []

    def on_resume(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return state, []

    def on_stop(self, *, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return state, []
