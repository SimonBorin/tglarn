from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import AnswerCallbackQuery
from tglarn_bot.handlers import _answer_callback, _handle_text_game_command
from tglarn_bot.texts import INTRO_TEXT
from tglarn_game import PlaceholderGameAdapter


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.from_user = SimpleNamespace(
            id=1001,
            username="kirk",
            first_name="James",
            last_name="Kirk",
        )
        self.text = text
        self.bot = SimpleNamespace(edit_message_text=AsyncMock())
        self.answers = []

    async def answer(self, text, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=SimpleNamespace(id=2002), message_id=3003)


class FakeSessionService:
    def __init__(self, needs_character: bool = False) -> None:
        self.calls = []
        self.needs_character = needs_character
        self.adapter = PlaceholderGameAdapter()
        self.state = self.adapter.restart().state

    async def needs_character_setup(
        self,
        telegram_user_id: int,
        username: str | None = None,
        display_name: str | None = None,
    ) -> bool:
        self.calls.append(("needs_character_setup", telegram_user_id, username, display_name))
        return self.needs_character

    async def ensure_session(self, telegram_user_id: int) -> dict:
        self.calls.append(("ensure_session", telegram_user_id))
        return {"engine_state": self.state}

    async def apply_command(self, telegram_user_id: int, command: str):
        self.calls.append(("apply_command", telegram_user_id, command))
        response = self.adapter.apply_command(self.state, command)
        self.state = response.state
        return response

    async def set_active_game_message(
        self,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> None:
        self.calls.append(("set_active_game_message", telegram_user_id, chat_id, message_id))


class NetworkFailingCallback:
    async def answer(self) -> None:
        raise TelegramNetworkError(
            method=AnswerCallbackQuery(callback_query_id="callback-id"),
            message="ServerDisconnectedError: Server disconnected",
        )


@pytest.mark.asyncio
async def test_answer_callback_ignores_transient_telegram_network_error() -> None:
    await _answer_callback(NetworkFailingCallback())


@pytest.mark.asyncio
async def test_text_command_sends_new_game_message_instead_of_editing_active_message() -> None:
    message = FakeMessage("east")
    service = FakeSessionService()

    await _handle_text_game_command(message, service)

    assert len(message.answers) == 1
    assert "@" in message.answers[0][0]
    assert service.calls == [
        ("needs_character_setup", 1001, "kirk", "James Kirk"),
        ("apply_command", 1001, "east"),
        ("set_active_game_message", 1001, 2002, 3003),
    ]
    message.bot.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_text_command_before_character_creation_shows_intro() -> None:
    message = FakeMessage("east")
    service = FakeSessionService(needs_character=True)

    await _handle_text_game_command(message, service)

    assert len(message.answers) == 1
    assert message.answers[0][0] == INTRO_TEXT
    assert service.calls == [
        ("needs_character_setup", 1001, "kirk", "James Kirk"),
    ]
    message.bot.edit_message_text.assert_not_awaited()
