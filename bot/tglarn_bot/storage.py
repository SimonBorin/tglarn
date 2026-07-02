"""MongoDB persistence for Telegram player sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, AsyncMongoClient, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from .config import MapView
from .errors import SessionConflictError


class MongoSessionStore:
    """Stores player metadata and game sessions in MongoDB.

    Documents are keyed by Telegram user id because the MVP supports direct-chat
    single-player sessions only.
    """

    def __init__(self, mongo_uri: str, database_name: str) -> None:
        self._client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(mongo_uri)
        self._db: AsyncDatabase[dict[str, Any]] = self._client[database_name]
        self._players: AsyncCollection[dict[str, Any]] = self._db["players"]
        self._sessions: AsyncCollection[dict[str, Any]] = self._db["sessions"]
        self._turns: AsyncCollection[dict[str, Any]] = self._db["turns"]

    async def ping(self) -> None:
        await self._client.admin.command("ping")

    async def close(self) -> None:
        await self._client.close()

    async def ensure_indexes(self) -> None:
        await self._players.create_index("telegram_user_id", unique=True)
        await self._sessions.create_index("telegram_user_id", unique=True)
        await self._turns.create_index(
            [("telegram_user_id", ASCENDING), ("created_at", ASCENDING)]
        )

    async def ensure_session(
        self,
        telegram_user_id: int,
        default_map_view: MapView,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        now = _utcnow()
        await self._players.update_one(
            {"telegram_user_id": telegram_user_id},
            {
                "$set": {
                    "username": username,
                    "display_name": display_name,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "telegram_user_id": telegram_user_id,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        return await self._sessions.find_one_and_update(
            {"telegram_user_id": telegram_user_id},
            {
                "$set": {"updated_at": now},
                "$setOnInsert": _new_session_fields(
                    telegram_user_id=telegram_user_id,
                    default_map_view=default_map_view,
                    created_at=now,
                ),
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def restart_session(
        self,
        telegram_user_id: int,
        default_map_view: MapView,
    ) -> dict[str, Any]:
        now = _utcnow()
        return await self._sessions.find_one_and_update(
            {"telegram_user_id": telegram_user_id},
            {
                "$set": {
                    "status": "active",
                    "engine_state": {},
                    "last_screen": None,
                    "last_log": [],
                    "last_status": {},
                    "active_game_chat_id": None,
                    "active_game_message_id": None,
                    "updated_at": now,
                    "restarted_at": now,
                },
                "$setOnInsert": {
                    "telegram_user_id": telegram_user_id,
                    "created_at": now,
                    "map_view": default_map_view,
                },
                "$inc": {"run_number": 1, "state_version": 1},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def set_map_view(
        self,
        telegram_user_id: int,
        view: MapView,
        default_map_view: MapView,
    ) -> dict[str, Any]:
        now = _utcnow()
        return await self._sessions.find_one_and_update(
            {"telegram_user_id": telegram_user_id},
            {
                "$set": {
                    "map_view": view,
                    "updated_at": now,
                },
                "$setOnInsert": _new_session_fields(
                    telegram_user_id=telegram_user_id,
                    default_map_view=default_map_view,
                    created_at=now,
                    exclude={"map_view"},
                ),
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def set_active_game_message(
        self,
        telegram_user_id: int,
        chat_id: int,
        message_id: int,
    ) -> dict[str, Any]:
        now = _utcnow()
        session = await self._sessions.find_one_and_update(
            {"telegram_user_id": telegram_user_id},
            {
                "$set": {
                    "active_game_chat_id": chat_id,
                    "active_game_message_id": message_id,
                    "updated_at": now,
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if session is None:
            raise RuntimeError(f"Session for Telegram user {telegram_user_id} was not found")
        return session

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
    ) -> dict[str, Any]:
        now = _utcnow()
        session = await self._sessions.find_one_and_update(
            _versioned_session_filter(telegram_user_id, expected_state_version),
            {
                "$set": {
                    "status": "active",
                    "engine_state": engine_state,
                    "last_screen": screen,
                    "last_log": log,
                    "last_status": status,
                    "updated_at": now,
                },
                "$inc": {"state_version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if session is None:
            raise SessionConflictError(
                f"Session state changed for Telegram user {telegram_user_id}"
            )
        if input_text is not None:
            await self._turns.insert_one(
                {
                    "telegram_user_id": telegram_user_id,
                    "run_number": session.get("run_number", 1),
                    "input": input_text,
                    "output_screen": screen,
                    "output_log": log,
                    "created_at": now,
                }
            )
        return session


def _new_session_fields(
    telegram_user_id: int,
    default_map_view: MapView,
    created_at: datetime,
    exclude: set[str] | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "telegram_user_id": telegram_user_id,
        "created_at": created_at,
        "status": "active",
        "run_number": 1,
        "state_version": 0,
        "map_view": default_map_view,
        "engine_state": {},
        "last_screen": None,
        "last_log": [],
        "last_status": {},
        "active_game_chat_id": None,
        "active_game_message_id": None,
    }
    for key in exclude or set():
        fields.pop(key, None)
    return fields


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _versioned_session_filter(
    telegram_user_id: int,
    expected_state_version: int,
) -> dict[str, Any]:
    filter_query: dict[str, Any] = {"telegram_user_id": telegram_user_id}
    if expected_state_version == 0:
        filter_query["$or"] = [
            {"state_version": 0},
            {"state_version": {"$exists": False}},
        ]
        return filter_query
    filter_query["state_version"] = expected_state_version
    return filter_query
