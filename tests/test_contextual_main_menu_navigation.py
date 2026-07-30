from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest
from tglarn_bot.handlers import register_handlers
from tglarn_bot.keyboards import CallbackData
from tglarn_game import GameResponse


def _registered_handlers(dispatcher, observer_name):
    router = dispatcher.sub_routers[0]
    return {
        handler.callback.__name__: handler.callback
        for handler in router.observers[observer_name].handlers
    }


def _button(markup, text):
    return next(
        button
        for row in markup.inline_keyboard
        for button in row
        if button.text == text
    )


def _button_texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def _callback(message, data):
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


def _message():
    return SimpleNamespace(
        edit_text=AsyncMock(),
        answer=AsyncMock(),
        answer_photo=AsyncMock(),
        edit_media=AsyncMock(),
        delete=AsyncMock(),
        photo=None,
        chat=SimpleNamespace(id=2002),
        message_id=3003,
        from_user=SimpleNamespace(
            id=1001,
            username="captain",
            first_name="Simon",
            last_name=None,
        ),
    )


def _session_service(*, active):
    return SimpleNamespace(
        active_game_message_matches=AsyncMock(return_value=active),
        ensure_session=AsyncMock(),
        set_active_game_message=AsyncMock(),
        set_map_view=AsyncMock(
            return_value=GameResponse(state={"view": "wide"}, screen="Updated view")
        ),
    )


def _dispatcher(session_service):
    dispatcher = Dispatcher()
    register_handlers(dispatcher, SimpleNamespace(), session_service)
    return dispatcher


def _last_edited_markup(message):
    return message.edit_text.await_args.kwargs["reply_markup"]


def _assert_bottom_back_to_game_menu(markup):
    bottom_button = markup.inline_keyboard[-1][0]
    assert bottom_button.text == "Back"
    assert bottom_button.callback_data == CallbackData.GAME_MENU


async def _open_contextual_main_menu(handlers, message):
    await handlers["game_menu_callback"](_callback(message, CallbackData.GAME_MENU))
    game_menu = _last_edited_markup(message)
    main_menu_button = _button(game_menu, "Main Menu")

    assert main_menu_button.callback_data == CallbackData.MAIN_MENU

    message.edit_text.reset_mock()
    await handlers["main_menu_callback"](_callback(message, main_menu_button.callback_data))
    main_menu = _last_edited_markup(message)
    _assert_bottom_back_to_game_menu(main_menu)
    return main_menu


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("button_text", "handler_name"),
    [
        ("About", "about_callback"),
        ("Plot", "plot_callback"),
        ("Legend", "legend_callback"),
        ("Rules", "rules_callback"),
        ("Display Size", "map_view_callback"),
    ],
)
async def test_contextual_section_return_restores_main_menu_with_game_menu_back(
    button_text,
    handler_name,
) -> None:
    service = _session_service(active=True)
    handlers = _registered_handlers(_dispatcher(service), "callback_query")
    message = _message()
    main_menu = await _open_contextual_main_menu(handlers, message)
    section_button = _button(main_menu, button_text)

    message.edit_text.reset_mock()
    await handlers[handler_name](_callback(message, section_button.callback_data))
    section_markup = _last_edited_markup(message)
    return_to_main = _button(section_markup, "Main Menu")

    message.edit_text.reset_mock()
    await handlers["main_menu_callback"](_callback(message, return_to_main.callback_data))

    _assert_bottom_back_to_game_menu(_last_edited_markup(message))
    assert service.active_game_message_matches.await_count == 2
    assert service.active_game_message_matches.await_args_list == [
        call(1001, 2002, 3003),
        call(1001, 2002, 3003),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("detail_button_text", "detail_handler_name"),
    [
        ("Controls", "rules_controls_callback"),
        ("Game Mechanics", "rules_mechanics_callback"),
    ],
)
async def test_contextual_rules_detail_return_restores_main_menu_with_game_menu_back(
    detail_button_text,
    detail_handler_name,
) -> None:
    service = _session_service(active=True)
    handlers = _registered_handlers(_dispatcher(service), "callback_query")
    message = _message()
    main_menu = await _open_contextual_main_menu(handlers, message)

    await handlers["rules_callback"](
        _callback(message, _button(main_menu, "Rules").callback_data)
    )
    rules_menu = _last_edited_markup(message)
    detail_button = _button(rules_menu, detail_button_text)

    message.edit_text.reset_mock()
    await handlers[detail_handler_name](_callback(message, detail_button.callback_data))
    rules_detail = _last_edited_markup(message)

    message.edit_text.reset_mock()
    await handlers["rules_callback"](
        _callback(message, _button(rules_detail, "Rules").callback_data)
    )
    restored_rules = _last_edited_markup(message)

    message.edit_text.reset_mock()
    await handlers["main_menu_callback"](
        _callback(message, _button(restored_rules, "Main Menu").callback_data)
    )
    _assert_bottom_back_to_game_menu(_last_edited_markup(message))
    assert service.active_game_message_matches.await_count == 2
    assert service.active_game_message_matches.await_args_list == [
        call(1001, 2002, 3003),
        call(1001, 2002, 3003),
    ]


@pytest.mark.asyncio
async def test_contextual_display_invalid_selection_return_restores_game_menu_back() -> None:
    service = _session_service(active=True)
    handlers = _registered_handlers(_dispatcher(service), "callback_query")
    message = _message()
    main_menu = await _open_contextual_main_menu(handlers, message)

    await handlers["map_view_callback"](
        _callback(message, _button(main_menu, "Display Size").callback_data)
    )
    message.edit_text.reset_mock()
    await handlers["map_view_selected_callback"](_callback(message, "view:invalid"))
    invalid_view_menu = _last_edited_markup(message)

    message.edit_text.reset_mock()
    await handlers["main_menu_callback"](
        _callback(message, _button(invalid_view_menu, "Main Menu").callback_data)
    )
    _assert_bottom_back_to_game_menu(_last_edited_markup(message))
    service.set_map_view.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("view_button_text", ["Medium", "Wide", "Max Size"])
async def test_contextual_display_valid_selection_returns_to_game_controls(
    view_button_text,
) -> None:
    service = _session_service(active=True)
    handlers = _registered_handlers(_dispatcher(service), "callback_query")
    message = _message()
    main_menu = await _open_contextual_main_menu(handlers, message)

    await handlers["map_view_callback"](
        _callback(message, _button(main_menu, "Display Size").callback_data)
    )
    view_menu = _last_edited_markup(message)
    selected_view = _button(view_menu, view_button_text)

    await handlers["map_view_selected_callback"](
        _callback(message, selected_view.callback_data)
    )

    game_markup = message.answer_photo.await_args.kwargs["reply_markup"]
    assert _button(game_markup, "Menu").callback_data == CallbackData.GAME_MENU
    assert CallbackData.MAIN_MENU not in {
        button.callback_data
        for row in game_markup.inline_keyboard
        for button in row
        if button.callback_data
    }
    service.set_map_view.assert_awaited_once()


@pytest.mark.asyncio
async def test_contextual_restart_cancel_sequence_restores_main_menu_with_game_menu_back() -> None:
    service = _session_service(active=True)
    handlers = _registered_handlers(_dispatcher(service), "callback_query")
    message = _message()
    main_menu = await _open_contextual_main_menu(handlers, message)

    await handlers["restart_request_callback"](
        _callback(message, _button(main_menu, "Restart Game").callback_data)
    )
    confirmation = _last_edited_markup(message)
    cancel_button = _button(confirmation, "Cancel")

    message.edit_text.reset_mock()
    await handlers["restart_cancel_callback"](_callback(message, cancel_button.callback_data))

    restored_main_menu = _last_edited_markup(message)
    assert _button_texts(restored_main_menu)[0] == "Resume Game"
    _assert_bottom_back_to_game_menu(restored_main_menu)


@pytest.mark.asyncio
async def test_contextual_main_menu_photo_replacement_records_new_message_identity() -> None:
    service = _session_service(active=True)
    handlers = _registered_handlers(_dispatcher(service), "callback_query")
    message = _message()
    replacement = SimpleNamespace(
        chat=SimpleNamespace(id=5005),
        message_id=6006,
    )
    message.photo = [SimpleNamespace()]
    message.edit_text.side_effect = TelegramBadRequest(
        method=SimpleNamespace(),
        message="Bad Request: there is no text in the message to edit",
    )
    message.answer.return_value = replacement

    await handlers["main_menu_callback"](_callback(message, CallbackData.MAIN_MENU))

    message.answer.assert_awaited_once()
    message.delete.assert_awaited_once()
    service.active_game_message_matches.assert_awaited_once_with(1001, 2002, 3003)
    service.set_active_game_message.assert_awaited_once_with(1001, 5005, 6006)


@pytest.mark.asyncio
@pytest.mark.parametrize("handler_name", ["start_command", "menu_command"])
async def test_context_free_commands_keep_main_menu_without_game_back(handler_name) -> None:
    service = _session_service(active=False)
    handlers = _registered_handlers(_dispatcher(service), "message")
    message = _message()

    await handlers[handler_name](message)

    markup = message.answer.await_args.kwargs["reply_markup"]
    assert _button_texts(markup)[0] == "Resume Game"
    assert "Back" not in _button_texts(markup)
    service.active_game_message_matches.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("handler_name", ["start_command", "menu_command"])
async def test_context_free_command_section_return_stays_without_game_back(
    handler_name,
) -> None:
    service = _session_service(active=False)
    dispatcher = _dispatcher(service)
    callback_handlers = _registered_handlers(dispatcher, "callback_query")
    message_handlers = _registered_handlers(dispatcher, "message")
    message = _message()

    await message_handlers[handler_name](message)
    root_menu = message.answer.await_args.kwargs["reply_markup"]
    await callback_handlers["about_callback"](
        _callback(message, _button(root_menu, "About").callback_data)
    )
    about_menu = _last_edited_markup(message)

    message.edit_text.reset_mock()
    await callback_handlers["main_menu_callback"](
        _callback(message, _button(about_menu, "Main Menu").callback_data)
    )

    restored_menu = _last_edited_markup(message)
    assert _button_texts(restored_menu)[0] == "Resume Game"
    assert "Back" not in _button_texts(restored_menu)
    service.active_game_message_matches.assert_awaited_once_with(1001, 2002, 3003)
