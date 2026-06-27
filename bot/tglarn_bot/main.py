"""Entrypoint for the Telegram bot process."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from pymongo.errors import PyMongoError
from tglarn_game import PlaceholderGameAdapter, RelarnProcessAdapter
from tglarn_game.models import GameAdapter

from .config import Settings, get_settings
from .handlers import register_handlers
from .services import GameSessionService
from .storage import MongoSessionStore

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    store = MongoSessionStore(settings.mongo_uri, settings.mongo_database)
    dispatcher = Dispatcher()
    session_service = GameSessionService(
        store=store,
        game_adapter=_build_game_adapter(settings),
        default_map_view=settings.default_map_view,
    )

    register_handlers(dispatcher, settings, session_service)
    try:
        await _prepare_store(store, settings)
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Open the main menu"),
                BotCommand(command="menu", description="Open the main menu"),
            ]
        )
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        await store.close()
        await bot.session.close()


def _build_game_adapter(settings: Settings) -> GameAdapter:
    if settings.game_adapter == "relarn_process":
        logger.info("Using upstream ReLarn process adapter")
        return RelarnProcessAdapter(
            binary_path=settings.relarn_binary_path,
            install_root=settings.relarn_install_root,
            timeout_seconds=settings.relarn_cycle_timeout_seconds,
            settle_seconds=settings.relarn_cycle_settle_seconds,
        )
    logger.info("Using placeholder game adapter")
    return PlaceholderGameAdapter()


async def _prepare_store(store: MongoSessionStore, settings: Settings) -> None:
    last_error: PyMongoError | None = None
    for attempt in range(1, settings.database_startup_attempts + 1):
        try:
            await store.ping()
            await store.ensure_indexes()
            logger.info("MongoDB connection is ready")
            return
        except PyMongoError as exc:
            last_error = exc
            logger.warning(
                "MongoDB is not ready yet (%s/%s): %s",
                attempt,
                settings.database_startup_attempts,
                exc,
            )
            if attempt < settings.database_startup_attempts:
                await asyncio.sleep(settings.database_startup_delay_seconds)
    raise RuntimeError("MongoDB did not become ready") from last_error


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
