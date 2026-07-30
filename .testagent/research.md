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
