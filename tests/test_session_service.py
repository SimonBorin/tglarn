import asyncio
from copy import deepcopy
from typing import Any

import pytest
from tglarn_bot.errors import SessionConflictError
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


class CapturingApplyAdapter:
    def __init__(self) -> None:
        self.applied_state: dict[str, Any] | None = None
        self.applied_command: str | None = None

    def start(self, state: dict[str, Any] | None = None, map_view: str = "wide") -> GameResponse:
        return GameResponse(state=state or {}, screen="screen", status={"map_view": map_view})

    def restart(self, map_view: str = "wide") -> GameResponse:
        return self.start({}, map_view)

    def apply_command(
        self,
        state: dict[str, Any] | None,
        command: str,
        map_view: str = "wide",
    ) -> GameResponse:
        self.applied_state = state
        self.applied_command = command
        return GameResponse(
            state=state or {},
            screen="answered",
            status={"map_view": map_view},
        )


class AccumulatingApplyAdapter:
    def __init__(self) -> None:
        self.applied_states: list[dict[str, Any]] = []

    def start(self, state: dict[str, Any] | None = None, map_view: str = "wide") -> GameResponse:
        return GameResponse(state=state or {}, screen="screen", status={"map_view": map_view})

    def restart(self, map_view: str = "wide") -> GameResponse:
        return self.start({}, map_view)

    def apply_command(
        self,
        state: dict[str, Any] | None,
        command: str,
        map_view: str = "wide",
    ) -> GameResponse:
        current = deepcopy(state or {})
        self.applied_states.append(current)
        commands = [*current.get("commands", []), command]
        return GameResponse(
            state={"adapter": "captured", "commands": commands},
            screen="screen",
            status={"map_view": map_view},
        )


class FailingAdapter:
    def start(self, state: dict[str, Any] | None = None, map_view: str = "wide") -> GameResponse:
        raise RuntimeError("boom")

    def restart(self, map_view: str = "wide") -> GameResponse:
        raise RuntimeError("boom")

    def apply_command(
        self,
        state: dict[str, Any] | None,
        command: str,
        map_view: str = "wide",
    ) -> GameResponse:
        raise RuntimeError("boom")


class FakeSessionStore:
    def __init__(self) -> None:
        self.session: dict[str, Any] = {"engine_state": {}, "state_version": 0}
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
        self.session.setdefault("state_version", 0)
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
        self.session = {
            "telegram_user_id": telegram_user_id,
            "engine_state": {},
            "state_version": self.session.get("state_version", 0) + 1,
        }
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
        expected_state_version: int,
        engine_state: dict[str, Any],
        screen: str,
        log: list[str],
        status: dict[str, Any],
        input_text: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "telegram_user_id": telegram_user_id,
            "default_map_view": default_map_view,
            "expected_state_version": expected_state_version,
            "engine_state": engine_state,
            "screen": screen,
            "log": log,
            "status": status,
            "input_text": input_text,
        }
        self.calls.append(("save_game_response", payload))
        if self.session.get("state_version", 0) != expected_state_version:
            raise SessionConflictError("stale write")
        self.session["engine_state"] = engine_state
        self.session["last_screen"] = screen
        self.session["last_log"] = log
        self.session["last_status"] = status
        self.session["state_version"] = expected_state_version + 1
        return self.session


class CopyingSessionStore(FakeSessionStore):
    def __init__(self) -> None:
        super().__init__()
        self.ensure_count = 0
        self.session = {
            "telegram_user_id": 1001,
            "map_view": "wide",
            "state_version": 0,
            "engine_state": {"adapter": "captured", "commands": []},
        }

    async def ensure_session(
        self,
        telegram_user_id: int,
        default_map_view: str,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_count += 1
        await asyncio.sleep(0)
        return deepcopy(self.session)

    async def save_game_response(
        self,
        telegram_user_id: int,
        default_map_view: str,
        expected_state_version: int,
        engine_state: dict[str, Any],
        screen: str,
        log: list[str],
        status: dict[str, Any],
        input_text: str | None = None,
    ) -> dict[str, Any]:
        await asyncio.sleep(0)
        if self.session.get("state_version", 0) != expected_state_version:
            raise SessionConflictError("stale write")
        self.session["engine_state"] = deepcopy(engine_state)
        self.session["state_version"] = expected_state_version + 1
        return deepcopy(self.session)


class ConflictingSessionStore(FakeSessionStore):
    async def save_game_response(
        self,
        telegram_user_id: int,
        default_map_view: str,
        expected_state_version: int,
        engine_state: dict[str, Any],
        screen: str,
        log: list[str],
        status: dict[str, Any],
        input_text: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "save_game_response",
                {
                    "telegram_user_id": telegram_user_id,
                    "expected_state_version": expected_state_version,
                    "input_text": input_text,
                },
            )
        )
        raise SessionConflictError("stale write")


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
    assert store.calls[-1][1]["expected_state_version"] == 0
    assert store.session["state_version"] == 1


@pytest.mark.asyncio
async def test_service_returns_safe_response_when_adapter_fails() -> None:
    store = FakeSessionStore()
    store.session.update(
        {
            "engine_state": {"adapter": "relarn_process", "save_blob_b64": "saved"},
            "last_screen": "previous screen",
            "last_status": {"pending_prompt": {"kind": "choice"}},
        }
    )
    service = GameSessionService(
        store=store,
        game_adapter=FailingAdapter(),
        default_map_view="wide",
    )

    response = await service.apply_command(1001, "east")

    assert response.state == {"adapter": "relarn_process", "save_blob_b64": "saved"}
    assert response.screen == "previous screen"
    assert response.log == ["The game engine encountered an error. State was not advanced."]
    assert response.status["adapter_error"] is True
    assert response.status["pending_prompt"] == {"kind": "choice"}
    assert [call[0] for call in store.calls] == ["ensure_session"]


@pytest.mark.asyncio
async def test_service_returns_safe_response_on_optimistic_lock_conflict() -> None:
    store = ConflictingSessionStore()
    store.session.update(
        {
            "engine_state": {"adapter": "captured", "commands": []},
            "last_screen": "current screen",
            "last_status": {"screen_type": "map"},
        }
    )
    service = GameSessionService(
        store=store,
        game_adapter=AccumulatingApplyAdapter(),
        default_map_view="wide",
    )

    response = await service.apply_command(1001, "east")

    assert response.state == {"adapter": "captured", "commands": []}
    assert response.screen == "current screen"
    assert response.log == [
        "The game state changed before this action completed. Use the latest game screen."
    ]
    assert response.status["session_conflict"] is True
    assert store.session["engine_state"] == {"adapter": "captured", "commands": []}


@pytest.mark.asyncio
async def test_service_serializes_commands_for_one_player_actor() -> None:
    store = CopyingSessionStore()
    adapter = AccumulatingApplyAdapter()
    service = GameSessionService(
        store=store,
        game_adapter=adapter,
        default_map_view="wide",
    )

    await asyncio.gather(
        service.apply_command(1001, "east"),
        service.apply_command(1001, "west"),
    )

    assert store.session["engine_state"]["commands"] == ["east", "west"]
    assert adapter.applied_states == [
        {"adapter": "captured", "commands": []},
        {"adapter": "captured", "commands": ["east"]},
    ]
    assert store.ensure_count == 1


@pytest.mark.asyncio
async def test_service_reloads_session_after_actor_ttl_expires() -> None:
    current_time = 1000.0

    def clock() -> float:
        return current_time

    store = CopyingSessionStore()
    service = GameSessionService(
        store=store,
        game_adapter=AccumulatingApplyAdapter(),
        default_map_view="wide",
        active_session_ttl_seconds=180.0,
        _clock=clock,
    )

    await service.apply_command(1001, "east")
    await service.apply_command(1001, "west")
    assert store.ensure_count == 1

    current_time += 181.0
    await service.apply_command(1001, "north")

    assert store.ensure_count == 2
    assert store.session["engine_state"]["commands"] == ["east", "west", "north"]


@pytest.mark.asyncio
async def test_service_ignores_stale_pending_prompt_from_last_status() -> None:
    pending_prompt = {
        "question": "Do you (g) quaff it, (t) take it, or (n) do nothing?",
        "kind": "choice",
        "options": [
            {"key": "g", "label": "Quaff it"},
            {"key": "t", "label": "Take it"},
            {"key": "n", "label": "Do nothing"},
        ],
        "trigger_keys": ["l"],
        "base_save_blob_b64": "base-save",
    }
    store = FakeSessionStore()
    initial_state = {"adapter": "relarn_process", "save_blob_b64": "after-save"}
    store.session["engine_state"] = initial_state
    store.session["last_status"] = {"pending_prompt": pending_prompt}
    adapter = CapturingApplyAdapter()
    service = GameSessionService(
        store=store,
        game_adapter=adapter,
        default_map_view="wide",
    )

    await service.apply_command(1001, "t")

    assert adapter.applied_command == "t"
    assert adapter.applied_state == initial_state


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


@pytest.mark.asyncio
async def test_service_detects_stale_active_game_message() -> None:
    store = FakeSessionStore()
    store.session["active_game_chat_id"] = 2002
    store.session["active_game_message_id"] = 3003
    service = GameSessionService(
        store=store,
        game_adapter=PlaceholderGameAdapter(),
        default_map_view="wide",
    )

    assert await service.active_game_message_matches(1001, 2002, 3003)
    assert not await service.active_game_message_matches(1001, 2002, 3004)
