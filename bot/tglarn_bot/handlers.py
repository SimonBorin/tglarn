"""Telegram handlers for the chat-based bot UI."""

import asyncio
import contextlib
from collections.abc import Coroutine
from html import escape
from typing import Any, cast

from aiogram import Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message, User

from .animations import (
    CREDITS_DELAY_SECONDS,
    SPLASH_CAPTIONS,
    SPLASH_DELAY_SECONDS,
    credits_frame_paths,
    splash_frame_paths,
)
from .config import MapView, Settings
from .keyboards import (
    CHARACTER_CLASS_BY_ID,
    CHARACTER_GENDER_BY_ID,
    CallbackData,
    back_to_menu_keyboard,
    character_class_guide_keyboard,
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
from .map_image import cleanup_rendered_game_image, render_game_image
from .rendering import render_game_response
from .services import GameSessionService
from .texts import (
    ABOUT_TEXT,
    CHARACTER_CLASS_GUIDE_TEXT,
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
    animations = _AnimationManager()

    @router.message(CommandStart())
    async def start_command(message: Message) -> None:
        _cancel_message_animation(message, animations)
        await _ensure_user_session(message, session_service)
        await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())

    @router.message(Command("menu"))
    async def menu_command(message: Message) -> None:
        _cancel_message_animation(message, animations)
        await _ensure_user_session(message, session_service)
        await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())

    @router.message(F.text)
    async def text_game_command(message: Message) -> None:
        await _handle_text_game_command(message, session_service, animations)

    @router.callback_query(F.data == CallbackData.MAIN_MENU)
    async def main_menu_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        _cancel_callback_animation(callback, animations)
        await _edit_callback_message(callback, MAIN_MENU_TEXT, main_menu_keyboard())

    @router.callback_query(F.data == CallbackData.START_GAME)
    async def start_game_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        telegram_user_id = _telegram_user_id(callback)
        if telegram_user_id is None:
            return
        username, display_name = _user_profile(callback.from_user)
        if await session_service.needs_character_setup(telegram_user_id, username, display_name):
            animations.start(
                telegram_user_id,
                _play_start_splash(
                    callback=callback,
                    text=INTRO_TEXT,
                    reply_markup=intro_keyboard(),
                    session_service=session_service,
                    telegram_user_id=telegram_user_id,
                    remember_as_game_message=False,
                ),
            )
            return
        response = await session_service.start_game(
            telegram_user_id,
            username,
            display_name,
        )
        animations.start(
            telegram_user_id,
            _play_start_splash(
                callback=callback,
                text=None,
                reply_markup=game_keyboard(response),
                session_service=session_service,
                telegram_user_id=telegram_user_id,
                game_response=response,
            ),
        )

    @router.callback_query(F.data == CallbackData.CHARACTER_INTRO)
    async def character_intro_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(callback, CHARACTER_CLASS_TEXT, character_class_keyboard())

    @router.callback_query(F.data == CallbackData.CHARACTER_CLASS_GUIDE)
    async def character_class_guide_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        await _edit_callback_message(
            callback,
            CHARACTER_CLASS_GUIDE_TEXT,
            character_class_guide_keyboard(),
        )

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
        edited_message = await _edit_callback_game_response(
            callback,
            response,
            game_keyboard(response),
            prefix_html=character_text,
        )
        await _remember_callback_game_message(callback, session_service, edited_message)

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
        edited_message = await _edit_callback_game_response(
            callback,
            response,
            game_keyboard(response),
            prefix_html=MAP_VIEW_UPDATED_TEXT.format(view=_map_view_label(view)),
        )
        await _remember_callback_game_message(callback, session_service, edited_message)

    @router.callback_query(F.data == CallbackData.SPELL_MENU)
    async def spell_menu_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        edited_message = await _edit_callback_message(
            callback,
            SPELL_MENU_TEXT,
            spell_menu_keyboard(),
        )
        await _remember_callback_game_message(callback, session_service, edited_message)

    @router.callback_query(F.data == CallbackData.GAME_MENU)
    async def game_menu_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        edited_message = await _edit_callback_message(
            callback,
            GAME_MENU_TEXT,
            game_menu_keyboard(),
        )
        await _remember_callback_game_message(callback, session_service, edited_message)

    @router.callback_query(F.data == CallbackData.GAME_LEGEND)
    async def game_legend_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        edited_message = await _edit_callback_message(callback, LEGEND_TEXT, game_legend_keyboard())
        await _remember_callback_game_message(callback, session_service, edited_message)

    @router.callback_query(F.data == CallbackData.BACK_TO_GAME)
    async def back_to_game_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        telegram_user_id = _telegram_user_id(callback)
        if telegram_user_id is None:
            return
        response = await session_service.current_game(telegram_user_id)
        edited_message = await _edit_callback_game_response(
            callback,
            response,
            game_keyboard(response),
        )
        await _remember_callback_game_message(callback, session_service, edited_message)

    @router.callback_query(F.data == CallbackData.RESTART_REQUEST)
    async def restart_request_callback(callback: CallbackQuery) -> None:
        await _answer_callback(callback)
        _cancel_callback_animation(callback, animations)
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
        _cancel_callback_animation(callback, animations)
        telegram_user_id = _telegram_user_id(callback)
        if telegram_user_id is not None:
            await session_service.prepare_new_character(telegram_user_id)
            animations.start(
                telegram_user_id,
                _play_start_splash(
                    callback=callback,
                    text=INTRO_TEXT,
                    reply_markup=intro_keyboard(),
                    session_service=session_service,
                    telegram_user_id=telegram_user_id,
                    remember_as_game_message=False,
                ),
            )
            return
        await _edit_callback_message(callback, INTRO_TEXT, intro_keyboard())

    @router.callback_query(F.data.startswith(CallbackData.GAME_PREFIX))
    async def game_action_callback(callback: CallbackQuery) -> None:
        telegram_user_id = _telegram_user_id(callback)
        command = _extract_game_command(callback.data)
        if telegram_user_id is None or command is None:
            return
        callback_message = callback.message
        if callback_message is not None:
            chat_id = getattr(getattr(callback_message, "chat", None), "id", None)
            message_id = getattr(callback_message, "message_id", None)
            if isinstance(chat_id, int) and isinstance(message_id, int):
                if not await session_service.active_game_message_matches(
                    telegram_user_id,
                    chat_id,
                    message_id,
                ):
                    await _answer_callback(
                        callback,
                        "This game screen is out of date. Use the latest game screen.",
                    )
                    return
        await _answer_callback(callback)
        response = await session_service.apply_command(telegram_user_id, command)
        if response.status.get("game_over"):
            animations.start(
                telegram_user_id,
                _play_game_over_credits(
                    callback=callback,
                    response=response,
                    session_service=session_service,
                    telegram_user_id=telegram_user_id,
                ),
            )
            return
        edited_message = await _edit_callback_game_response(
            callback,
            response,
            game_keyboard(response),
        )
        await _remember_callback_game_message(callback, session_service, edited_message)

    dispatcher.include_router(router)


async def _ensure_user_session(message: Message, session_service: GameSessionService) -> None:
    if message.from_user is not None:
        await session_service.ensure_session(
            message.from_user.id,
            *_user_profile(message.from_user),
        )


async def _handle_text_game_command(
    message: Message,
    session_service: GameSessionService,
    animations: "_AnimationManager | None" = None,
) -> None:
    if message.from_user is None or message.text is None:
        return
    if message.text.startswith("/"):
        _cancel_message_animation(message, animations)
        await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
        return

    if await session_service.needs_character_setup(
        message.from_user.id,
        *_user_profile(message.from_user),
    ):
        await message.answer(INTRO_TEXT, reply_markup=intro_keyboard())
        return

    response = await session_service.apply_command(message.from_user.id, message.text)
    if response.status.get("game_over") and animations is not None:
        animations.start(
            message.from_user.id,
            _play_game_over_credits_from_message(
                message=message,
                response=response,
                session_service=session_service,
                telegram_user_id=message.from_user.id,
            ),
        )
        return

    sent = await _answer_game_response(message, response, game_keyboard(response))
    await session_service.set_active_game_message(
        message.from_user.id,
        sent.chat.id,
        sent.message_id,
    )


class _AnimationManager:
    def __init__(self) -> None:
        self._tasks: dict[int, asyncio.Task[None]] = {}

    def start(self, telegram_user_id: int, coro: Coroutine[Any, Any, None]) -> None:
        self.cancel(telegram_user_id)
        task = asyncio.create_task(coro)
        self._tasks[telegram_user_id] = task

        def _forget(done_task: asyncio.Task[None]) -> None:
            if self._tasks.get(telegram_user_id) is done_task:
                self._tasks.pop(telegram_user_id, None)

        task.add_done_callback(_forget)

    def cancel(self, telegram_user_id: int) -> None:
        task = self._tasks.pop(telegram_user_id, None)
        if task is not None:
            task.cancel()


async def _play_start_splash(
    callback: CallbackQuery,
    text: str | None,
    reply_markup,
    session_service: GameSessionService,
    telegram_user_id: int,
    remember_as_game_message: bool = True,
    game_response=None,
) -> None:
    if callback.message is None:
        return

    animation_message: Message | None = None
    try:
        frames = splash_frame_paths()
        animation_message = await callback.message.answer_photo(
            FSInputFile(frames[0]),
            caption=SPLASH_CAPTIONS[0],
        )
        await _delete_message(callback.message)

        for index, frame in enumerate(frames[1:], start=1):
            await asyncio.sleep(SPLASH_DELAY_SECONDS)
            await animation_message.edit_media(
                InputMediaPhoto(media=FSInputFile(frame), caption=SPLASH_CAPTIONS[index])
            )

        await asyncio.sleep(SPLASH_DELAY_SECONDS)
        if game_response is not None:
            sent = await _answer_game_response(animation_message, game_response, reply_markup)
            await _delete_message(animation_message)
            if remember_as_game_message:
                await session_service.set_active_game_message(
                    telegram_user_id,
                    sent.chat.id,
                    sent.message_id,
                )
            return

        text = text or ""
        if _can_keep_splash_message(text, remember_as_game_message):
            await animation_message.edit_caption(caption=text, reply_markup=reply_markup)
            return

        sent = await animation_message.answer(text, reply_markup=reply_markup)
        await _delete_message(animation_message)
        if remember_as_game_message:
            await session_service.set_active_game_message(
                telegram_user_id,
                sent.chat.id,
                sent.message_id,
            )
    except asyncio.CancelledError:
        if animation_message is not None:
            await _delete_message(animation_message)
        raise
    except TelegramBadRequest:
        return


def _can_keep_splash_message(text: str, remember_as_game_message: bool) -> bool:
    return not remember_as_game_message and len(text) <= 900 and "<pre>" not in text


async def _play_game_over_credits(
    callback: CallbackQuery,
    response,
    session_service: GameSessionService,
    telegram_user_id: int,
) -> None:
    if callback.message is None:
        return
    await _play_game_over_credits_from_message(
        message=callback.message,
        response=response,
        session_service=session_service,
        telegram_user_id=telegram_user_id,
        delete_source=True,
    )


async def _play_game_over_credits_from_message(
    message: Message,
    response,
    session_service: GameSessionService,
    telegram_user_id: int,
    delete_source: bool = False,
) -> None:
    try:
        frames = credits_frame_paths()
        caption = _game_over_credits_caption(response)
        credits_message = await message.answer_photo(
            FSInputFile(frames[0]),
            caption=caption,
            reply_markup=game_keyboard(response),
        )
        if delete_source:
            await _delete_message(message)
        await session_service.set_active_game_message(
            telegram_user_id,
            credits_message.chat.id,
            credits_message.message_id,
        )

        for frame in frames[1:]:
            await asyncio.sleep(CREDITS_DELAY_SECONDS)
            await credits_message.edit_media(
                InputMediaPhoto(media=FSInputFile(frame), caption=caption),
                reply_markup=game_keyboard(response),
            )
    except asyncio.CancelledError:
        raise
    except TelegramBadRequest:
        return


def _game_over_credits_caption(response) -> str:
    parts = []
    if response.log:
        log_text = "\n".join(f"- {escape(item)}" for item in response.log)
        parts.append(f"<b>Log</b>\n{log_text}")
    parts.append("<i>Use Restart Game to begin a new run.</i>")
    return "\n\n".join(parts)


async def _delete_message(message: Message) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await message.delete()


def _cancel_callback_animation(
    callback: CallbackQuery,
    animations: "_AnimationManager | None",
) -> None:
    if animations is not None and callback.from_user is not None:
        animations.cancel(callback.from_user.id)


def _cancel_message_animation(message: Message, animations: "_AnimationManager | None") -> None:
    if animations is not None and message.from_user is not None:
        animations.cancel(message.from_user.id)


async def _answer_callback(callback: CallbackQuery, text: str | None = None) -> None:
    with contextlib.suppress(TelegramNetworkError):
        if text is None:
            await callback.answer()
        else:
            await callback.answer(text)


async def _answer_game_response(
    message: Message,
    response,
    reply_markup,
    prefix_html: str | None = None,
) -> Message:
    rendered_image = render_game_image(response, prefix_html=prefix_html)
    if rendered_image is None:
        text = _render_game_text(response, prefix_html)
        return await message.answer(text, reply_markup=reply_markup)
    try:
        return await message.answer_photo(
            FSInputFile(rendered_image.path),
            caption=rendered_image.caption,
            reply_markup=reply_markup,
        )
    finally:
        cleanup_rendered_game_image(rendered_image)


async def _edit_callback_game_response(
    callback: CallbackQuery,
    response,
    reply_markup,
    prefix_html: str | None = None,
) -> Message | None:
    rendered_image = render_game_image(response, prefix_html=prefix_html)
    if rendered_image is None:
        return await _edit_callback_message(
            callback,
            _render_game_text(response, prefix_html),
            reply_markup,
        )
    if callback.message is None:
        cleanup_rendered_game_image(rendered_image)
        return None
    try:
        if callback.message.photo:
            try:
                await callback.message.edit_media(
                    InputMediaPhoto(
                        media=FSInputFile(rendered_image.path),
                        caption=rendered_image.caption,
                    ),
                    reply_markup=reply_markup,
                )
                return callback.message
            except TelegramBadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    return callback.message
                raise

        sent = await callback.message.answer_photo(
            FSInputFile(rendered_image.path),
            caption=rendered_image.caption,
            reply_markup=reply_markup,
        )
        await _delete_message(callback.message)
        return sent
    finally:
        cleanup_rendered_game_image(rendered_image)


def _render_game_text(response, prefix_html: str | None = None) -> str:
    rendered = render_game_response(response)
    if not prefix_html:
        return rendered
    return f"{prefix_html}\n\n{rendered}"


async def _edit_callback_message(
    callback: CallbackQuery,
    text: str,
    reply_markup,
) -> Message | None:
    if callback.message is None:
        return None
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
        return callback.message
    except TelegramBadRequest as exc:
        message = str(exc).lower()
        if "message is not modified" in message:
            return callback.message
        if callback.message.photo:
            return await _edit_photo_callback_message(callback, text, reply_markup)
        raise


async def _edit_photo_callback_message(
    callback: CallbackQuery,
    text: str,
    reply_markup,
) -> Message | None:
    if callback.message is None:
        return None

    sent = await callback.message.answer(text, reply_markup=reply_markup)
    await _delete_message(callback.message)
    return sent


async def _remember_callback_game_message(
    callback: CallbackQuery,
    session_service: GameSessionService,
    message: Message | None = None,
) -> None:
    telegram_user_id = _telegram_user_id(callback)
    target_message = message or callback.message
    if telegram_user_id is None or target_message is None:
        return
    await session_service.set_active_game_message(
        telegram_user_id,
        target_message.chat.id,
        target_message.message_id,
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
