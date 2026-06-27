"""Shared game adapter models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

MapView = Literal["medium", "wide", "max"]


@dataclass(frozen=True, slots=True)
class GameAction:
    """Telegram-friendly action exposed by a game response."""

    id: str
    label: str
    command: str
    group: str = "context"


@dataclass(frozen=True, slots=True)
class GameResponse:
    """Result returned by any game adapter implementation."""

    state: dict[str, Any]
    screen: str
    log: list[str] = field(default_factory=list)
    status: dict[str, Any] = field(default_factory=dict)
    actions: list[GameAction] = field(default_factory=list)


class GameAdapter(Protocol):
    """Stable boundary between bot/session code and game implementation."""

    def start(
        self,
        state: dict[str, Any] | None = None,
        map_view: MapView = "wide",
    ) -> GameResponse: ...

    def restart(self, map_view: MapView = "wide") -> GameResponse: ...

    def apply_command(
        self,
        state: dict[str, Any] | None,
        command: str,
        map_view: MapView = "wide",
    ) -> GameResponse: ...
