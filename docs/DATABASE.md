# Database Decision

## Decision

Use a MongoDB-compatible document database for player, session, and game-state persistence. Direct-chat metadata can be added later if it becomes useful, but the current key is Telegram user id.

MVP runtime:

- MongoDB in a neighboring Podman container.
- Bot connects through a normal MongoDB connection string.
- The database must be reachable by the bot through `MONGO_URI`; the bot must not assume a local database file. In compose, the host is `mongo`; for host-machine development, `.env` uses `localhost`.

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

## Implemented Collections

### `players`

One document per Telegram user.

```json
{
  "_id": 123456789,
  "telegram_user_id": 123456789,
  "username": "example",
  "display_name": "Example Player",
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:30:00Z"
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
  "updated_at": "2026-06-26T10:30:00Z"
}
```

Indexes:

- `_id` / `chat_id`
- `telegram_user_id`

### `sessions`

One active document per Telegram user for the MVP.

```json
{
  "telegram_user_id": 123456789,
  "status": "active",
  "run_number": 1,
  "map_view": "compact",
  "created_at": "2026-06-26T10:00:00Z",
  "updated_at": "2026-06-26T10:30:00Z",
  "engine_state": {},
  "last_screen": null,
  "last_log": []
}
```

Indexes:

- unique `telegram_user_id`

### `turns`

Append-only command history for debugging and retrospective analysis. The collection and index are created now; writes will be added with the game adapter.

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
MONGO_URI=mongodb://tglarn:password@mongo:27017/tglarn?authSource=admin
MONGO_DATABASE=tglarn
```

For local Podman, `mongo` is the service name in `deploy/compose.yml`.

For Amazon DocumentDB, `MONGO_URI` should point at the DocumentDB cluster endpoint and include the required TLS options and `retryWrites=false`.
