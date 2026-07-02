"""Application services used by Telegram handlers."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, cast

from tglarn_game import GameResponse
from tglarn_game.models import GameAdapter

from .config import MapView
from .errors import SessionConflictError

_DEFAULT_ACTIVE_SESSION_TTL_SECONDS = 180.0
_ENGINE_ERROR_MESSAGE = "The game engine encountered an error. State was not advanced."
_SESSION_CONFLICT_MESSAGE = (
    "The game state changed before this action completed. Use the latest game screen."
)
logger = logging.getLogger(__name__)
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

    async def get_session(self, telegram_user_id: int) -> dict[str, Any] | None: ...

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
        expected_state_version: int,
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
    _adapter_slots: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(4),
        init=False,
        repr=False,
    )
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
        try:
            response = await self._run_adapter_call(
                self.game_adapter.start,
                _session_engine_state(session),
                map_view=map_view,
            )
        except Exception:
            logger.exception("Game adapter failed while starting a session")
            return _adapter_error_response(session, map_view)
        return await self._save_or_conflict_response(
            actor,
            telegram_user_id,
            session,
            response,
            "resume",
            map_view,
        )

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
        try:
            response = await self._run_adapter_call(
                self.game_adapter.start,
                {"character": character},
                map_view=map_view,
            )
        except Exception:
            logger.exception("Game adapter failed while creating a character")
            return _adapter_error_response(session, map_view)
        response = GameResponse(
            state=response.state,
            screen=response.screen,
            log=[f"{character['gender'].title()} {character['class']} enters Larn."] + response.log,
            status=response.status,
            actions=response.actions,
        )
        return await self._save_or_conflict_response(
            actor,
            telegram_user_id,
            session,
            response,
            f"new_character:{character['class']}:{character['gender']}",
            map_view,
        )

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
        try:
            return await self._run_adapter_call(
                self.game_adapter.start,
                _session_engine_state(session),
                map_view=map_view,
            )
        except Exception:
            logger.exception("Game adapter failed while loading current game")
            return _adapter_error_response(session, map_view)

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
        try:
            response = await self._run_adapter_call(self.game_adapter.restart, map_view=map_view)
        except Exception:
            logger.exception("Game adapter failed while restarting a session")
            return _adapter_error_response(session, map_view)
        return await self._save_or_conflict_response(
            actor,
            telegram_user_id,
            session,
            response,
            "restart",
            map_view,
        )

    async def apply_command(self, telegram_user_id: int, command: str) -> GameResponse:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._apply_command(actor, telegram_user_id, command),
        )

    async def active_game_message_matches(
        self,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> bool:
        return await self._with_actor(
            telegram_user_id,
            lambda actor: self._active_game_message_matches(
                actor,
                telegram_user_id,
                chat_id,
                message_id,
            ),
        )

    async def _active_game_message_matches(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> bool:
        session = await self.store.get_session(telegram_user_id)
        if session is None:
            session = await self._ensure_session(actor, telegram_user_id)
        else:
            actor.session = session
        matches = _active_game_message_matches(session, chat_id, message_id)
        logger.debug(
            "Validated active game message for Telegram user %s: "
            "incoming_chat_id=%s incoming_message_id=%s "
            "active_chat_id=%s active_message_id=%s matches=%s",
            telegram_user_id,
            chat_id,
            message_id,
            session.get("active_game_chat_id"),
            session.get("active_game_message_id"),
            matches,
        )
        return matches

    async def _apply_command(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        command: str,
    ) -> GameResponse:
        session = await self._ensure_session(actor, telegram_user_id)
        map_view = self._session_map_view(session)
        try:
            response = await self._run_adapter_call(
                self.game_adapter.apply_command,
                _session_engine_state(session),
                command,
                map_view=map_view,
            )
        except Exception:
            logger.exception("Game adapter failed while applying command")
            return _adapter_error_response(session, map_view)
        return await self._save_or_conflict_response(
            actor,
            telegram_user_id,
            session,
            response,
            command,
            map_view,
        )

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
        try:
            response = await self._run_adapter_call(
                self.game_adapter.start,
                _session_engine_state(session),
                map_view=view,
            )
        except Exception:
            logger.exception("Game adapter failed while changing map view")
            return _adapter_error_response(session, view)
        response = GameResponse(
            state=response.state,
            screen=response.screen,
            log=[f"Display size set to {view}."] + response.log,
            status=response.status,
            actions=response.actions,
        )
        return await self._save_or_conflict_response(
            actor,
            telegram_user_id,
            session,
            response,
            f"set_display_size:{view}",
            view,
        )

    async def _save_game_response(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        expected_state_version: int,
        response: GameResponse,
        input_text: str,
    ) -> None:
        actor.session = await self.store.save_game_response(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
            expected_state_version=expected_state_version,
            engine_state=response.state,
            screen=response.screen,
            log=response.log,
            status=response.status,
            input_text=input_text,
        )

    async def _save_or_conflict_response(
        self,
        actor: _PlayerActor,
        telegram_user_id: int,
        session: dict[str, Any],
        response: GameResponse,
        input_text: str,
        map_view: MapView,
    ) -> GameResponse:
        try:
            await self._save_game_response(
                actor,
                telegram_user_id,
                _session_state_version(session),
                response,
                input_text,
            )
        except SessionConflictError:
            logger.info("Rejected stale session write for Telegram user %s", telegram_user_id)
            return _session_conflict_response(session, map_view)
        return response

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

    async def _run_adapter_call(
        self,
        operation: Callable[..., _T],
        *args: Any,
        **kwargs: Any,
    ) -> _T:
        async with self._adapter_slots:
            return await asyncio.to_thread(operation, *args, **kwargs)

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


def _session_state_version(session: dict[str, Any]) -> int:
    value = session.get("state_version", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _adapter_error_response(session: dict[str, Any], map_view: MapView) -> GameResponse:
    return _safe_session_response(
        session,
        map_view,
        _ENGINE_ERROR_MESSAGE,
        {"adapter_error": True},
    )


def _session_conflict_response(session: dict[str, Any], map_view: MapView) -> GameResponse:
    return _safe_session_response(
        session,
        map_view,
        _SESSION_CONFLICT_MESSAGE,
        {"session_conflict": True},
    )


def _safe_session_response(
    session: dict[str, Any],
    map_view: MapView,
    message: str,
    extra_status: dict[str, Any],
) -> GameResponse:
    state = session.get("engine_state")
    if not isinstance(state, dict):
        state = {}
    status = session.get("last_status")
    if not isinstance(status, dict):
        status = {}
    screen = session.get("last_screen")
    if not isinstance(screen, str) or not screen:
        screen = "Game engine error."
    return GameResponse(
        state=state,
        screen=screen,
        log=[message],
        status=status | {"map_view": map_view, **extra_status},
    )


def _active_game_message_matches(
    session: dict[str, Any],
    chat_id: int,
    message_id: int,
) -> bool:
    active_message_id = session.get("active_game_message_id")
    if active_message_id is None:
        return True
    active_chat_id = session.get("active_game_chat_id")
    return active_message_id == message_id and (
        active_chat_id is None or active_chat_id == chat_id
    )


def _character_state(character_class: str, gender: str) -> dict[str, str]:
    normalized_gender = gender if gender in {"male", "female", "nonbinary"} else "male"
    spouse_gender = "male" if normalized_gender == "female" else "female"
    return {
        "name": "Tglarn",
        "class": character_class,
        "gender": normalized_gender,
        "spouse_gender": spouse_gender,
    }
