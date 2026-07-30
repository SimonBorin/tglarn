# Regression validation status

## Result

- Full pytest suite: `156 passed`.
- Ruff: `All checks passed!`.
- Native build:
  `make -C vendor/relarn/src SYS=darwin-x86` completed with
  `-std=gnu99 -Wall -Werror` and linked `relarn.bin`.
- Container build was attempted but the local Podman VM was not running. The
  direct native build exercised the changed C translation units successfully.

## Test-gap review

The changed branches were reviewed as mutation points against the added
regressions:

| Mutation point | Killing regression |
|---|---|
| Remove the `?` picker-opening byte from an item action | `test_item_commands_open_native_fullscreen_pickers` |
| Count only populated store rows | `test_indexed_store_selection_preserves_blank_category_rows` |
| Treat equipped and unequipped inventory entries identically | `test_inventory_actions_reflect_equipped_state` |
| Restore broad charm/amulet wield-name guessing | `test_inventory_actions_do_not_guess_non_wieldable_charms` |
| Use the numeric default as the maximum | `test_detect_number_prompt_uses_native_maximum` |
| Accept a 19-digit keypad draft | `test_number_pad_builds_and_parses_inline_drafts` |
| Permit Telegram callback payloads over 64 UTF-8 bytes | `test_game_callback_rejects_payloads_over_telegram_limit` |

No uncovered survivor was found in the bounded changed-code review.

## Assertion-quality review

- Every added regression contains a meaningful equality, membership,
  collection, or exception assertion.
- Exact C byte sequences are asserted where the adapter crosses the
  Python/native boundary.
- Boundary and negative cases cover invalid item classification, oversized
  numeric drafts, blank numeric submission, and oversized callback payloads.
- No assertion-free, tautological, sleep-based, or exception-swallowing test
  was introduced.

## Development support validation

- `tests/test_support.py`: 21 focused tests passed.
- Full suite: 188 tests passed.
- Ruff and `git diff --check`: passed.
- Regressions cover exact button order and URL, Stars invoice fields,
  pre-checkout tampering, payment persistence and thanks, `/paysupport`, and
  `/terms`.
