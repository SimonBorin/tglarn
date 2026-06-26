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
- `game/` - game adapter/domain layer. This is where Telegram-friendly APIs should wrap the original game behavior.
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

Current status: project scaffold and imported upstream source are in place. The Telegram bot implementation is not wired yet.

Expected local prerequisites for the implementation phase:

- Python 3.11+
- Podman
- Telegram bot token from BotFather
- MongoDB or another persistence backend, depending on the final adapter design

Create local secrets outside git, for example in `.env`:

```bash
BOT_TOKEN=replace-with-telegram-bot-token
MONGO_PASS=replace-with-local-password
```

Do not commit real tokens or passwords.

## Run

The playable bot runtime is not implemented yet. The intended MVP run path is:

```bash
podman compose -f deploy/compose.yml up -d
```

This command will be added and validated when the bot service, persistence service, and deployment files are implemented.

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
