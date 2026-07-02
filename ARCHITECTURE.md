# Technology Stack

- Python 3.11+ architecture target. The current repository metadata requires Python 3.12+ and configures Ruff for `py312`.
- Telegram framework: aiogram v3.
- Persistence: MongoDB-compatible document storage. The challenge stack describes this as MongoDB with the Motor driver; the current repository implements the async MongoDB boundary with PyMongo 4.11+ `AsyncMongoClient`, which serves the same async persistence role behind `MongoSessionStore`.
- Rendering: Pillow for rasterizing terminal maps, modal screens, splash frames, and credits into PNG images.
- Terminal parsing: `pyte` for reading pseudo-terminal output into a Python terminal buffer.
- Native engine: original C ReLarn compiled from `vendor/relarn/` and executed through `subprocess.Popen`.
- PTY bridge: `os.openpty`, terminal sizing, process groups, and controlled stdin/stdout interaction.
- Runtime packaging: Podman, `Containerfile`, and `deploy/compose.yml`.
- Validation: `pytest`, `pytest-asyncio`, and `ruff`.
- Public Telegram entry point: [@tglarnbot](https://t.me/tglarnbot).

# Architecture Overview

`tglarn` is an asynchronous Telegram adapter around a synchronous C terminal game. The central design constraint is that ReLarn expects stdin/stdout terminal interaction, while Telegram expects event-driven callbacks and messages.

The runtime layers are:

```text
Telegram user
  -> bot/tglarn_bot/      aiogram handlers, callbacks, keyboards, rendering
  -> bot/tglarn_bot/services.py
                           async session boundary and adapter offloading
  -> bot/tglarn_bot/storage.py
                           MongoDB persistence and optimistic locking
  -> game/tglarn_game/relarn_process.py
                           ReLarn subprocess, PTY, prompt state machine
  -> vendor/relarn/       upstream C game engine and assets
```

The Telegram handlers never call the blocking C adapter directly. `GameSessionService` serializes work per player with an actor lock, then executes heavy adapter operations through `asyncio.to_thread`. A bounded `asyncio.Semaphore(4)` limits simultaneous adapter work so multiple slow C cycles cannot starve the bot event loop.

The ReLarn adapter treats each command as a controlled process cycle:

1. Restore the player's native save blob from MongoDB state.
2. Create a temporary home/runtime directory for ReLarn.
3. Open a PTY with `os.openpty`.
4. Start the C binary as a subprocess in a separate process group.
5. Send command bytes, including prompt answers, ESC, Enter, or numeric input.
6. Capture and parse terminal output.
7. Read the ReLarn turn-log export for complete same-turn event history, including duplicate combat messages that may scroll out of the visible terminal console.
8. Detect maps, prompts, modal screens, game-over screens, and save output.
9. Return a `GameResponse` with new state, screen text, status, actions, and optional prompt metadata.
10. Close PTY descriptors and terminate/reap the process group.

MongoDB stores the durable session boundary. A session contains the native ReLarn save blob, last rendered output, prompt metadata, map view, active Telegram message metadata, and `state_version`. This lets the bot recover after restarts and reject stale Telegram callbacks.

# Major Design Decisions

1. Thread offloading bounded by `asyncio.Semaphore(4)`.

   ReLarn is a blocking terminal application. Running it directly in an aiogram callback would block the event loop for every other user. The service layer wraps adapter operations with `asyncio.to_thread` and limits concurrent adapter work to four slots. This keeps Telegram polling responsive while still allowing parallel player sessions.

2. Optimistic Concurrency Control using `state_version` and `$inc`.

   Telegram users can press inline buttons faster than the bot can edit the message. To eliminate button-spam race conditions, session writes match both `telegram_user_id` and the expected `state_version`, then atomically increment `state_version` with `$inc`. If MongoDB returns no document, the write is rejected as stale and the valid stored `engine_state` is preserved.

3. Pillow-based visual engine for cross-platform ANSI grid rendering.

   The original C engine outputs complex, colorful ANSI/curses terminal grids. Telegram native text parsers, including Markdown and HTML modes, are volatile across mobile, desktop, and web clients and cannot reliably render multi-colored monospace grids without breaking layout. Pillow is therefore used as a visual compatibility layer: the adapter captures terminal state and rasterizes map and modal output into clean PNG images, preserving the retro display intended by the original game while avoiding client-specific text rendering failures.

4. Explicit PTY and process lifecycle ownership.

   The adapter owns every file descriptor and process it creates. Startup failure closes both PTY ends. Shutdown escalates from process-group termination to process-group kill and waits for the child process to be reaped. This avoids file descriptor leaks and zombie ReLarn processes.

5. Prompt handling as a state machine.

   ReLarn has many interactive terminal states: stores, bank prompts, tax prompts, object prompts, inventory menus, indexed picklists, lettered picklists, yes/no invoices, and multi-pick sale lists. The adapter records pending prompt metadata in `engine_state` so Telegram buttons answer the exact terminal state that produced them.

6. Explicit turn-log export for combat transparency.

   The curses console only displays the last six message lines. In Telegram, that can hide earlier same-turn events such as repeated monster hits before death. The C `say()` path now mirrors messages into a per-cycle turn-log file passed through `TGLARN_TURN_LOG_PATH`; the Python adapter reads this file before issuing the save command and uses it as the authoritative player-facing log for map and game-over responses.

# AI Tooling & Agent Workflow

The project used a three-role AI-native workflow:

- Product Owner / Tech Lead: User, defining scope, reviewing architecture, setting acceptance criteria, and deciding which risks mattered.
- Prompt Engineer / AI Strategist: Gemini, producing high-level state-machine prompts and directing the audit phases.
- Core Developer / Test Architect: Codex, executing repository changes, implementing Python code, refactoring concurrency and PTY lifecycle management, and expanding the automated tests.

Workflow:

1. Initial Scan.

   Codex inspected the repository structure, Python modules, tests, deployment files, existing docs, and the upstream C ReLarn source tree before making implementation changes.

2. Gap Analysis Report.

   Gemini framed a strict state-machine audit. Codex mapped C terminal inputs to Telegram UX states, including store invoices, DND Store prompts, Trading Post sale flows, bank number prompts, inventory picklists, object prompts, and generic indexed lists.

3. Iterative Execution.

   Codex implemented missing adapter states in stages: cancel/ESC infrastructure, `numPrompt`, store buy/sell confirmation, sale completion, indexed picklists, and emoji-free English button labels.

4. Concurrency Hardening.

   Codex refactored the infrastructure after the gameplay flows were covered: bounded `asyncio.to_thread`, PTY cleanup, process-group termination, zombie reaping, optimistic MongoDB locking, stale callback rejection, base64 validation, and crash-safe service responses.

5. Test Expansion.

   Every major adapter state gained regression coverage. The repository now contains 140 tests spanning keyboards, rendering, image generation, ReLarn prompt parsing, service persistence, stale callbacks, optimistic locking, error boundaries, and combat log transparency.
