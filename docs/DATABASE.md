# Database Decision

## Decision

Use a MongoDB-compatible document database for player, chat, session, and game-state persistence.

MVP runtime:

- MongoDB in a neighboring Podman container.
- Bot connects through a normal MongoDB connection string.
- The database must be reachable by the bot through `MONGO_URI`; the bot must not assume localhost or a local database file.

Future AWS runtime:

- Amazon DocumentDB or another MongoDB-compatible managed document database.
- The application should not depend on local filesystem persistence.

## Why Document Storage Fits

The bot state is naturally document-shaped:

- Telegram user metadata;
- chat metadata;
- active game session;
- game-state snapshot;
- last rendered output;
- turn history.

There is no strong need for joins, cross-session transactions, or relational reporting in the MVP. The dominant access pattern is keyed lookup by Telegram user/session id followed by atomic update of that session document.

## Why Not SQLite

SQLite is simple and would work for a single VM, but it couples persistence to one filesystem volume and does not match the target shape where the bot connects to a separate database service. It is still useful for small tools and tests, but it is not the chosen production path.

## Why Not PostgreSQL/Aurora

PostgreSQL with JSONB would be technically solid, but it adds relational schema and SQL concerns we do not currently need. It is a good fallback if the project later needs reporting, complex querying, strict relational constraints, or broader team familiarity.

## Why Not DynamoDB for MVP

DynamoDB is a strong AWS-native option for scalable session/game state, but it requires designing access patterns around DynamoDB keys and using AWS-specific APIs from day one. For this project, MongoDB locally plus a future DocumentDB target is a more direct path because the session state is a mutable JSON-like document and can be developed entirely in local containers first.

## DocumentDB Compatibility Constraints

To keep migration from MongoDB to Amazon DocumentDB realistic, the application should use a conservative MongoDB subset:

- simple `insert_one`, `find_one`, `update_one`, `find_one_and_update` operations;
- explicit indexes on lookup fields;
- single-document atomic updates for active session state;
- simple append-only turn history writes;
- no dependency on advanced aggregation pipelines;
- no MongoDB-specific features unless checked against DocumentDB support;
- set `retryWrites=false` in connection strings for DocumentDB compatibility.

## Initial Collections

### `players`

One document per Telegram user.

```json
{
  "_id": 123456789,
  "telegram_user_id": 123456789,
  "username": "example",
  "first_name": "Example",
  "last_name": "Player",
  "created_at": "2026-06-26T10:00:00Z",
  "last_seen_at": "2026-06-26T10:30:00Z"
}
```

Indexes:

- `_id` / `telegram_user_id`
- `username` optional, non-unique

### `chats`

One document per direct Telegram chat.

```json
{
  "_id": 123456789,
  "chat_id": 123456789,
  "telegram_user_id": 123456789,
  "type": "private",
  "created_at": "2026-06-26T10:00:00Z",
  "last_seen_at": "2026-06-26T10:30:00Z"
}
```

Indexes:

- `_id` / `chat_id`
- `telegram_user_id`

### `sessions`

One or more documents per player. Usually one active session.

```json
{
  "_id": "session-id",
  "telegram_user_id": 123456789,
  "chat_id": 123456789,
  "status": "active",
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:30:00Z",
  "state_version": 1,
  "game_state": {},
  "last_output": "You are standing at the entrance..."
}
```

Indexes:

- `telegram_user_id + status`
- `updated_at`

### `turns`

Append-only command history for debugging and retrospective analysis.

```json
{
  "_id": "turn-id",
  "session_id": "session-id",
  "telegram_user_id": 123456789,
  "input": "north",
  "output": "You move north.",
  "created_at": "2026-06-26T10:31:00Z"
}
```

Indexes:

- `session_id + created_at`
- `telegram_user_id + created_at`

## Configuration

Use environment variables:

```text
MONGO_URI=mongodb://tglarn_user:password@mongo:27017/tglarn?authSource=admin&retryWrites=false
MONGO_DB=tglarn
```

For local Podman, `mongo` is the service name in `deploy/compose.yml`.

For Amazon DocumentDB, `MONGO_URI` should point at the DocumentDB cluster endpoint and include the required TLS options and `retryWrites=false`.
