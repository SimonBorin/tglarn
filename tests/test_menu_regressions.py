from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Dispatcher
from tglarn_bot import __version__
from tglarn_bot import handlers as handler_module
from tglarn_bot.animations import SPLASH_CAPTIONS
from tglarn_bot.handlers import register_handlers
from tglarn_bot.keyboards import CallbackData, game_menu_keyboard, main_menu_keyboard
from tglarn_bot.texts import ABOUT_TEXT, PLOT_TEXT
from tglarn_game import GameResponse


def _registered_callback_handlers(dispatcher):
    router = dispatcher.sub_routers[0]
    return {
        handler.callback.__name__: handler.callback
        for handler in router.observers["callback_query"].handlers
    }


def _button_texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def _button_callback_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _dispatcher_with_handlers(session_service):
    dispatcher = Dispatcher()
    register_handlers(dispatcher, SimpleNamespace(), session_service)
    return dispatcher


def _callback(message, *, data=None):
    return SimpleNamespace(
        answer=AsyncMock(),
        data=data,
        message=message,
        from_user=SimpleNamespace(
            id=1001,
            username="captain",
            first_name="Simon",
            last_name=None,
        ),
    )


def _editable_message():
    return SimpleNamespace(
        edit_text=AsyncMock(),
        answer=AsyncMock(),
        answer_photo=AsyncMock(),
        edit_media=AsyncMock(),
        delete=AsyncMock(),
        photo=None,
        chat=SimpleNamespace(id=2002),
        message_id=3003,
    )


def test_game_main_menu_keeps_resume_and_adds_bottom_back_to_game_menu() -> None:
    markup = main_menu_keyboard(show_back=True)

    assert _button_texts(markup)[0] == "Resume Game"
    assert _button_texts(markup)[-1] == "Back"
    assert _button_callback_data(markup)[-1] == CallbackData.GAME_MENU

    game_menu_main_button = next(
        button
        for row in game_menu_keyboard().inline_keyboard
        for button in row
        if button.text == "Main Menu"
    )
    assert game_menu_main_button.callback_data == CallbackData.GAME_MAIN_MENU


@pytest.mark.asyncio
async def test_game_main_menu_callback_renders_contextual_back_path() -> None:
    dispatcher = _dispatcher_with_handlers(SimpleNamespace())
    handler = _registered_callback_handlers(dispatcher)["game_main_menu_callback"]
    message = _editable_message()
    callback = _callback(message, data=CallbackData.GAME_MAIN_MENU)

    await handler(callback)

    callback.answer.assert_awaited_once_with()
    message.edit_text.assert_awaited_once()
    markup = message.edit_text.await_args.kwargs["reply_markup"]
    assert _button_texts(markup)[0] == "Resume Game"
    assert _button_texts(markup)[-1] == "Back"
    assert _button_callback_data(markup)[-1] == CallbackData.GAME_MENU


@pytest.mark.asyncio
async def test_resume_game_renders_current_screen_without_start_splash(monkeypatch) -> None:
    response = GameResponse(state={"turn": 4}, screen="Resumed game")
    play_start_splash = AsyncMock()
    monkeypatch.setattr(handler_module, "_play_start_splash", play_start_splash)
    session_service = SimpleNamespace(
        needs_character_setup=AsyncMock(return_value=False),
        start_game=AsyncMock(return_value=response),
        set_active_game_message=AsyncMock(),
    )
    dispatcher = _dispatcher_with_handlers(session_service)
    handler = _registered_callback_handlers(dispatcher)["start_game_callback"]
    message = _editable_message()
    callback = _callback(message, data=CallbackData.START_GAME)

    await handler(callback)

    callback.answer.assert_awaited_once_with()
    session_service.start_game.assert_awaited_once()
    play_start_splash.assert_not_called()
    message.answer_photo.assert_awaited_once()
    assert message.answer_photo.await_args.kwargs["caption"] not in SPLASH_CAPTIONS
    message.edit_media.assert_not_awaited()
    message.answer.assert_not_awaited()


def test_main_menu_separates_plot_from_project_about() -> None:
    texts = _button_texts(main_menu_keyboard())

    assert texts[-2:] == ["Plot", "About"]
    assert "Repository" not in texts
    assert "daughter is dying" in PLOT_TEXT


@pytest.mark.asyncio
async def test_plot_and_about_callbacks_show_distinct_content() -> None:
    dispatcher = _dispatcher_with_handlers(SimpleNamespace())
    handlers = _registered_callback_handlers(dispatcher)

    plot_message = _editable_message()
    await handlers["plot_callback"](_callback(plot_message, data=CallbackData.PLOT))
    assert plot_message.edit_text.await_args.args[0] == PLOT_TEXT

    about_message = _editable_message()
    await handlers["about_callback"](_callback(about_message, data=CallbackData.ABOUT))
    about = about_message.edit_text.await_args.args[0]

    assert "Version:" in about
    assert __version__ in about
    assert "Author:" in about
    assert "Simon Borin" in about
    assert "https://github.com/SimonBorin" in about
    assert "https://github.com/SimonBorin/tglarn" in about
    assert "https://simonborin.github.io/tglarn/" in about
    assert "ringcentral" not in about.lower()
    assert "simon-a-borin" not in about.lower()
    assert "daughter is dying" not in about


def test_about_template_uses_runtime_version_placeholder() -> None:
    rendered = ABOUT_TEXT.format(version="9.8.7")

    assert "Version:" in rendered
    assert "9.8.7" in rendered
    assert "0.1.0" not in rendered


def test_release_version_drives_image_tag_label_and_runtime_game_version() -> None:
    root = Path(__file__).parents[1]
    release_workflow = (root / ".github/workflows/release.yml").read_text()
    containerfile = (root / "Containerfile").read_text()
    package_init = (root / "bot/tglarn_bot/__init__.py").read_text()

    assert "VERSION: ${{ needs.version.outputs.version }}" in release_workflow
    assert "RELEASE_TAG: ${{ needs.version.outputs.tag }}" in release_workflow
    assert "tags: tglarn:${{ env.RELEASE_TAG }}" in release_workflow
    assert "TGLARN_VERSION=${{ env.VERSION }}" in release_workflow

    assert "ARG TGLARN_VERSION=" in containerfile
    assert 'org.opencontainers.image.version="$TGLARN_VERSION"' in containerfile
    assert 'TGLARN_VERSION="$TGLARN_VERSION"' in containerfile
    assert 'os.getenv("TGLARN_VERSION"' in package_init
