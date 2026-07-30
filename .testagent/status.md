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

## Menu regression validation

- Full suite: **195 passed**.
- Focused suite:
  `tests/test_menu_regressions.py tests/test_support.py
  tests/test_menu_keyboards.py tests/test_menu_texts.py
  tests/test_relarn_process.py` — **142 passed**.
- Ruff on the focused test files and `git diff --check` — passed.
- Navigation coverage:
  `test_game_main_menu_keeps_resume_and_adds_bottom_back_to_game_menu` and
  `test_game_main_menu_callback_renders_contextual_back_path`.
- Resume coverage:
  `test_resume_game_renders_current_screen_without_start_splash` spies on the
  splash coroutine, forbids loading frames, and still permits Telegram's
  necessary one-time final game-image render.
- Plot/About coverage:
  `test_main_menu_separates_plot_from_project_about`,
  `test_plot_and_about_callbacks_show_distinct_content`, and
  `test_about_template_uses_runtime_version_placeholder`.
- Release-version invariant:
  `test_release_version_drives_image_tag_label_and_runtime_game_version`.
- Same-message Stars coverage:
  `test_stars_callback_reuses_current_message_with_invoice_link` passed for
  50, 100, and 250 Stars; it forbids `answer_invoice` and new text messages,
  requires an edited current message, and verifies the Back callback.
