from typing import Any

import pytest
from tglarn_bot.services import GameSessionService
from tglarn_game import GameResponse, PlaceholderGameAdapter


class CapturingGameAdapter:
    def __init__(self) -> None:
        self.started_state: dict[str, Any] | None = None

    def start(self, state: dict[str, Any] | None = None, map_view: str = "wide") -> GameResponse:
        self.started_state = state
        return GameResponse(
            state={"adapter": "captured", "character": state["character"], "save_blob_b64": "save"},
            screen="screen",
            log=["A new run begins."],
            status={"map_view": map_view},
        )

    def restart(self, map_view: str = "wide") -> GameResponse:
        return self.start({"character": {"class": "Geek", "gender": "male"}}, map_view)

    def apply_command(
        self,
        state: dict[str, Any] | None,
        command: str,
        map_view: str = "wide",
    ) -> GameResponse:
        return self.start(state, map_view)


class FakeSessionStore:
    def __init__(self) -> None:
        self.session: dict[str, Any] = {"engine_state": {}}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def ensure_session(
        self,
        telegram_user_id: int,
        default_map_view: str,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "telegram_user_id": telegram_user_id,
            "default_map_view": default_map_view,
            "username": username,
            "display_name": display_name,
        }
        self.calls.append(("ensure_session", payload))
        self.session.setdefault("telegram_user_id", telegram_user_id)
        self.session.setdefault("map_view", default_map_view)
        return self.session

    async def restart_session(
        self,
        telegram_user_id: int,
        default_map_view: str,
    ) -> dict[str, Any]:
        payload = {
            "telegram_user_id": telegram_user_id,
            "default_map_view": default_map_view,
        }
        self.calls.append(("restart_session", payload))
        self.session = {"telegram_user_id": telegram_user_id, "engine_state": {}}
        return self.session

    async def set_map_view(
        self,
        telegram_user_id: int,
        view: str,
        default_map_view: str,
    ) -> dict[str, Any]:
        payload = {
            "telegram_user_id": telegram_user_id,
            "view": view,
            "default_map_view": default_map_view,
        }
        self.calls.append(("set_map_view", payload))
        self.session["map_view"] = view
        return payload

    async def set_active_game_message(
        self,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> dict[str, Any]:
        payload = {
            "telegram_user_id": telegram_user_id,
            "chat_id": chat_id,
            "message_id": message_id,
        }
        self.calls.append(("set_active_game_message", payload))
        self.session["active_game_chat_id"] = chat_id
        self.session["active_game_message_id"] = message_id
        return self.session

    async def save_game_response(
        self,
        telegram_user_id: int,
        default_map_view: str,
        engine_state: dict[str, Any],
        screen: str,
        log: list[str],
        status: dict[str, Any],
        input_text: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "telegram_user_id": telegram_user_id,
            "default_map_view": default_map_view,
            "engine_state": engine_state,
            "screen": screen,
            "log": log,
            "status": status,
            "input_text": input_text,
        }
        self.calls.append(("save_game_response", payload))
        self.session["engine_state"] = engine_state
        self.session["last_screen"] = screen
        self.session["last_log"] = log
        self.session["last_status"] = status
        return self.session


@pytest.mark.asyncio
async def test_service_passes_user_profile_to_store() -> None:
    store = FakeSessionStore()
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    result = await service.ensure_session(42, username="player", display_name="Player One")

    assert result["telegram_user_id"] == 42
    assert result["map_view"] == "wide"
    assert store.calls[0] == (
        "ensure_session",
        {
            "telegram_user_id": 42,
            "default_map_view": "wide",
            "username": "player",
            "display_name": "Player One",
        },
    )


@pytest.mark.asyncio
async def test_service_returns_current_game_without_saving_turn() -> None:
    store = FakeSessionStore()
    store.session["engine_state"] = {"adapter": "placeholder", "x": 2, "y": 1}
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    response = await service.current_game(1001)

    assert response.state["x"] == 2
    assert response.log == ["Game loaded."]
    assert store.calls[-1][0] == "ensure_session"


@pytest.mark.asyncio
async def test_service_restarts_only_requested_user_and_saves_new_state() -> None:
    store = FakeSessionStore()
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    response = await service.restart_session(1001)

    assert response.state["adapter"] == "placeholder"
    assert response.state["turn"] == 0
    assert store.calls[0][0] == "restart_session"
    assert store.calls[1][0] == "save_game_response"
    assert store.calls[1][1]["telegram_user_id"] == 1001
    assert store.calls[1][1]["input_text"] == "restart"


@pytest.mark.asyncio
async def test_service_starts_new_character_with_selected_class_and_gender() -> None:
    store = FakeSessionStore()
    adapter = CapturingGameAdapter()
    service = GameSessionService(
        store=store,
        game_adapter=adapter,
        default_map_view="wide",
    )

    response = await service.start_new_character(1001, "Wizard", "female")

    assert adapter.started_state == {
        "character": {
            "name": "Tglarn",
            "class": "Wizard",
            "gender": "female",
            "spouse_gender": "male",
        }
    }
    assert response.state["character"]["class"] == "Wizard"
    assert response.log[0] == "Female Wizard enters Larn."
    assert store.calls[0][0] == "ensure_session"
    assert store.calls[1][0] == "save_game_response"
    assert store.calls[1][1]["input_text"] == "new_character:Wizard:female"


@pytest.mark.asyncio
async def test_service_clears_existing_save_before_new_character() -> None:
    store = FakeSessionStore()
    store.session["engine_state"] = {"save_blob_b64": "old-save"}
    adapter = CapturingGameAdapter()
    service = GameSessionService(
        store=store,
        game_adapter=adapter,
        default_map_view="wide",
    )

    response = await service.start_new_character(1001, "Elf", "male")

    assert response.state["character"]["class"] == "Elf"
    assert [call[0] for call in store.calls[:3]] == [
        "ensure_session",
        "restart_session",
        "save_game_response",
    ]


@pytest.mark.asyncio
async def test_service_prepares_new_character_by_clearing_session() -> None:
    store = FakeSessionStore()
    store.session["engine_state"] = {"save_blob_b64": "old-save"}
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    result = await service.prepare_new_character(1001)

    assert result["engine_state"] == {}
    assert store.calls == [
        ("restart_session", {"telegram_user_id": 1001, "default_map_view": "wide"})
    ]


@pytest.mark.asyncio
async def test_service_sets_map_view_for_requested_user() -> None:
    store = FakeSessionStore()
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    response = await service.set_map_view(1001, "max")

    assert "Display:" not in response.screen
    assert response.status["map_view"] == "max"
    assert response.status["viewport"] == {"width": 52, "height": 23}
    assert store.calls[-1][0] == "save_game_response"
    assert store.calls[-1][1]["input_text"] == "set_display_size:max"


@pytest.mark.asyncio
async def test_service_applies_command_and_persists_state() -> None:
    store = FakeSessionStore()
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    response = await service.apply_command(1001, "east")

    assert isinstance(response, GameResponse)
    assert response.state["x"] == 2
    assert response.state["turn"] == 1
    assert store.session["engine_state"] == response.state
    assert store.calls[-1][1]["input_text"] == "east"


@pytest.mark.asyncio
async def test_service_remembers_active_game_message() -> None:
    store = FakeSessionStore()
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    result = await service.set_active_game_message(1001, chat_id=2002, message_id=3003)

    assert result["active_game_chat_id"] == 2002
    assert result["active_game_message_id"] == 3003
    assert store.calls[-1] == (
        "set_active_game_message",
        {"telegram_user_id": 1001, "chat_id": 2002, "message_id": 3003},
    )
