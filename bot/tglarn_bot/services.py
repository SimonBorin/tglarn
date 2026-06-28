"""Application services used by Telegram handlers."""

from dataclasses import dataclass
from typing import Any, Protocol, cast

from tglarn_game import GameResponse
from tglarn_game.models import GameAdapter

from .config import MapView


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
class GameSessionService:
    """Session boundary between Telegram handlers and persistence/game logic."""

    store: SessionStore
    game_adapter: GameAdapter
    default_map_view: MapView

    async def ensure_session(
        self,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        return await self.store.ensure_session(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
            username=username,
            display_name=display_name,
        )

    async def start_game(
        self,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> GameResponse:
        session = await self.ensure_session(telegram_user_id, username, display_name)
        map_view = self._session_map_view(session)
        response = self.game_adapter.start(_session_engine_state(session), map_view=map_view)
        await self._save_game_response(telegram_user_id, response, "resume")
        return response

    async def needs_character_setup(
        self,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> bool:
        session = await self.ensure_session(telegram_user_id, username, display_name)
        return not _engine_state_has_started_game(session.get("engine_state"))

    async def start_new_character(
        self,
        telegram_user_id: int,
        character_class: str,
        gender: str,
    ) -> GameResponse:
        session = await self.ensure_session(telegram_user_id)
        if _engine_state_has_started_game(session.get("engine_state")):
            session = await self.store.restart_session(
                telegram_user_id=telegram_user_id,
                default_map_view=self.default_map_view,
            )
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
            telegram_user_id,
            response,
            f"new_character:{character['class']}:{character['gender']}",
        )
        return response

    async def prepare_new_character(self, telegram_user_id: int) -> dict[str, Any]:
        return await self.store.restart_session(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
        )

    async def current_game(self, telegram_user_id: int) -> GameResponse:
        session = await self.ensure_session(telegram_user_id)
        map_view = self._session_map_view(session)
        return self.game_adapter.start(_session_engine_state(session), map_view=map_view)

    async def restart_session(self, telegram_user_id: int) -> GameResponse:
        session = await self.store.restart_session(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
        )
        map_view = self._session_map_view(session)
        response = self.game_adapter.restart(map_view=map_view)
        await self._save_game_response(telegram_user_id, response, "restart")
        return response

    async def apply_command(self, telegram_user_id: int, command: str) -> GameResponse:
        session = await self.ensure_session(telegram_user_id)
        map_view = self._session_map_view(session)
        response = self.game_adapter.apply_command(
            _session_engine_state(session),
            command,
            map_view=map_view,
        )
        await self._save_game_response(telegram_user_id, response, command)
        return response

    async def set_active_game_message(
        self,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> dict[str, Any]:
        return await self.store.set_active_game_message(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def set_map_view(self, telegram_user_id: int, view: MapView) -> GameResponse:
        session = await self.store.set_map_view(
            telegram_user_id=telegram_user_id,
            view=view,
            default_map_view=self.default_map_view,
        )
        response = self.game_adapter.start(_session_engine_state(session), map_view=view)
        response = GameResponse(
            state=response.state,
            screen=response.screen,
            log=[f"Display size set to {view}."] + response.log,
            status=response.status,
            actions=response.actions,
        )
        await self._save_game_response(telegram_user_id, response, f"set_display_size:{view}")
        return response

    async def _save_game_response(
        self,
        telegram_user_id: int,
        response: GameResponse,
        input_text: str,
    ) -> None:
        await self.store.save_game_response(
            telegram_user_id=telegram_user_id,
            default_map_view=self.default_map_view,
            engine_state=response.state,
            screen=response.screen,
            log=response.log,
            status=response.status,
            input_text=input_text,
        )

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
    state = session.get("engine_state")
    if not isinstance(state, dict) or "pending_prompt" in state:
        return state

    last_status = session.get("last_status")
    if not isinstance(last_status, dict):
        return state

    pending_prompt = last_status.get("pending_prompt")
    if not isinstance(pending_prompt, dict):
        return state

    return state | {"pending_prompt": pending_prompt}


def _character_state(character_class: str, gender: str) -> dict[str, str]:
    normalized_gender = gender if gender in {"male", "female", "nonbinary"} else "male"
    spouse_gender = "male" if normalized_gender == "female" else "female"
    return {
        "name": "Tglarn",
        "class": character_class,
        "gender": normalized_gender,
        "spouse_gender": spouse_gender,
    }
