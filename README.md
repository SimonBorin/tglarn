# tglarn

`tglarn` is a Telegram bot adaptation of ReLarn/Larn for the AI-Native Development Challenge.

The project goal is to make an old text/roguelike game playable through a direct Telegram bot conversation while documenting the full AI-native development lifecycle: requirements, planning, architecture, implementation, validation, documentation, and retrospective.

## Game Description

ReLarn is an old-school roguelike derived from Larn/Ularn. The player explores a dungeon, manages resources, fights monsters, collects items, and tries to progress through the game world using text commands.

`tglarn` will wrap that game loop in a Telegram-friendly interface:

- one direct chat with the bot equals one player session;
- Telegram messages and inline buttons drive game commands;
- game state is persisted server-side;
- the original ReLarn source is kept separate from bot-specific code.

## Screenshots

Not available yet. Screenshots or short demo captures will be added after the first playable Telegram flow exists.

## Layout

- `vendor/relarn/` - imported upstream ReLarn source. Keep this close to upstream and avoid bot-specific edits here unless a change must patch the original game.
- `game/` - game adapter/domain layer. It currently contains a placeholder adapter with the same boundary the future C ReLarn adapter should implement.
- `bot/tglarn_bot/` - Telegram bot handlers, keyboards, command routing, and session persistence.
- `deploy/` - Podman, VM, GitLab CI/CD, and deployment files.
- `docs/` - architecture notes, porting notes, and licensing notes.
- `tests/` - automated checks.
- `LICENSES/` - third-party license texts that are also preserved in the imported upstream tree.

Imported ReLarn upstream commit:

```text
36400b004448620d94a9f432570de9fb077988a5
```

## Upstream References

- ReLarn website: http://relarn.org
- ReLarn official repository: https://gitlab.com/relarn/relarn
- Imported source mirror: https://github.com/relarn/relarn
- Known upstream contributors: `vendor/relarn/AUTHORS.txt`

## Setup

Current status: project scaffold, imported upstream source, Telegram chat menu, MongoDB-backed session persistence, local container build files, a placeholder game adapter, and an experimental upstream ReLarn process adapter are in place. The default remains the placeholder adapter; set `GAME_ADAPTER=relarn_process` to use the original C game through the pty bridge.

Expected local prerequisites for the implementation phase:

- Python 3.12+ for local bot development
- Podman for container runtime
- Telegram bot token from BotFather
- MongoDB-compatible database; local MVP uses MongoDB in Podman, future deployment may use Amazon DocumentDB

Python and database binaries should not be installed directly on the VM for normal runtime. The bot and supporting services should run in containers.

Create local secrets outside git. `.env.example` is committed as a template, while `.env` is ignored by git. The bot token can also be exported from your shell profile as `TG_LARN_BOT_TOKEN`.

```bash
TG_LARN_BOT_TOKEN=replace-with-telegram-bot-token
MONGO_INITDB_ROOT_USERNAME=tglarn
MONGO_INITDB_ROOT_PASSWORD=change-me
MONGO_DATABASE=tglarn
MONGO_URI=mongodb://tglarn:change-me@localhost:27017/tglarn?authSource=admin
GAME_ADAPTER=placeholder
```

Do not commit real tokens or passwords.

## Run

Recommended local container run path:

```bash
source ~/.zprofile
./deploy/local-up.sh
```

The script creates `.env` from `.env.example` if needed, builds `localhost/tglarn-bot:dev`, starts MongoDB, and starts the bot. If `podman-compose` is installed it uses `deploy/compose.yml`; otherwise it falls back to direct `podman build/run`, which avoids Docker Desktop compose-provider issues. Stop foreground bot execution with `Ctrl+C`, then stop local containers with:

```bash
./deploy/local-down.sh
```

Detached mode:

```bash
source ~/.zprofile
./deploy/local-up.sh -d
podman logs -f tglarn-bot
```

If your Podman Compose provider is configured correctly, you can also run compose directly:

```bash
source ~/.zprofile
set -a; source .env; set +a
podman compose -f deploy/compose.yml up --build -d
```

For local Python development against the Mongo container exposed on `127.0.0.1:27017`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
source ~/.zprofile
set -a; source .env; set +a
.venv/bin/python -m tglarn_bot.main
```

The bot currently exposes `/start` and `/menu`, plus inline buttons for resuming the game, restarting with confirmation, rules, legend, about, repository link, and display size selection. The Rules menu is split into Controls and Game Mechanics. The active game screen is driven by inline buttons and is edited in place after button presses, so normal button play does not spam new bot messages. Text commands such as `north`, `south`, `east`, `west`, `look`, `status`, and `help` remain available as a fallback; unlike button presses, each typed command sends a new game response message so the latest result stays next to the player's input. Fallback responses are persisted in MongoDB and remembered as the new active game screen for later buttons. Display sizes currently render map viewports as `medium` 21x11, `wide` 31x15, and `max` 52x23. See `deploy/README.md` for the container strategy and Kubernetes-readiness notes.

The experimental `relarn_process` adapter runs the upstream C ReLarn binary under a pseudo-terminal for each action. It stores the native ReLarn savefile as a base64 blob in Mongo session state, so player progress is still database-backed and does not require a long-running game process per user. The container image builds ReLarn into `/opt/relarn`; for local Python runs you must either keep `GAME_ADAPTER=placeholder` or point `RELARN_BINARY_PATH` and `RELARN_INSTALL_ROOT` at a local ReLarn build/install tree.

## Current Placeholder Actions

- `north`, `n`, `up` - move north.
- `south`, `s`, `down` - move south.
- `east`, `e`, `right` - move east.
- `west`, `w`, `left` - move west.
- `nw`, `ne`, `sw`, `se` - move diagonally.
- `wait`, `.` - wait one turn.
- `descend`, `go down`, `>` - go down stairs when standing on stairs.
- `look`, `l` - inspect the area.
- `status`, `stats` - show hero stats.
- `help`, `?` - show help and map legend.
- `/menu` - open the main menu.

## Required Challenge Documents

- `SPEC.md` - game rules, scope, requirements, acceptance criteria.
- `ARCHITECTURE.md` - stack, design, decisions, AI workflow.
- `RETROSPECTIVE.md` - AI-native development workflow and lessons learned.

## Remotes

GitHub origin:

```bash
git remote add origin git@github.com:SimonBorin/tglarn.git
```

Required GitLab challenge remote will be added later under:

```text
https://git.ringcentral.com/rc-ai-learning
```

Suggested repository name:

```text
simon-borin-tglarn
```

## License

This project is intended to be distributed under GPL-2.0-or-later because it is based on ReLarn, which is licensed under GNU GPL version 2 or, at your option, any later version.

The full GPL v2 text is in `LICENSE.txt`.

The imported ReLarn source retains its original copyright and license notices under `vendor/relarn/`.

The field-of-view library in `vendor/relarn/src/fov/` is separately licensed under a permissive MIT-style license by Greg McIntyre. Its notice is preserved in `vendor/relarn/src/fov/COPYING-libfov`, copied to `LICENSES/libfov-MIT.txt`, and summarized in `NOTICE.md`.

The bundled Inconsolata font is licensed under the SIL Open Font License 1.1. Its notice is preserved in `vendor/relarn/data/fonts/OFL.txt`, copied to `LICENSES/inconsolata-OFL-1.1.txt`, and summarized in `NOTICE.md`.
