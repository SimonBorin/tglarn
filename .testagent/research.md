# Bounded test research

## Scope

- `game/tglarn_game/relarn_process.py`
- `bot/tglarn_bot/keyboards.py`
- `bot/tglarn_bot/handlers.py` when numeric-pad routing requires it
- `vendor/relarn/src/action.c` and `vendor/relarn/src/game.c` only for
  slot-specific unequip behavior
- Existing pytest suites under `tests/`

## Existing conventions

- Pytest function tests with direct helper imports.
- Keyboard tests flatten `InlineKeyboardMarkup` and assert button text and
  callback data.
- ReLarn adapter tests use synthetic 80x25 terminal line arrays and assert
  detected prompt metadata and exact replay key sequences.
- Async handler/service tests use pytest-asyncio and fake service/store objects.

## Acceptance checklist

- Direct item action buttons must open a selectable C picker instead of leaving
  `quickinv()` blocked.
- Indexed store buttons must preserve the physical C picker row across blank
  category separators.
- Equipped inventory items must expose `Unwield` or `Take Off`, and action
  classification must not offer known invalid charm actions.
- Numeric prompts must be completable with inline digit, backspace, maximum,
  submit, and cancel buttons without typed text.
- Missing meaningful C commands (wait, run, close door, trap identification,
  tax status, scores, help, version) must have Python mappings and buttons.
- Every generated callback must be checked against Telegram's 64-byte limit.

## Static pairing analyzer limitation

The mandatory `find-untested-sources` tree-sitter analyzer was invoked once.
Its parser package attempted to create a cache under
`~/Library/Caches/tree-sitter-language-pack`, which is outside the writable
sandbox. The escalation request was aborted, so the analyzer could not produce
a reliable pairing report. Existing source-to-test locations above are based
on the repository's established test layout, not on a successful static
pairing run.

## Development support extension

- `keyboards.py` owns game-menu placement and the support submenu.
- `payments.py` owns Star amounts, payloads, and checkout validation.
- `handlers.py` owns invoices, checkout, payment confirmation, `/paysupport`,
  and `/terms`.
- `tests/test_support.py` uses an in-memory dispatcher and mocks, with no
  network or database access.

## Menu regression extension

- `bot/tglarn_bot/keyboards.py` owns the main-menu, game-menu, Plot, About,
  support, and back-navigation button structures.
- `bot/tglarn_bot/handlers.py` decides whether Resume renders the current game
  directly or schedules the new-game splash animation.
- `bot/tglarn_bot/__init__.py` exposes the deployed `TGLARN_VERSION`; About must
  render that runtime value instead of a separately maintained literal.
- Existing callback-handler tests use an in-memory `Dispatcher`,
  `SimpleNamespace` Telegram objects, and `AsyncMock` methods. This permits
  regression coverage without Telegram, MongoDB, or a running ReLarn process.
- Telegram invoices are separate messages when sent with `answer_invoice`.
  Reusing the current support message therefore requires an invoice-link flow:
  create the link via the bot, then edit the existing support message with the
  payment action and a Back path.

## Beta feedback and canonical-link extension

- `README.md` is the repository landing document and must expose the beta state
  and issue-report invitation outside an HTML comment.
- `site/index.html` is the GitHub Pages entry point. A standard-library
  `HTMLParser` can distinguish visible body copy from scripts/styles and collect
  the actual anchor targets without adding a test dependency.
- The canonical report target is
  `https://github.com/SimonBorin/tglarn/issues`; the canonical repository target
  is `https://github.com/SimonBorin/tglarn`.
- `bot/tglarn_bot/texts.py` owns the About template. The canonical Pages URL is
  `https://simonborin.github.io/tglarn/`.

## Contextual Main Menu navigation extension

- Context is message-scoped, not callback-token-scoped:
  `session_service.active_game_message_matches(user_id, chat_id, message_id)`
  identifies whether the edited message belongs to the active in-game flow.
- The same `CallbackData.MAIN_MENU` route must therefore render either the
  ordinary menu or a contextual menu whose bottom Back action targets
  `CallbackData.GAME_MENU`.
- About, Plot, Legend, Rules, rule details, Display Size, invalid display
  selection, and restart cancellation all edit the same message. Their local
  navigation may remain unchanged, but following it back to Main Menu must
  re-evaluate the active-message context and restore the bottom game-menu Back.
- Valid Display Size selection intentionally returns to the game response. Its
  keyboard must expose `Menu -> GAME_MENU` and contain no direct context-free
  Main Menu callback.
- `/start` and `/menu` are new message commands rather than callbacks on the
  active game message, so they legitimately render the context-free Main Menu.
- A photo-to-text Main Menu transition replaces the Telegram message. The
  replacement chat/message ID must become the active game message immediately;
  otherwise the next nested return is misclassified as context-free.

## Game-over screenshot and public credits identity extension

- README references the documentation screenshot under `docs/screenshots/`;
  GitHub Pages references its own copy under `site/assets/`.
- Preventing the removed screenshot from silently returning requires both
  negative source assertions (`End of a run`, `tglarn-game-over.png`) and
  absence checks for both copied assets.
- `bot/tglarn_bot/animations.py` owns the actual in-game `CREDIT_TEXTS`.
  The creator credit must use `@SimonBorin` and must exclude both historical
  work-identity markers: `Simon.A.Borin` and `@ringcentral.com`.
- Credit frames are cached under `CREDITS_CACHE_NAMESPACE`. Changing only
  `CREDIT_TEXTS` without invalidating the old `credits-v5` namespace can keep
  displaying previously rendered work-identity frames from `/tmp`.
