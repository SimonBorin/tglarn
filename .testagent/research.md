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
