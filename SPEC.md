# Specification

## Project

`tglarn` is a Telegram bot adaptation of ReLarn/Larn for the AI-Native Development Challenge.

## Game Rules

The game rules are inherited from ReLarn/Larn. At MVP level, the Telegram bot should expose the existing text-game loop rather than redesign the game.

High-level gameplay:

- The player controls a single adventurer.
- The player explores dungeon-like locations through text commands.
- The player can inspect status, move, interact with the world, fight monsters, collect items, and progress through the original game objective.
- The game state changes only when the player submits a command.
- One Telegram direct chat maps to one independent player session.

Detailed original rules remain in the imported upstream documentation under `vendor/relarn/doc/` and will be mapped into Telegram-friendly commands during implementation.

## Scope

### MVP Scope

- Import and preserve upstream ReLarn source and license notices.
- Define a clean project structure for upstream code, game adapter, Telegram bot, deployment, docs, and tests.
- Build a minimal Telegram bot flow that supports one direct-chat player session per Telegram user.
- Provide a main menu via `/start` and `/menu`, with actions for starting the game flow, restarting with confirmation, rules, repository link, and display size settings.
- Persist player session state server-side in a MongoDB-compatible document database.
- Provide enough commands to start a new game, view the current game screen/status, submit commands, and continue playing. The current placeholder adapter supports basic movement, look/status/help commands, and display-size-dependent viewport rendering until the ReLarn engine adapter is wired.
- Add automated smoke tests for session isolation and adapter behavior.
- Provide Podman-based local/deployment setup where all runtime services run in containers.
- Keep the required challenge documentation up to date.

### Out of Scope for MVP

- Group chat or multiplayer support.
- Full UI redesign.
- Competitive scoring or leaderboards.
- Rewriting ReLarn gameplay from scratch.
- One-click GitLab Pages/GitDocs playable version. This is a bonus target and may require either a hosted Telegram bot link or a separate browser demo.

## Functional Requirements

1. A user can start the bot in a direct Telegram chat.
2. A user can open the main menu with `/start` or `/menu` at any time.
3. A user can create or restart their own game session.
4. Restart requires explicit confirmation because current progress will be lost.
5. Player progress is persisted automatically by default; there is no manual save/load mechanism.
6. A user can submit supported game commands through Telegram messages and/or inline buttons.
7. A user receives a readable game response after each command.
8. Different Telegram users have isolated game states.
9. Bot runtime secrets are provided via environment variables and are never committed.
10. The original ReLarn source remains separated under `vendor/relarn/`.
11. Third-party license notices remain available in the repository.
12. The project can be run locally or on a VM using Podman with MongoDB in a neighboring container.
13. The repository contains `README.md`, `SPEC.md`, `ARCHITECTURE.md`, and `RETROSPECTIVE.md`.

## Non-Functional Requirements

- The code should favor small, testable adapter boundaries over direct bot-to-game coupling.
- The runtime should be restartable without losing persisted sessions.
- All runtime services should run in containers; no manually installed bot or database service should be required on the VM.
- Container design should keep a future Kubernetes deployment path open.
- The project should be understandable to reviewers who have not played ReLarn.
- Documentation should record AI tooling decisions, prompts/workflow patterns, and lessons learned.

## Acceptance Criteria

### Initial Structure Acceptance

- `vendor/relarn/` contains imported upstream ReLarn source.
- `bot/`, `game/`, `deploy/`, `docs/`, and `tests/` exist.
- Root documentation files exist: `README.md`, `SPEC.md`, `ARCHITECTURE.md`, `RETROSPECTIVE.md`.
- Root license and notices exist: `LICENSE.txt`, `NOTICE.md`, `LICENSES/`.

### MVP Gameplay Acceptance

- A reviewer can configure a Telegram bot token and run the service.
- A reviewer can open a direct chat with the bot and start a game.
- The bot returns game output after each supported command. During the adapter phase, placeholder output is acceptable as long as it goes through the same persistence and rendering path as the final engine.
- Two different Telegram users can play without state leaking between sessions.
- Basic automated tests pass in CI.
- The bot and database run through Podman containers for local/VM deployment.

### Final Challenge Acceptance

- The implementation is working by July 15, 2026.
- Documentation describes the final setup, run flow, architecture, and AI-native workflow.
- `RETROSPECTIVE.md` contains concrete observations about what worked, what did not work, surprises, AI-generated code estimate, time spent, and lessons learned.
