"""Telegram handlers for the chat-based bot UI."""

from typing import cast

from aiogram import Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, User

from .config import MapView, Settings
from .keyboards import (
    CHARACTER_CLASS_BY_ID,
    CHARACTER_GENDER_BY_ID,
    CallbackData,
    back_to_menu_keyboard,
    character_class_keyboard,
    character_gender_keyboard,
    game_keyboard,
    game_legend_keyboard,
    game_menu_keyboard,
    intro_keyboard,
    main_menu_keyboard,
    map_view_keyboard,
    repository_keyboard,
    restart_confirmation_keyboard,
    rules_detail_keyboard,
    rules_menu_keyboard,
    spell_menu_keyboard,
)
from .rendering import render_game_response
from .services import GameSessionService
from .texts import (
    ABOUT_TEXT,
    CHARACTER_CLASS_TEXT,
    CHARACTER_CREATED_TEXT,
    CHARACTER_GENDER_TEXT,
    CONTROLS_TEXT,
    GAME_MECHANICS_TEXT,
    GAME_MENU_TEXT,
    INTRO_TEXT,
    LEGEND_TEXT,
    MAIN_MENU_TEXT,
    MAP_VIEW_TEXT,
    MAP_VIEW_UPDATED_TEXT,
    REPOSITORY_TEXT,
    RESTART_CONFIRM_TEXT,
    RULES_MENU_TEXT,
    SPELL_MENU_TEXT,
)

_VALID_MAP_VIEWS = {"medium", "wide", "max"}


def register_handlers(
    dispatcher: Dispatcher,
    settings: Settings,
    session_service: GameSessionService,
) -> None:
    router = Router(name="chat_menu")

    @router.message(CommandStart())
    async def start_command(message: Message) -> None:
        await _ensure_user_session(message, session_service)
        await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())

    @router.message(Command("menu"))
    async def menu_command(message: Message) -> None:
        await _ensure_user_session(message, session_service)
        await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())

    @router.message(F.text)
    async def text_game_command(message: Message) -> None:
        await _handle_text_game_command(message, session_service)

    @router.callback_query(F.data == CallbackData.MAIN_MENU)
    async def main_menu_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, MAIN_MENU_TEXT, main_menu_keyboard())

    @router.callback_query(F.data == CallbackData.START_GAME)
    async def start_game_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        telegram_user_id = _telegram_user_id(callback)
        if telegram_user_id is None:
            return
        username, display_name = _user_profile(callback.from_user)
        if await session_service.needs_character_setup(telegram_user_id, username, display_name):
            await _edit_callback_message(callback, INTRO_TEXT, intro_keyboard())
            return
        response = await session_service.start_game(
            telegram_user_id,
            username,
            display_name,
        )
        await _edit_callback_message(
            callback,
            render_game_response(response),
            game_keyboard(response),
        )
        await _remember_callback_game_message(callback, session_service)

    @router.callback_query(F.data == CallbackData.CHARACTER_INTRO)
    async def character_intro_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, CHARACTER_CLASS_TEXT, character_class_keyboard())

    @router.callback_query(F.data.startswith(CallbackData.CHARACTER_CLASS_PREFIX))
    async def character_class_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        class_id = _extract_character_class_id(callback.data)
        if class_id is None:
            await _edit_callback_message(callback, CHARACTER_CLASS_TEXT, character_class_keyboard())
            return
        character_class = CHARACTER_CLASS_BY_ID[class_id]
        await _edit_callback_message(
            callback,
            CHARACTER_GENDER_TEXT.format(character_class=character_class),
            character_gender_keyboard(class_id),
        )

    @router.callback_query(F.data.startswith(CallbackData.CHARACTER_GENDER_PREFIX))
    async def character_gender_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        telegram_user_id = _telegram_user_id(callback)
        selected = _extract_character_gender(callback.data)
        if telegram_user_id is None or selected is None:
            await _edit_callback_message(callback, CHARACTER_CLASS_TEXT, character_class_keyboard())
            return
        class_id, gender_id = selected
        character_class = CHARACTER_CLASS_BY_ID[class_id]
        gender_label = CHARACTER_GENDER_BY_ID[gender_id]
        response = await session_service.start_new_character(
            telegram_user_id,
            character_class,
            gender_id,
        )
        character_text = CHARACTER_CREATED_TEXT.format(
            gender=gender_label,
            character_class=character_class,
        )
        rendered = f"{character_text}\n\n{render_game_response(response)}"
        await _edit_callback_message(callback, rendered, game_keyboard(response))
        await _remember_callback_game_message(callback, session_service)

    @router.callback_query(F.data == CallbackData.RULES)
    async def rules_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, RULES_MENU_TEXT, rules_menu_keyboard())

    @router.callback_query(F.data == CallbackData.RULES_CONTROLS)
    async def rules_controls_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, CONTROLS_TEXT, rules_detail_keyboard())

    @router.callback_query(F.data == CallbackData.RULES_MECHANICS)
    async def rules_mechanics_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, GAME_MECHANICS_TEXT, rules_detail_keyboard())

    @router.callback_query(F.data == CallbackData.LEGEND)
    async def legend_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, LEGEND_TEXT, back_to_menu_keyboard())

    @router.callback_query(F.data == CallbackData.ABOUT)
    async def about_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, ABOUT_TEXT, back_to_menu_keyboard())

    @router.callback_query(F.data == CallbackData.REPOSITORY)
    async def repository_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(
            callback,
            REPOSITORY_TEXT,
            repository_keyboard(settings.repository_url),
        )

    @router.callback_query(F.data == CallbackData.MAP_VIEW)
    async def map_view_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, MAP_VIEW_TEXT, map_view_keyboard())

    @router.callback_query(F.data.startswith("view:"))
    async def map_view_selected_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        view = _extract_map_view(callback.data)
        if view is None:
            await _edit_callback_message(callback, MAP_VIEW_TEXT, map_view_keyboard())
            return
        telegram_user_id = _telegram_user_id(callback)
        if telegram_user_id is None:
            return
        response = await session_service.set_map_view(telegram_user_id, view)
        rendered = (
            f"{MAP_VIEW_UPDATED_TEXT.format(view=_map_view_label(view))}\n\n"
            f"{render_game_response(response)}"
        )
        await _edit_callback_message(
            callback,
            rendered,
            game_keyboard(response),
        )
        await _remember_callback_game_message(callback, session_service)

    @router.callback_query(F.data == CallbackData.SPELL_MENU)
    async def spell_menu_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, SPELL_MENU_TEXT, spell_menu_keyboard())
        await _remember_callback_game_message(callback, session_service)

    @router.callback_query(F.data == CallbackData.GAME_MENU)
    async def game_menu_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, GAME_MENU_TEXT, game_menu_keyboard())
        await _remember_callback_game_message(callback, session_service)

    @router.callback_query(F.data == CallbackData.GAME_LEGEND)
    async def game_legend_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, LEGEND_TEXT, game_legend_keyboard())
        await _remember_callback_game_message(callback, session_service)

    @router.callback_query(F.data == CallbackData.BACK_TO_GAME)
    async def back_to_game_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        telegram_user_id = _telegram_user_id(callback)
        if telegram_user_id is None:
            return
        response = await session_service.current_game(telegram_user_id)
        await _edit_callback_message(
            callback,
            render_game_response(response),
            game_keyboard(response),
        )
        await _remember_callback_game_message(callback, session_service)

    @router.callback_query(F.data == CallbackData.RESTART_REQUEST)
    async def restart_request_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(
            callback,
            RESTART_CONFIRM_TEXT,
            restart_confirmation_keyboard(),
        )

    @router.callback_query(F.data == CallbackData.RESTART_CANCEL)
    async def restart_cancel_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, MAIN_MENU_TEXT, main_menu_keyboard())

    @router.callback_query(F.data == CallbackData.RESTART_CONFIRM)
    async def restart_confirm_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        telegram_user_id = _telegram_user_id(callback)
        if telegram_user_id is not None:
            await session_service.prepare_new_character(telegram_user_id)
        await _edit_callback_message(callback, INTRO_TEXT, intro_keyboard())

    @router.callback_query(F.data.startswith(CallbackData.GAME_PREFIX))
    async def game_action_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        telegram_user_id = _telegram_user_id(callback)
        command = _extract_game_command(callback.data)
        if telegram_user_id is None or command is None:
            return
        response = await session_service.apply_command(telegram_user_id, command)
        await _edit_callback_message(
            callback,
            render_game_response(response),
            game_keyboard(response),
        )
        await _remember_callback_game_message(callback, session_service)

    dispatcher.include_router(router)


async def _ensure_user_session(message: Message, session_service: GameSessionService) -> None:
    if message.from_user is not None:
        await session_service.ensure_session(
            message.from_user.id,
            *_user_profile(message.from_user),
        )


async def _handle_text_game_command(message: Message, session_service: GameSessionService) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
        return

    if await session_service.needs_character_setup(
        message.from_user.id,
        *_user_profile(message.from_user),
    ):
        await message.answer(INTRO_TEXT, reply_markup=intro_keyboard())
        return

    response = await session_service.apply_command(message.from_user.id, message.text)
    sent = await message.answer(
        render_game_response(response),
        reply_markup=game_keyboard(response),
    )
    await session_service.set_active_game_message(
        message.from_user.id,
        sent.chat.id,
        sent.message_id,
    )


async def _answer_callback(callback: CallbackQuery) -> None:
    await callback.answer()


async def _edit_callback_message(
    callback: CallbackQuery,
    text: str,
    reply_markup,
) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _remember_callback_game_message(
    callback: CallbackQuery,
    session_service: GameSessionService,
) -> None:
    telegram_user_id = _telegram_user_id(callback)
    if telegram_user_id is None or callback.message is None:
        return
    await session_service.set_active_game_message(
        telegram_user_id,
        callback.message.chat.id,
        callback.message.message_id,
    )


def _telegram_user_id(callback: CallbackQuery) -> int | None:
    if callback.from_user is None:
        return None
    return callback.from_user.id


def _user_profile(user: User | None) -> tuple[str | None, str | None]:
    if user is None:
        return None, None
    display_name = " ".join(part for part in [user.first_name, user.last_name] if part)
    return user.username, display_name or None


def _extract_map_view(callback_data: str | None) -> MapView | None:
    if callback_data is None:
        return None
    _, _, value = callback_data.partition(":")
    if value == "desktop":
        return "max"
    if value in _VALID_MAP_VIEWS:
        return cast(MapView, value)
    return None


def _extract_game_command(callback_data: str | None) -> str | None:
    if callback_data is None:
        return None
    prefix, _, value = callback_data.partition(":")
    if f"{prefix}:" != CallbackData.GAME_PREFIX or not value:
        return None
    return value


def _extract_character_class_id(callback_data: str | None) -> str | None:
    if callback_data is None or not callback_data.startswith(CallbackData.CHARACTER_CLASS_PREFIX):
        return None
    class_id = callback_data.removeprefix(CallbackData.CHARACTER_CLASS_PREFIX)
    return class_id if class_id in CHARACTER_CLASS_BY_ID else None


def _extract_character_gender(callback_data: str | None) -> tuple[str, str] | None:
    if callback_data is None or not callback_data.startswith(CallbackData.CHARACTER_GENDER_PREFIX):
        return None
    value = callback_data.removeprefix(CallbackData.CHARACTER_GENDER_PREFIX)
    class_id, separator, gender_id = value.partition(":")
    if separator != ":":
        return None
    if class_id not in CHARACTER_CLASS_BY_ID or gender_id not in CHARACTER_GENDER_BY_ID:
        return None
    return class_id, gender_id


def _map_view_label(view: MapView) -> str:
    return {"medium": "Medium", "wide": "Wide", "max": "Max Size"}[view]
