# Architecture

## Technology Stack

Planned stack:

- Language: Python for Telegram bot and adapter code.
- Upstream game source: C ReLarn source imported under `vendor/relarn/`.
- Bot API: Telegram Bot API through a Python Telegram library.
- Persistence: MongoDB-compatible document database for MVP, with a future path to Amazon DocumentDB.
- Runtime: container-first deployment with Podman on a VM for MVP; Kubernetes-compatible structure later.
- CI/CD: GitLab CI for tests and optional deployment.
- Documentation: Markdown in repository root.

## Architecture Overview

The project is intentionally split into layers:

```text
Telegram user
  -> bot/tglarn_bot/      Telegram command and callback handling
  -> game/                Python adapter and session API
  -> vendor/relarn/       Imported original ReLarn source
  -> persistence          Session state storage
```

The bot layer should not directly modify imported upstream game internals. It should call a stable adapter API that accepts a player/session id plus a command and returns renderable text and state updates.

## Proposed Components

### `vendor/relarn/`

Contains the original upstream ReLarn source imported for reference, porting, and adaptation. This tree should remain close to upstream. If changes are needed, they should be documented and kept minimal.

### `game/`

Owns the Telegram-friendly game adapter. Expected responsibilities:

- session id handling;
- command normalization;
- invoking or wrapping game logic;
- converting game output into concise text suitable for Telegram;
- providing testable functions independent of Telegram.

### `bot/tglarn_bot/`

Owns Telegram-specific behavior:

- `/start` and restart flows;
- command handlers;
- inline keyboards where useful;
- formatting messages;
- error handling for invalid commands;
- environment configuration.

### `deploy/`

Owns operational files:

- Podman `Containerfile` and compose files;
- environment variable examples;
- VM deployment notes;
- GitLab CI/CD configuration if it is not kept at repository root.

### `tests/`

Owns automated tests:

- adapter unit tests;
- bot handler smoke tests where practical;
- session isolation tests;
- CI checks.

## Database Decision

The selected persistence layer is a MongoDB-compatible document database. The MVP will run MongoDB in a neighboring Podman container. The bot will connect through a `MONGO_URI`, so the same application code can later point at a separate managed database such as Amazon DocumentDB.

This is a better fit than SQLite for the target architecture because the bot should not depend on a local database file once deployed beyond the first VM. It is also simpler than PostgreSQL/Aurora for this project because player sessions and game state are mutable JSON-like documents and do not need relational joins.

To keep the future DocumentDB path realistic, the adapter should use conservative MongoDB operations: keyed lookups, single-document updates, explicit indexes, append-only turn logs, and `retryWrites=false` in DocumentDB connection strings. Avoid advanced MongoDB features unless they are checked against DocumentDB compatibility.

More detail is in `docs/DATABASE.md`.

## Major Design Decisions

1. Keep upstream ReLarn in `vendor/relarn/` rather than mixing it with bot code.

   Reason: this preserves license notices, makes upstream provenance clear, and reduces accidental bot-specific edits in third-party code.

2. Use Telegram direct chats only for MVP.

   Reason: the challenge does not require multiplayer, and direct-chat sessions keep state isolation simple and predictable.

3. Treat GitLab/GitDocs one-click play as a bonus, not the initial MVP.

   Reason: a Telegram bot requires a running backend and a bot token. A hosted bot link can satisfy easy demo access later, while GitLab Pages would require a separate browser-playable adaptation.

4. Prefer a small adapter boundary before deep porting.

   Reason: the fastest path to a complete challenge project is to expose a playable slice, then iterate.

5. Run everything in containers.

   Reason: the project should be deployable on a VM without hand-installed services and should have a clear path to Kubernetes later. The MVP should use Podman Compose with separate bot and MongoDB containers.

## AI Tooling Used

Current AI tooling:

- Codex for repository setup, documentation drafting, architecture planning, license-notice review, and implementation assistance.

Potential later tools:

- ChatGPT for design review and retrospective synthesis.
- GitLab CI feedback as an automated validation loop.

## Agent Workflow

Current workflow pattern:

1. User states project direction and constraints.
2. AI inspects the local repository and upstream license/source files.
3. AI proposes a conservative structure.
4. AI creates or updates files in small steps.
5. AI verifies file contents, git status, and license copies.
6. User reviews and redirects.

Planned implementation workflow:

1. Draft a narrow playable MVP spec.
2. Create adapter interfaces before bot handlers.
3. Implement a minimal command loop.
4. Add tests around session isolation and command handling.
5. Containerize with Podman.
6. Add GitLab CI.
7. Iterate on UX and documentation.
8. Record lessons in `RETROSPECTIVE.md` throughout the project, not only at the end.
