# Project Overview

`tglarn` is a Telegram bot adaptation of the ReLarn/Larn roguelike engine. It wraps the original C game, preserved under `vendor/relarn/`, with a Python Telegram adapter that translates terminal-driven gameplay into direct-chat messages, contextual inline buttons, and rendered game images.

## Play the Live Bot

Play the public Telegram build here: [@tglarnbot](https://t.me/tglarnbot).

Scan this QR code or open the handle directly:

![Telegram QR code for @tglarnbot](docs/screenshots/tglarn-bot-qr.png)

The project keeps the legacy engine and the new integration code deliberately separate:

- `vendor/relarn/` contains the upstream C ReLarn source and assets.
- `game/tglarn_game/` contains the Python game adapter boundary, including the ReLarn subprocess and PTY bridge.
- `bot/tglarn_bot/` contains aiogram handlers, keyboards, rendering, persistence services, and Telegram-specific UX.
- `tests/` contains the 140-test suite covering the adapter, keyboards, rendering, process prompts, session service, and error boundaries.

The AI-native team model was explicit:

- Product Owner / Tech Lead: Simon.A.Borin, responsible for product scope, architectural boundaries, feature requests, and final review.
- Prompt Engineer / AI Strategist: Gemini, responsible for high-level system design, state-machine audit prompts, and implementation planning.
- Core Developer / Test Architect: Codex, responsible for implementation, concurrency control, PTY lifecycle management, process cleanup, and the automated test suite.

# Game Description

Larn is a classic roguelike about a parent trying to find a cure for a daughter who has contracted Dianthroritis. The player explores the caverns of Larn, manages limited resources, fights monsters, collects treasure, interacts with town services, and searches for the Potion of Cure Dianthroritis before time or death ends the run.

The game remains turn-based and command-driven. Movement, inventory actions, spellcasting, stores, banks, tax prompts, object interactions, and win/loss conditions are still controlled by the original C engine. The Telegram bot changes the interface, not the rules.

# Screenshots

Rendered dungeon map:

![Rendered dungeon map](docs/screenshots/tglarn-map-render.png)

Store prompt inline keyboard:

![Store prompt inline keyboard](docs/screenshots/tglarn-store-prompt.png)

Game-over credits screen:

![Game-over credits screen](docs/screenshots/tglarn-game-over.png)

# Setup & Run Instructions

Prerequisites:

- Python 3.12+ for the current repository metadata in `pyproject.toml`. The architecture is compatible with Python 3.11+, but the checked-in package metadata currently declares `requires-python = ">=3.12"`.
- A Telegram bot token from BotFather.
- MongoDB or a MongoDB-compatible database.
- Podman for the provided local container workflow.
- A compiled ReLarn binary when using `GAME_ADAPTER=relarn_process` outside the provided container image.

Create a local virtual environment and install dependencies:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create local environment configuration:

```bash
cp .env.example .env
```

Set the required runtime variables in `.env`:

```text
TG_LARN_BOT_TOKEN=replace-with-token-from-botfather
MONGO_URI=mongodb://tglarn:change-me@localhost:27017/tglarn?authSource=admin
MONGO_DATABASE=tglarn
DEFAULT_MAP_VIEW=wide
GAME_ADAPTER=placeholder
```

Use the real C engine adapter by switching the adapter and pointing to a ReLarn install:

```text
GAME_ADAPTER=relarn_process
RELARN_BINARY_PATH=/opt/relarn/lib/relarn/relarn.bin
RELARN_INSTALL_ROOT=/opt/relarn
RELARN_CYCLE_TIMEOUT_SECONDS=3
RELARN_CYCLE_SETTLE_SECONDS=0.12
```

Run the local Podman stack:

```bash
./deploy/local-up.sh
```

Run the stack detached and follow bot logs:

```bash
./deploy/local-up.sh -d
podman logs -f tglarn-bot
```

Stop local containers:

```bash
./deploy/local-down.sh
```

Run the bot directly from the virtual environment after MongoDB is available:

```bash
. .venv/bin/activate
set -a
. .env
set +a
python -m tglarn_bot.main
```

Run linting and the full test suite:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
```

The repository currently contains 140 tests. They cover menu keyboards, text rendering, Pillow image rendering, placeholder gameplay, ReLarn prompt detection, inventory flows, store invoices, number prompts, stale button rejection, optimistic locking, adapter error boundaries, combat log transparency, and session isolation.

# Licensing & Credits

`tglarn` is distributed under the GNU General Public License Version 2 terms applicable to the ReLarn-derived work. The root GPL license text is stored as `LICENSE.txt`; the upstream ReLarn copy is preserved at `vendor/relarn/LICENSE.txt`.

Attribution and license breakdown:

- Core engine: ReLarn, Copyright (C) 1986-2020 by The Authors. The imported engine is located at `vendor/relarn/` and is distributed under the GNU General Public License Version 2, or at the user's option any later version, as stated in `vendor/relarn/Copyright.txt`.
- Field of View library: `libfov`, located at `vendor/relarn/src/fov/`, Copyright (c) 2006 Greg McIntyre. It is distributed under permissive MIT terms. The preserved license text is available at `LICENSES/libfov-MIT.txt` and `vendor/relarn/src/fov/COPYING-libfov`.
- Font asset: `Inconsolata-Medium.ttf`, located at `vendor/relarn/data/fonts/`, Copyright 2006 The Inconsolata Project Authors. It is licensed under the SIL Open Font License 1.1. The preserved license text is available at `LICENSES/inconsolata-OFL-1.1.txt` and `vendor/relarn/data/fonts/OFL.txt`.
- Local modifications: files outside `vendor/relarn/` are tglarn-specific project structure, Telegram integration, deployment support, documentation, and tests.

Pop-culture references and artifacts appearing in the upstream game belong to their respective rights holders. Their presence in ReLarn or this wrapper does not imply endorsement, sponsorship, or affiliation.
