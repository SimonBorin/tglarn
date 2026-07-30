# Regression test plan

1. Adapter command sequences
   - Assert direct `wield`, `wear`, `drop`, `read`, `quaff`, and `eat` commands
     expand to the native command plus `?`.
   - Assert new top-level and run commands map to exact C bytes.

2. Indexed stores
   - Detect a store screen containing a blank separator.
   - Assert each option records its physical row and selection emits the
     correct number of `j` keys.

3. Inventory equipment actions
   - Assert wielded items expose `Unwield`, worn items expose `Take Off`, and
     ordinary items expose only valid actions.
   - Assert action callbacks produce exact C replay bytes.

4. Numeric keypad
   - Assert the keyboard renders digits, backspace, maximum, submit, and
     cancellation.
   - Assert callback parsing limits drafts to C `long` size and submit produces
     the existing `number:` adapter command.

5. Command UI and callback safety
   - Assert every meaningful mapped C command is reachable from a keyboard.
   - Assert callback construction rejects payloads over 64 UTF-8 bytes.

6. Validation
   - Run focused pytest files after each phase.
   - Run full pytest and Ruff once after all changes.
   - Review new assertions and record the final result in
     `.testagent/status.md`.

## Development support extension

1. Assert `⭐ Support Development ⭐` is strictly between `Legend` and
   `Main Menu`.
2. Assert the submenu exposes the exact Ko-fi URL and the 50/100/250 Telegram
   Stars choices.
3. Exercise invoice construction, pre-checkout validation, payment persistence,
   thanks, `/paysupport`, and `/terms`.
4. Run focused tests, the full suite, Ruff, and diff checks.

## Menu regression extension

1. Assert the ordinary main menu keeps Resume, renames the story action to
   Plot, adds About immediately below it, and removes Repository.
2. Assert Main Menu opened from the in-game menu has a final Back button that
   returns to the game menu while Resume remains available.
3. Exercise Resume through the registered callback handler and assert that it
   edits the current game response directly without sending splash photos.
4. Exercise Plot and About callbacks. Plot must retain the story; About must
   show the deployed runtime version, Simon Borin as author, and the canonical
   GitHub URL without a Repository menu action or work-account attribution.
5. Exercise Stars selection and assert it reuses the existing message, exposes
   a Back path, and does not call `answer_invoice`, `answer`, or another
   new-message API.
6. Run the focused regressions and record exact results below.

## Beta feedback and canonical-link extension

1. Parse README content and require a visible Beta heading, beta wording, an
   issue-report invitation, and the canonical GitHub Issues link.
2. Parse the Pages HTML as visible text and anchors; require beta/issue wording,
   the canonical Issues link, and the canonical repository link.
3. Format the bot About template and require the canonical Pages URL.
4. Run the new static tests together with the existing About callback
   regression, then run Ruff and `git diff --check`.
