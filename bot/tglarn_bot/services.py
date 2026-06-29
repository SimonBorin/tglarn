"""Application services used by Telegram handlers."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, cast

from tglarn_game import GameResponse
from tglarn_game.models import GameAdapter

from .config import MapView

_DEFAULT_ACTIVE_SESSION_TTL_SECONDS = 180.0
_T = TypeVar("_T")


class SessionStore(Protocol):
    async def ensure_session(
        self,
        telegram_user_id: int,
        default_map_view: MapView,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]: ...

    async def restart_session(
        self,
        telegram_user_id: int,
        default_map_view: MapView,
    ) -> dict[str, Any]: ...

    async def set_map_view(
        self,
        telegram_user_id: int,
        view: MapView,
        default_map_view: MapView,
    ) -> dict[str, Any]: ...

    async def set_active_game_message(
        self,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> dict[str, Any]: ...

    async def save_game_response(
        self,
        telegram_user_id: int,
        default_map_view: MapView,
        engine_state: dict[str, Any],
        screen: str,
        log: list[str],
        status: dict[str, Any],
        input_text: str | None = None,
    ) -> dict[str, Any]: ...


@dataclass(slots=True)
class _PlayerActor:
    telegram_user_id: int
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    session: dict[str, Any] | None = None
    expires_at: float = 0.0

    def touch(self, now: float, ttl_seconds: float) -> None:
        self.expires_at = now + ttl_seconds


@dataclass(slots=True)
class GameSessionService:
    """Session boundary between Telegram handlers and persistence/game logic."""

    store: SessionStore
    game_adapter: GameAdapter
    default_map_view: MapView
    active_session_ttl_seconds: float = _DEFAULT_ACTIVE_SESSION_TTL_SECONDS
    _actors: dict[int, _PlayerActor] = field(default_factory=dict, init=False, repr=False)
    _clock: Callable[[], float] = field(default=time.monotonic, repr=False)

    async def ensure_session(
        self,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._ensure_session(
                actor,
                telegram_user_id,
                username=username,
                display_name=display_name,
            ),
        )

    async def start_game(
        self,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> GameResponse:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._start_game(
                actor,
                telegram_user_id,
                username=username,
                display_name=display_name,
            ),
        )

    async def _start_game(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> GameResponse:
        session = await self._ensure_session(
            actor,
            telegram_user_id,
            username=username,
            display_name=display_name,
        )
        map_view = self._session_map_view(session)
        response = self.game_adapter.start(_session_engine_state(session), map_view=map_view)
        await self._save_game_response(actor, telegram_user_id, response, "resume")
        return response

    async def needs_character_setup(
        self,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> bool:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._needs_character_setup(
                actor,
                telegram_user_id,
                username=username,
                display_name=display_name,
            ),
        )

    async def _needs_character_setup(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> bool:
        session = await self._ensure_session(
            actor,
            telegram_user_id,
            username=username,
            display_name=display_name,
        )
        return not _engine_state_has_started_game(session.get("engine_state"))

    async def start_new_character(
        self,
        telegram_user_id: int,
        character_class: str,
        gender: str,
    ) -> GameResponse:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._start_new_character(
                actor,
                telegram_user_id,
                character_class,
                gender,
            ),
        )

    async def _start_new_character(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        character_class: str,
        gender: str,
    ) -> GameResponse:
        session = await self._ensure_session(actor, telegram_user_id)
        if _engine_state_has_started_game(session.get("engine_state")):
            session = await self.store.restart_session(
                telegram_user_id=telegram_user_id,
                default_map_view=self.default_map_view,
            )
            actor.session = session
        map_view = self._session_map_view(session)
        character = _character_state(character_class, gender)
        response = self.game_adapter.start({"character": character}, map_view=map_view)
        response = GameResponse(
            state=response.state,
            screen=response.screen,
            log=[f"{character['gender'].title()} {character['class']} enters Larn."] + response.log,
            status=response.status,
            actions=response.actions,
        )
        await self._save_game_response(
            actor,
            telegram_user_id,
            response,
            f"new_character:{character['class']}:{character['gender']}",
        )
        return response

    async def prepare_new_character(self, telegram_user_id: int) -> dict[str, Any]:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._prepare_new_character(actor, telegram_user_id),
        )

    async def _prepare_new_character(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
    ) -> dict[str, Any]:
        session = await self.store.restart_session(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
        )
        actor.session = session
        return session

    async def current_game(self, telegram_user_id: int) -> GameResponse:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._current_game(actor, telegram_user_id),
        )

    async def _current_game(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
    ) -> GameResponse:
        session = await self._ensure_session(actor, telegram_user_id)
        map_view = self._session_map_view(session)
        return self.game_adapter.start(_session_engine_state(session), map_view=map_view)

    async def restart_session(self, telegram_user_id: int) -> GameResponse:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._restart_session(actor, telegram_user_id),
        )

    async def _restart_session(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
    ) -> GameResponse:
        session = await self.store.restart_session(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
        )
        actor.session = session
        map_view = self._session_map_view(session)
        response = self.game_adapter.restart(map_view=map_view)
        await self._save_game_response(actor, telegram_user_id, response, "restart")
        return response

    async def apply_command(self, telegram_user_id: int, command: str) -> GameResponse:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._apply_command(actor, telegram_user_id, command),
        )

    async def _apply_command(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        command: str,
    ) -> GameResponse:
        session = await self._ensure_session(actor, telegram_user_id)
        map_view = self._session_map_view(session)
        response = self.game_adapter.apply_command(
            _session_engine_state(session),
            command,
            map_view=map_view,
        )
        await self._save_game_response(actor, telegram_user_id, response, command)
        return response

    async def set_active_game_message(
        self,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> dict[str, Any]:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._set_active_game_message(
                actor,
                telegram_user_id,
                chat_id,
                message_id,
            ),
        )

    async def _set_active_game_message(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> dict[str, Any]:
        session = await self.store.set_active_game_message(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
        )
        actor.session = session
        return session

    async def set_map_view(self, telegram_user_id: int, view: MapView) -> GameResponse:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._set_map_view(actor, telegram_user_id, view),
        )

    async def _set_map_view(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        view: MapView,
    ) -> GameResponse:
        session = await self.store.set_map_view(
            telegram_user_id=telegram_user_id,
            view=view,
            default_map_view=self.default_map_view,
        )
        actor.session = session
        response = self.game_adapter.start(_session_engine_state(session), map_view=view)
        response = GameResponse(
            state=response.state,
            screen=response.screen,
            log=[f"Display size set to {view}."] + response.log,
            status=response.status,
            actions=response.actions,
        )
        await self._save_game_response(
            actor,
            telegram_user_id,
            response,
            f"set_display_size:{view}",
        )
        return response

    async def _save_game_response(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        response: GameResponse,
        input_text: str,
    ) -> None:
        actor.session = await self.store.save_game_response(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
            engine_state=response.state,
            screen=response.screen,
            log=response.log,
            status=response.status,
            input_text=input_text,
        )

    async def close(self) -> None:
        self._actors.clear()

    async def _ensure_session(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        if actor.session is not None and username is None and display_name is None:
            return actor.session
        actor.session = await self.store.ensure_session(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
            username=username,
            display_name=display_name,
        )
        return actor.session

    async def _with_actor(
        self,
        telegram_user_id: int,
        operation: Callable[[_PlayerActor], Awaitable[_T]],
    ) -> _T:
        actor = self._actor_for(telegram_user_id)
        async with actor.lock:
            actor.touch(self._clock(), self.active_session_ttl_seconds)
            result = await operation(actor)
            actor.touch(self._clock(), self.active_session_ttl_seconds)
            return result

    def _actor_for(self, telegram_user_id: int) -> _PlayerActor:
        now = self._clock()
        self._drop_expired_actors(now)
        actor = self._actors.get(telegram_user_id)
        if actor is None:
            actor = _PlayerActor(telegram_user_id=telegram_user_id)
            self._actors[telegram_user_id] = actor
        actor.touch(now, self.active_session_ttl_seconds)
        return actor

    def _drop_expired_actors(self, now: float) -> None:
        expired = [
            telegram_user_id
            for telegram_user_id, actor in self._actors.items()
            if actor.expires_at <= now and not actor.lock.locked()
        ]
        for telegram_user_id in expired:
            del self._actors[telegram_user_id]

    def _session_map_view(self, session: dict[str, Any]) -> MapView:
        value = session.get("map_view", self.default_map_view)
        if value in {"compact", "normal"}:
            return "medium"
        if value in {"desktop", "max_size", "maximum"}:
            return "max"
        if value in {"medium", "wide", "max"}:
            return cast(MapView, value)
        return self.default_map_view


def _engine_state_has_started_game(state: Any) -> bool:
    if not isinstance(state, dict):
        return False
    if state.get("adapter") == "placeholder":
        return True
    return isinstance(state.get("save_blob_b64"), str) and bool(state.get("save_blob_b64"))


def _session_engine_state(session: dict[str, Any]) -> Any:
    return session.get("engine_state")


def _character_state(character_class: str, gender: str) -> dict[str, str]:
    normalized_gender = gender if gender in {"male", "female", "nonbinary"} else "male"
    spouse_gender = "male" if normalized_gender == "female" else "female"
    return {
        "name": "Tglarn",
        "class": character_class,
        "gender": normalized_gender,
        "spouse_gender": spouse_gender,
    }
